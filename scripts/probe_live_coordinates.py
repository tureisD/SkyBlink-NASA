#!/usr/bin/env python3
"""Bounded live-coordinate verification; no fabricated or committed sky data.

Example: python scripts/probe_live_coordinates.py --fields all --sizes .05,.2
The default smoke is two noncatalog fields. Each field/size gets an isolated
temporary cache. Warm repeats occur only after a successful cold response.
An optional same-position two-client run checks shared work, not load capacity.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "high_latitude": (210.80227, 54.34895),
    "low_latitude": (83.82, -5.39),
    "dense_plane": (266.4051, -28.936175),
    "north_pole": (20.0, 89.9),
    "south_pole": (200.0, -89.9),
    "ra_zero_west": (359.99, -20.0),
    "ra_zero_east": (0.01, -20.0),
    "field_offset": (210.90227, 54.44895),
    "detector_edge": (134.90921145189702, -7.347808815089828),
}


def _worker(field: str, size: float, concurrent: bool) -> list[dict]:
    sys.path.insert(0, str(ROOT / "backend"))
    from fastapi.testclient import TestClient
    from app.main import app
    import logging
    logging.disable(logging.CRITICAL)
    ra, dec = FIELDS[field]

    def request(label: str) -> dict:
        started = time.monotonic()
        with TestClient(app) as client:
            response = client.get("/api/v1/sky", params={"ra": ra, "dec": dec, "size": size})
            payload = response.json()
            elapsed = time.monotonic() - started
            result = {"mode": label, "status": response.status_code, "seconds": round(elapsed, 3),
                      "epoch_ids": [epoch["epoch_id"] for epoch in payload.get("epochs", [])],
                      "difference_pairs": list(payload.get("differences", {})),
                      "provenance": payload.get("provenance"), "error": payload.get("error")}
            if response.status_code == 200:
                urls = {url for epoch in payload["epochs"] for url in epoch["frames"].values()}
                urls.update(url for pair in payload["differences"].values() for url in pair.values())
                result["asset_statuses"] = {url: client.get(url).status_code for url in sorted(urls)}
                result["query"] = payload["query"]
                result["bands_by_epoch"] = {epoch["epoch_id"]: sorted(epoch["frames"]) for epoch in payload["epochs"]}
                result["simulated"] = payload["provenance"]["is_simulated_fallback"]
        return result

    if concurrent:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(request, f"concurrent_{index}") for index in (1, 2)]
            return [future.result() for future in futures]
    cold = request("cold")
    results = [cold]
    if cold["status"] == 200:
        results.append(request("warm"))
    else:
        results.append({"mode": "warm", "skipped": "Cold retrieval failed; no warm product exists."})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", default="high_latitude,ra_zero_east")
    parser.add_argument("--sizes", default=".05,.2")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/phase2/phase2-live-results.json")
    parser.add_argument("--case-timeout", type=float, default=145.0)
    parser.add_argument("--sky-deadline", type=float, help="Diagnostic override of backend sky budget; does not validate the production deadline")
    parser.add_argument("--concurrent", action="store_true", help="Also run one cold same-position pair, for the first requested field/size")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(_worker(args.fields, float(args.sizes), args.concurrent)), flush=True)
        return 0
    fields = list(FIELDS) if args.fields == "all" else args.fields.split(",")
    sizes = [float(value) for value in args.sizes.split(",")]
    if any(field not in FIELDS for field in fields) or any(size not in {.05, .2} for size in sizes):
        parser.error("Use known field names (or all) and sizes .05,.2")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "method": "Actual FastAPI TestClient requests through the live IRSA pipeline; isolated per-case cache; no network stubs.",
              "limitations": "Does not test browser or public reverse proxy. field_offset samples a shifted cutout, not a proven detector-footprint boundary. 503 is not evidence of absent sky coverage.",
              "case_timeout_seconds": args.case_timeout,
              "sky_deadline_override_seconds": args.sky_deadline,
              "cases": []}
    jobs = [(field, size, False) for field in fields for size in sizes]
    if args.concurrent:
        jobs.append((fields[0], sizes[0], True))
    for field, size, concurrent in jobs:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="skyblink-live-probe-") as cache:
            env = dict(os.environ, CACHE_DIR=cache, LOG_LEVEL="CRITICAL")
            if args.sky_deadline is not None:
                env["LIVE_SKY_DEADLINE_SECONDS"] = str(args.sky_deadline)
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--fields", field, "--sizes", str(size)]
            if concurrent:
                command.append("--concurrent")
            case = {"field": field, "ra": FIELDS[field][0], "dec": FIELDS[field][1], "size_deg": size, "concurrent": concurrent}
            try:
                process = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True, timeout=args.case_timeout)
                case["results"] = json.loads(process.stdout) if process.returncode == 0 else []
                if process.returncode:
                    case["worker_error"] = process.stderr[-2000:]
            except subprocess.TimeoutExpired as exc:
                case["worker_error"] = "Hard wall-clock probe timeout; process terminated, no successful result assumed."
                if exc.stdout:
                    output = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
                    try:
                        case["results"] = json.loads(output)
                        case["worker_error"] = "HTTP results were emitted, but process cleanup exceeded the hard wall-clock bound."
                        case["cleanup_timeout"] = True
                    except json.JSONDecodeError:
                        case["partial_worker_stdout"] = output[-2000:]
            case["wall_seconds"] = round(time.monotonic() - started, 3)
            report["cases"].append(case)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(case), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
