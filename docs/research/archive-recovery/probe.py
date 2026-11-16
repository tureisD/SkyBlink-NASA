"""Portable read-only IRSA incident probe (Python standard library only).

Run from each network close in time, with a NEW output directory:
    python probe.py --out receipts/network-a
No credentials, async jobs, downloads of science images, or automatic retries.
Results are connectivity diagnostics, never observation inputs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://irsa.ipac.caltech.edu"
LIMIT = 1024 * 1024


def queries():
    yield "availability", BASE + "/TAP/availability"
    for name, query in [
        ("schema", "SELECT TOP 1 table_name FROM TAP_SCHEMA.tables"),
        ("catalog", "SELECT TOP 1 ra,dec FROM fp_psc"),
        ("plane", "SELECT TOP 1 planeid FROM spherex.plane"),
        ("obscore", "SELECT TOP 1 obs_id,access_url FROM spherex.obscore"),
    ]:
        yield name, BASE + "/TAP/sync?" + urllib.parse.urlencode({
            "REQUEST": "doQuery", "LANG": "ADQL", "QUERY": query,
            "FORMAT": "votable", "MAXREC": "1",
        })
    yield "official_sia", BASE + "/SIA?" + urllib.parse.urlencode({
        "COLLECTION": "spherex_dr1", "POS": "circle 127.69444 -39.17760 0.01",
        "RESPONSEFORMAT": "HTML",
    })
    yield "static_control", BASE + "/cloud_access/"


def inspect_xml(body):
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {"xml": False}
    statuses = [dict(value=e.get("value"), text=e.text)
                for e in root.iter() if e.tag.split("}")[-1] == "INFO"
                and e.get("name") == "QUERY_STATUS"]
    return {"xml": True, "root": root.tag.split("}")[-1],
            "query_status": statuses,
            "tabledata_rows": sum(e.tag.split("}")[-1] == "TR" for e in root.iter())}


def probe(name, url, out, timeout):
    start = time.monotonic()
    item = {"name": name, "url": url,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "socket_timeout_seconds": timeout}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SkyBlink-incident-probe/1"})
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error  # Retain the HTTP error body as evidence.
        with response:
            item.update(status=response.code, final_url=response.url,
                        headers={k: v for k, v in response.headers.items()
                                 if k.lower() in {"server", "date", "content-type", "via", "retry-after"}})
            body = response.read(LIMIT + 1)
        truncated = len(body) > LIMIT
        body = body[:LIMIT]
        (out / (name + ".body")).write_bytes(body)
        item.update(bytes_retained=len(body), truncated=truncated,
                    sha256=hashlib.sha256(body).hexdigest())
        if not truncated:
            item.update(inspect_xml(body))
        item["science_query_success"] = (
            name in {"catalog", "plane", "obscore"} and item.get("status") == 200
            and not truncated and item.get("root") == "VOTABLE"
            and item.get("tabledata_rows", 0) > 0
            and any(s["value"] == "OK" for s in item.get("query_status", []))
            and not any(s["value"] == "ERROR" for s in item.get("query_status", []))
        )
    except Exception as error:
        item.update(exception=type(error).__name__, message=str(error), science_query_success=False)
    item["elapsed_seconds"] = round(time.monotonic() - start, 3)
    (out / (name + ".json")).write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(item), flush=True)
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error("timeout must be greater than zero and at most 60 seconds")
    args.out.mkdir(parents=True, exist_ok=False)
    env = {"created_at": datetime.now(timezone.utc).isoformat(),
           "platform": platform.platform(), "python": platform.python_version(),
           "proxy_variable_names_present": [k for k in os.environ
               if k.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}],
           "system_proxy_schemes": list(urllib.request.getproxies()),
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "scope": "Read-only diagnostics, not complete discovery or scientific acceptance"}
    try:
        env["resolved_addresses"] = sorted({r[4][0] for r in socket.getaddrinfo("irsa.ipac.caltech.edu", 443)})
    except OSError as error:
        env["dns_error"] = str(error)
    (args.out / "environment.json").write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    results = [probe(name, url, args.out, args.timeout) for name, url in queries()]
    (args.out / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0 if all(r.get("science_query_success") for r in results
                    if r["name"] in {"catalog", "plane", "obscore"}) else 1


if __name__ == "__main__":
    raise SystemExit(main())
