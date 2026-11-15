"""Retain fresh, bounded IRSA HTTP/discovery evidence without using saved URIs."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import httpx
from core.config import settings
from services.irsa_client import USER_AGENT, _rows_from_votable, IrsaClient, IRSANoData

GEOMETRY_FIELDS = (
    ("wrap-west", 359.9999, 0), ("wrap-east", .0001, 0),
    ("north-near", 0, 89.999), ("north-pole", 0, 90),
    ("south-near", 0, -89.999), ("south-pole", 0, -90),
    ("sparse-galactic-pole", 192.85948, 27.12825),
    ("dense-galactic-centre", 266.4051, -28.936175),
    ("historical-field-b", 334.622377, .806761),
)
SCIENCE_FIELDS = (("north-galactic-pole",192.85948,27.12825),
                  ("south-galactic-pole",12.85948,-27.12825),
                  ("north-b60",159.8833073544,39.5544404047),
                  ("south-b60",339.8833073544,-39.5544404047))


def now():
    return datetime.now(timezone.utc).isoformat()


def probe(case, directory: Path):
    started = time.monotonic()
    record = {"id": case["id"], "requested_at": now(), "method": case.get("method", "GET"),
              "endpoint": case["url"], "parameters": case.get("params", {}),
              "trust_env": case.get("trust_env", True), "timeout_seconds": case.get("timeout", 45),
              "user_agent": case.get("user_agent", USER_AGENT)}
    try:
        with httpx.Client(follow_redirects=False, trust_env=record["trust_env"],
                          headers={"User-Agent": record["user_agent"]},
                          timeout=httpx.Timeout(record["timeout_seconds"], connect=10)) as client:
            kwargs = ({"files": {key: (None,str(value)) for key,value in record["parameters"].items()}}
                      if case.get("multipart") else
                      {"params" if record["method"] == "GET" else "data": record["parameters"]})
            record["multipart"] = bool(case.get("multipart"))
            with client.stream(record["method"], record["endpoint"], **kwargs) as response:
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 128 * 1024 * 1024 or time.monotonic() - started > record["timeout_seconds"]:
                        raise RuntimeError("Probe response exceeded its bounded byte/time limit")
                body = bytes(content)
                digest = hashlib.sha256(body).hexdigest()
                path = directory / f'{case["id"]}-{digest}.response'
                path.write_bytes(body)
                record.update(status=response.status_code, bytes=len(body), sha256=digest,
                              response_path=path.relative_to(ROOT).as_posix(),
                              response_headers={key: response.headers[key] for key in
                                  ("server", "via", "content-type", "date", "retry-after", "x-cache", "cache-control", "location")
                                  if key in response.headers})
                if body.lstrip().startswith(b"<?xml") or b"<VOTABLE" in body[:500]:
                    try:
                        rows = _rows_from_votable(body)
                        record.update(votable_rows=len(rows), columns=list(rows[0]) if rows else [])
                    except Exception as exc:
                        record["votable_error"] = str(exc)
                elif response.status_code >= 400:
                    record["body_excerpt"] = body[:500].decode("utf-8", errors="replace")
    except Exception as exc:
        record.update(error=type(exc).__name__, message=str(exc))
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps({key: record.get(key) for key in ("id", "status", "votable_rows", "error", "message", "elapsed_seconds")}), flush=True)
    return record


def cases(ra, dec):
    simple = "SELECT TOP 1 table_name FROM TAP_SCHEMA.tables WHERE schema_name='spherex'"
    query = f"""SELECT TOP 5000 a.uri, p.time_bounds_lower AS mjd_obs,
