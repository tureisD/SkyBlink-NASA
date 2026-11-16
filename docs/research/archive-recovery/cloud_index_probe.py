"""Research-only, bounded S3 header inventory and coordinate search.

This does not implement SkyBlink discovery. Scope is exactly one detector
directory; a miss never means no archive data. No science pixels are retained.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET

from astropy.io import fits
from astropy.wcs import WCS
import httpx
import numpy as np

BASE = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
PREFIX_PATTERN = r"(?:dr1|qr3)/level2/[A-Za-z0-9_]+/l2b-[A-Za-z0-9-]+/[1-6]/"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    temporary.replace(path)


def image_header(body):
    """Read named IMAGE header after an empty PRIMARY; never access pixel data."""
    offset = 0
    for position in range(2):
        end = next((i+80 for i in range(offset, len(body)-79, 80)
                    if body[i:i+8] == b"END     "), None)
        if end is None:
            return None
        padded_end = offset + math.ceil((end-offset)/2880)*2880
        if padded_end > len(body):
            return None
        header = fits.Header.fromstring(body[offset:padded_end].decode("ascii"), sep="")
        if position == 0:
            if not header.get("SIMPLE") or header.get("NAXIS") != 0:
                raise ValueError("Expected an empty PRIMARY; unsupported layout")
        elif header.get("EXTNAME") == "IMAGE" and header.get("NAXIS") == 2:
            return header, body[offset:padded_end]
        else:
            raise ValueError("Expected named IMAGE after PRIMARY; unsupported layout")
        offset = padded_end
    return None


def contains(header, ra, dec):
    """Spatial TAN-SIP inverse, plus forward round trip; center containment only."""
    wcs = WCS(header).celestial
    with np.errstate(all="ignore"):
        xy = wcs.all_world2pix([[ra, dec]], 0, quiet=True)[0]
    if not np.isfinite(xy).all():
        return False
    x, y = map(float, xy)
    if not (-0.5 <= x < header["NAXIS1"]-0.5 and -0.5 <= y < header["NAXIS2"]-0.5):
        return False
    returned = wcs.all_pix2world([[x, y]], 0)[0]
    # Stable angular separation using 3-D unit vectors, including wrap/poles.
    def vector(lon, lat):
        lon, lat = np.deg2rad([lon, lat])
        return np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])
    separation = np.linalg.norm(vector(ra, dec)-vector(*returned))
    return bool(np.isfinite(separation) and separation < np.deg2rad(1e-6))


def build(args):
    if not re.fullmatch(PREFIX_PATTERN, args.prefix):
        raise ValueError("Scope must be one DR1/QR3 level2 planning-period/version/detector directory")
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "headers").mkdir()
    started = time.monotonic()
    snapshot = {"scope": args.prefix, "all_archive_complete": False,
                "enumeration_complete": False, "headers_complete": False,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "base_url": BASE, "objects": [], "failures": [], "list_pages": [],
                "script_sha256": digest(Path(__file__).read_bytes()),
                "max_objects": args.max_objects, "workers": args.workers}
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        items = []
        token = None
        seen_tokens = set()
        for page in range(4):
            params = {"list-type": "2", "prefix": args.prefix, "max-keys": "1000"}
            if token:
                params["continuation-token"] = token
            response = client.get(BASE, params=params)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            name = f"list-{page:02}.xml"
            (args.out/name).write_bytes(response.content)
            snapshot["list_pages"].append({"file": name, "sha256": digest(response.content),
                                           "url": str(response.url), "status": response.status_code})
            for item in root.findall("s:Contents", NS):
                key = item.findtext("s:Key", namespaces=NS)
                if not key.startswith(args.prefix) or "/" in key[len(args.prefix):]:
                    raise ValueError("Listing escaped the requested detector directory")
                if not key.endswith(".fits"):
                    continue
                items.append({"key": key, "etag": item.findtext("s:ETag", namespaces=NS),
                              "size": int(item.findtext("s:Size", namespaces=NS)),
                              "last_modified": item.findtext("s:LastModified", namespaces=NS)})
            if len(items) > args.max_objects:
                raise ValueError("Object cap exceeded; no header crawl started")
            if root.findtext("s:IsTruncated", namespaces=NS) == "false":
                snapshot["enumeration_complete"] = True
                break
            token = root.findtext("s:NextContinuationToken", namespaces=NS)
            if not token or token in seen_tokens:
                raise ValueError("Missing/repeated pagination token")
            seen_tokens.add(token)
        if not snapshot["enumeration_complete"] or len({x["key"] for x in items}) != len(items):
            raise ValueError("Incomplete/duplicate directory listing; no header crawl started")
        print(f"Listed {len(items)} objects; starting {args.workers} bounded workers", flush=True)
        snapshot["listed_objects"] = len(items)
        save_json(args.out/"listing.json", snapshot | {"objects": items})

        def fetch(item):
            tick = time.monotonic()
            receipt = dict(item, url=BASE+quote(item["key"], safe="/"), range_requests=[])
            try:
                for limit in (28800, 57600, 115200):
                    with client.stream("GET", receipt["url"], headers={
                        "Range": f"bytes=0-{limit-1}", "If-Match": item["etag"]}) as response:
                        part = {"status": response.status_code, "range": response.headers.get("content-range"),
                                "etag": response.headers.get("etag")}
                        receipt["range_requests"].append(part)
                        if (response.status_code != 206 or part["etag"] != item["etag"]
                                or part["range"] != f"bytes 0-{limit-1}/{item['size']}"):
                            raise ValueError("Range/ETag/length mismatch; refusing object")
                        body = b""
                        for chunk in response.iter_bytes():
                            body += chunk
                            if len(body) > limit:
                                raise ValueError("Oversized range body")
                    if len(body) != limit:
                        raise ValueError("Short range body")
                    part.update(bytes=len(body), sha256=digest(body))
                    extracted = image_header(body)
                    if extracted is not None:
                        break
                if extracted is None:
                    raise ValueError("IMAGE header exceeds diagnostic cap")
                header, header_bytes = extracted
                mjd_begin, mjd_end = float(header["MJD-BEG"]), float(header["MJD-END"])
                if header["TIMESYS"] != "UTC" or not (math.isfinite(mjd_begin) and mjd_begin <= mjd_end < float('inf')):
                    raise ValueError("Unsupported/invalid observation time")
                detector = int(header["DETECTOR"])
                if detector != int(args.prefix.rstrip('/').rsplit('/', 1)[1]):
                    raise ValueError("Header/path detector mismatch")
                wcs = WCS(header).celestial
                center = [(header["NAXIS1"]-1)/2, (header["NAXIS2"]-1)/2]
                center_world = wcs.all_pix2world([center], 0)[0].tolist()
                if not contains(header, *center_world):
                    raise ValueError("Spatial WCS center failed containment/round trip")
                name = "headers/" + digest(item["key"].encode()) + ".header"
                (args.out/name).write_bytes(header_bytes)
                receipt.update(header_file=name, header_sha256=digest(header_bytes),
                               mjd_begin=mjd_begin, mjd_end=mjd_end, timesys="UTC", detector=detector,
                               center_world=center_world, release=args.prefix.split('/')[0],
                               collection=None)
            except Exception as error:
                receipt.update(error=type(error).__name__, message=str(error))
            receipt["elapsed_seconds"] = round(time.monotonic()-tick, 3)
            return receipt

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(fetch, item) for item in items]
            for n, future in enumerate(as_completed(futures), 1):
                item = future.result()
                snapshot["failures" if "error" in item else "objects"].append(item)
                if n % 100 == 0:
                    print(f"Headers {n}/{len(items)}, failures {len(snapshot['failures'])}", flush=True)
                    save_json(args.out/"checkpoint.json", snapshot)
    snapshot["objects"].sort(key=lambda item: item["key"])
    snapshot.update(headers_complete=not snapshot["failures"] and len(snapshot["objects"]) == len(items),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    elapsed_seconds=round(time.monotonic()-started, 3))
    snapshot["range_bytes_received"] = sum(p.get("bytes", 0) for item in
        snapshot["objects"]+snapshot["failures"] for p in item["range_requests"])
    save_json(args.out/"snapshot.json", snapshot)
    print(json.dumps({k: v for k, v in snapshot.items() if k not in {'objects','failures','list_pages'}}), flush=True)


def query(args):
    snapshot = json.loads(args.snapshot.read_text())
    matches, failures = [], []
    for item in snapshot["objects"]:
        try:
            raw = (args.snapshot.parent/item["header_file"]).read_bytes()
            if digest(raw) != item["header_sha256"]:
                raise ValueError("Header hash mismatch")
            header = fits.Header.fromstring(raw.decode("ascii"), sep="")
            if contains(header, args.ra, args.dec):
                matches.append({k: item[k] for k in ('key','url','etag','mjd_begin','mjd_end','detector','header_sha256')})
        except Exception as error:
            failures.append({"key": item["key"], "error": str(error)})
    result = {"ra": args.ra, "dec": args.dec, "scope": snapshot["scope"],
              "snapshot_sha256": digest(args.snapshot.read_bytes()), "matches": matches,
              "search_failures": failures, "indexed_objects": len(snapshot["objects"]),
              "scope_complete": snapshot["headers_complete"] and snapshot["enumeration_complete"] and not failures,
              "all_archive_complete": False,
              "meaning": "Center containment only; no full-field, wavelength, photometry or pair acceptance"}
    save_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in {'matches','search_failures'}})
          + f" matches={len(matches)} errors={len(failures)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--prefix", required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--max-objects", type=int, choices=range(1, 2501), default=2000)
    b.add_argument("--workers", type=int, choices=range(1, 7), default=4)
    q = sub.add_parser("query")
    q.add_argument("--snapshot", type=Path, required=True)
    q.add_argument("--ra", type=float, required=True)
    q.add_argument("--dec", type=float, required=True)
    q.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "query" and not (0 <= args.ra < 360 and -90 <= args.dec <= 90):
        parser.error("Finite RA [0,360) and Dec [-90,90] required")
    (build if args.command == "build" else query)(args)


if __name__ == "__main__":
    main()
