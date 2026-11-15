"""Fresh end-to-end archive requests with explicit coverage and lineage checks.

This is an observation-access probe, not a variability validation. No response
is fabricated; failures are retained. Run against a separately started API.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx


def probe(base, query, name, endpoint):
    started = time.monotonic()
    result = {"name": name, "endpoint": endpoint, "query": query,
              "requested_at": datetime.now(timezone.utc).isoformat()}
    try:
        with httpx.Client(timeout=140) as client:
            response = client.get(f"{base}/api/v1/{endpoint}", params=query)
            result.update(http_status=response.status_code, elapsed_seconds=round(time.monotonic()-started, 3))
            body = response.json()
            if response.status_code != 200:
                result.update(error=body, access_verified=False)
                return result
            provenance = body["provenance"]
            link = provenance.get("analysis_record_url")
            if not link or not link.startswith("/api/v1/assets/live_"):
                raise ValueError("Archive response lacks a live-namespace analysis record")
            record_response = client.get(base + link)
            record_response.raise_for_status()
            record = record_response.json()
            if record["analysis_id"] != provenance.get("analysis_id"):
                raise ValueError("Linked analysis identity differs from the response")
            identity = record["identity"]
            receipts = record.get("acquisition", {}).get("cutouts") or []
            successful = [item for item in receipts if item.get("outcome") == "downloaded"]
            # Fail closed if receipt vocabulary differs; never infer freshness
            # from a local response or from is_simulated_fallback alone.
            if not successful:
                successful = [item for item in receipts if item.get("sha256") and item.get("retrieved_at")]
            all_fresh = bool(successful) and all(item.get("from_cache") is False for item in successful)
            linked = {item["sha256"] for item in identity["inputs"]}
            acquired = {item["sha256"] for item in successful}
            result.update(analysis_id=record["analysis_id"], data_access=provenance.get("data_access"),
                          record_sha256=hashlib.sha256(record_response.content).hexdigest(),
                          comparison_status=provenance.get("comparison_status"),
                          comparison_reason=provenance.get("comparison_reason"),
                          discovery=identity["selection"].get("scope"),
                          acquired_inputs=len(successful), linked_inputs=len(linked),
                          fresh_input_receipts=all_fresh, all_inputs_have_fresh_receipts=linked <= acquired,
                          epochs=[{"id": e["epoch_id"], "range": e.get("observation_range"),
                                   "release": e["release"], "availability": e.get("measurement_availability")}
                                  for e in body["epochs"]],
                          access_verified=(provenance.get("data_access") == "archive" and all_fresh
                                           and linked <= acquired and provenance.get("is_simulated_fallback") is False),
                          science_acceptance="not_established_by_access_probe")
            if endpoint == "sky":
                urls = {url for epoch in body["epochs"] for url in epoch["frames"].values()}
                assets = []
                for url in sorted(urls):
                    asset = client.get(base + url)
                    asset.raise_for_status()
                    digest = hashlib.sha256(asset.content).hexdigest()
                    if digest != identity["outputs"]["assets"][Path(url).name]:
                        raise ValueError("Displayed asset does not match its analysis record")
                    assets.append({"url": url, "sha256": digest})
                result["assets"] = assets
                result["differences"] = list(body["differences"])
            else:
                channels = [channel for epoch in body["epochs"] for channel in epoch["channels"]]
                result["channels"] = {"present": len(channels),
                                      "finite": sum(c["flux_ujy"] is not None for c in channels),
                                      "eligible": sum(c["is_used_in_photometry"] for c in channels)}
    except Exception as exc:
        result.update(access_verified=False, exception=type(exc).__name__, error=str(exc),
                      elapsed_seconds=round(time.monotonic()-started, 3))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8015")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=[1, 2], default=1)
    parser.add_argument("--target", default="all")
    parser.add_argument("--endpoint", choices=["sky", "spectrum", "both"], default="both")
    parser.add_argument("--coordinates", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output path; previous probe evidence must be retained")
    targets = httpx.get(args.base + "/api/v1/targets", timeout=15).raise_for_status().json()["targets"]
    jobs = []
    for target in targets:
        if args.target not in ("all", target["id"]):
            continue
        for endpoint in (["sky", "spectrum"] if args.endpoint == "both" else [args.endpoint]):
            query = {"source": "archive", "ra": target["ra_epoch2025"], "dec": target["dec_epoch2025"], "target_id": target["id"]}
            if endpoint == "sky": query["size"] = .2
            jobs.append((query, target["id"], endpoint))
    if args.coordinates:
        for name, ra, dec in [("north_galactic_pole",192.85948,27.12825),
                              ("north_celestial_pole",0.,90.), ("ra_wrap",359.9999999,-20.)]:
            jobs.append(({"source":"archive","ra":ra,"dec":dec,"size":.05},name,"sky"))
    result = {"scope":"fresh archive access, not universal scientific validity",
              "started_at":datetime.now(timezone.utc).isoformat(),"results":[]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(probe, args.base, *job) for job in jobs]
        for future in futures:
            item = future.result()
            result["results"].append(item)
            args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
            print(json.dumps({key:item.get(key) for key in ["name","endpoint","http_status","elapsed_seconds","access_verified"]}),flush=True)
    return 0 if all(item["access_verified"] for item in result["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