p.time_bounds_upper AS mjd_obs_upper, p.energy_bandpassname AS detector_band,
p.planeid AS planeid, a.contentlength AS contentlength, p.datarelease AS datarelease
FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid
WHERE 1=CONTAINS(POINT('ICRS',{ra:.8f},{dec:.8f}),p.poly)
AND a.producttype='science' AND a.contenttype='image/fits'
AND (a.uri LIKE '%/dr1/%' OR a.uri LIKE '%/qr3/%')
ORDER BY p.time_bounds_lower ASC,a.uri ASC"""
    return [
        {"id": "sia_dr1_post", "url": "https://irsa.ipac.caltech.edu/SIA", "method": "POST",
         "params": {"COLLECTION": "spherex_dr1", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "sia_dr1_deep_post", "url": "https://irsa.ipac.caltech.edu/SIA", "method": "POST",
         "params": {"COLLECTION": "spherex_dr1_deep", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "sia_dr1_multipart", "url": "https://irsa.ipac.caltech.edu/SIA", "method": "POST", "multipart": True,
         "params": {"COLLECTION": "spherex_dr1", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "sia_combined", "url": "https://irsa.ipac.caltech.edu/SIA",
         "params": {"COLLECTION": ["spherex_dr1", "spherex_qr3", "spherex_dr1_deep", "spherex_qr3_deep"],
                    "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "availability", "url": "https://irsa.ipac.caltech.edu/TAP/availability", "timeout": 20},
        {"id": "tap_schema_get", "url": "https://irsa.ipac.caltech.edu/TAP/sync",
         "params": {"QUERY": simple, "FORMAT": "votable"}},
        {"id": "sia_dr1_current", "url": "https://irsa.ipac.caltech.edu/SIA",
         "params": {"COLLECTION": "spherex_dr1", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "sia_qr3_current", "url": "https://irsa.ipac.caltech.edu/SIA",
         "params": {"COLLECTION": "spherex_qr3", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "sia_dr1_deep", "url": "https://irsa.ipac.caltech.edu/SIA",
         "params": {"COLLECTION": "spherex_dr1_deep", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "sia_qr3_deep", "url": "https://irsa.ipac.caltech.edu/SIA",
         "params": {"COLLECTION": "spherex_qr3_deep", "POS": f"circle {ra:.8f} {dec:.8f} 0.000000", "RESPONSEFORMAT": "votable", "MAXREC": 100000}},
        {"id": "tap_position_get", "url": "https://irsa.ipac.caltech.edu/TAP/sync", "timeout": 90,
         "params": {"query": query, "format": "votable", "MAXREC": 5000}},
        {"id": "tap_position_post", "url": "https://irsa.ipac.caltech.edu/TAP/sync", "method": "POST", "timeout": 90,
         "params": {"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": query, "FORMAT": "votable", "MAXREC": 5000}},
    ]


def discover(field, directory, retries=3, allow_partial=False):
    name, ra, dec = field
    config = replace(settings, cache_dir=directory / name, retries=retries,
                     retry_backoff_seconds=.25, request_timeout_seconds=12,
                     tap_timeout_seconds=15, connect_timeout_seconds=6)
    started = time.monotonic()
    client = IrsaClient(config, deadline_at=started+90, use_cache=False)
    result = {"id": name, "query": {"ra": ra, "dec": dec}, "started_at": now(),
              "scope": "fresh complete-or-error DR1/QR3 wide+deep discovery; no cutouts/flux queried",
              "deadline_seconds": 90, "retries": retries, "proxy_revalidation_requested": True,
              "allow_partial": allow_partial}
    try:
        records = client.query_artifacts(ra,dec,allow_partial=allow_partial)
        result.update(status=client.discovery_metadata["status"], record_count=len(records), records=[asdict(record) for record in records],
                      detector_counts=dict(Counter(record.band for record in records)),
                      release_counts=dict(Counter(record.release for record in records)))
    except IRSANoData as exc:
        result.update(status="no_data", error=str(exc), records=[])
    except Exception as exc:
        result.update(status="failed", error=type(exc).__name__, message=str(exc))
    result["discovery"] = client.discovery_metadata
    result["elapsed_seconds"] = round(time.monotonic()-started,3)
    print(json.dumps({key:result.get(key) for key in ("id","status","record_count","elapsed_seconds","message")}),flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ra", type=float, default=192.85948)
    parser.add_argument("--dec", type=float, default=27.12825)
    parser.add_argument("--run", required=True, help="New evidence directory name")
    parser.add_argument("--cases", default="all", help="Comma-separated named probes, or all")
    parser.add_argument("--mode", choices=("transport", "discovery"), default="transport")
    parser.add_argument("--fields", default="geometry", help="geometry, science or comma-separated preregistered field IDs")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--allow-partial", action="store_true", help="Explicit available-observation policy; partial status remains visible")
    args = parser.parse_args(argv)
    if not 1 <= args.retries <= 4:
        parser.error("Retries must be 1..4")
    if not args.run.replace("-", "").replace("_", "").isalnum():
        parser.error("Run name must contain only letters, digits, underscores or dashes")
    directory = ROOT / "backend/.cache/phase4/online-discovery" / args.run
    directory.mkdir(parents=True, exist_ok=False)
    selected = [item for item in cases(args.ra, args.dec) if args.cases == "all" or item["id"] in args.cases.split(",")]
    report = {"run": args.run, "created_at": now(), "position": {"ra": args.ra, "dec": args.dec},
              "scope": "fresh upstream request diagnosis; single TOP page probes do not establish completeness", "requests": []}
    if args.mode == "discovery":
        fields = (list(GEOMETRY_FIELDS) if args.fields == "geometry" else list(SCIENCE_FIELDS)
                  if args.fields == "science" else [field for field in (*GEOMETRY_FIELDS,*SCIENCE_FIELDS) if field[0] in args.fields.split(",")])
        if not fields:
            parser.error("No preregistered fields selected")
        report.update(scope="fresh discovery matrix; explicit partial policy when requested; independent of historical saved input inventory",
                      allow_partial=args.allow_partial, fields=[])
        for field in fields:
            report["fields"].append(discover(field,directory,args.retries,args.allow_partial))
            temporary=directory/"report.tmp"
            temporary.write_text(json.dumps(report,indent=2)+"\n")
            temporary.replace(directory/"report.json")
        (ROOT / f"docs/evidence/phase4/phase4-online-discovery-{args.run}.json").write_text(json.dumps(report,indent=2)+"\n")
        return
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(probe, item, directory) for item in selected]
        for future in as_completed(futures):
            report["requests"].append(future.result())
            temporary = directory / "report.tmp"
            temporary.write_text(json.dumps(report, indent=2) + "\n")
            temporary.replace(directory / "report.json")
    destination = ROOT / f"docs/evidence/phase4/phase4-online-discovery-{args.run}.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
