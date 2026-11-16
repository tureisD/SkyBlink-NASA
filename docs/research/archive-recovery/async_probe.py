"""Bounded diagnostic of the documented TAP async lifecycle, not runtime discovery.

Creates one small job, records every response, then requests abort/deletion.
Run with a new --out directory. No observation input or cache is generated.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urljoin, urlparse

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=180, choices=range(30, 301))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    base = "https://irsa.ipac.caltech.edu/TAP/async"
    query = "SELECT TOP 1 planeid FROM spherex.plane"
    events = []
    job = None
    phase = None
    started = time.monotonic()
    deadline = started + args.seconds
    with httpx.Client(timeout=15, follow_redirects=False, headers={
        "User-Agent": "SkyBlink-archive-diagnostic/1", "Cache-Control": "no-cache"
    }) as client:
        def request(name, method, url, **kwargs):
            tick = time.monotonic()
            event = {"name": name, "method": method, "url": url,
                     "requested_at": datetime.now(timezone.utc).isoformat()}
            response = None
            try:
                response = client.request(method, url, **kwargs)
                body = response.content
                (args.out / (name + ".body")).write_bytes(body)
                event.update(status=response.status_code, bytes=len(body),
                             sha256=hashlib.sha256(body).hexdigest(),
                             location=response.headers.get("location"),
                             headers={k: v for k, v in response.headers.items()
                                      if k in {"date", "server", "content-type", "age"}})
            except httpx.HTTPError as error:
                event.update(exception=type(error).__name__, message=str(error))
            event["elapsed_seconds"] = round(time.monotonic() - tick, 3)
            events.append(event)
            (args.out / "events.json").write_text(json.dumps(events, indent=2)+"\n")
            print(json.dumps(event), flush=True)
            return response

        try:
            response = request("create", "POST", base, data={
                "QUERY": query, "LANG": "ADQL", "REQUEST": "doQuery",
                "FORMAT": "votable", "MAXREC": "1", "PHASE": "RUN"})
            if response is not None and response.status_code == 303:
                candidate = urljoin(base, response.headers.get("location", ""))
                parsed = urlparse(candidate)
                if (parsed.scheme == "https" and parsed.netloc == "irsa.ipac.caltech.edu"
                        and parsed.path.startswith("/TAP/async/")
                        and parsed.path.rsplit("/", 1)[-1].isdigit()):
                    job = candidate
            if job:
                n = 0
                while time.monotonic() < deadline:
                    response = request(f"phase-{n:02}", "GET", job + "/phase",
                                       timeout=min(15, max(1, deadline-time.monotonic())))
                    if response is None or response.status_code != 200:
                        break
                    phase = response.text.strip()
                    print("phase=" + phase, flush=True)
                    if phase == "COMPLETED":
                        request("result", "GET", job + "/results/result")
                        break
                    if phase in {"ERROR", "ABORTED", "ABORT"}:
                        request("error", "GET", job + "/error")
                        break
                    if phase not in {"QUEUED", "EXECUTING", "PENDING"}:
                        break
                    if phase == "PENDING":
                        request("run", "POST", job + "/phase", data={"PHASE": "RUN"})
                    time.sleep(min(10, max(0, deadline-time.monotonic())))
                    n += 1
        finally:
            if job:
                if phase not in {"COMPLETED", "ERROR", "ABORTED", "ABORT"}:
                    request("abort", "POST", job + "/phase", data={"PHASE": "ABORT"})
                request("delete", "DELETE", job)
                request("verify-delete", "GET", job)
            summary = {"query": query, "job": job, "last_phase": phase,
                       "elapsed_seconds": round(time.monotonic()-started, 3),
                       "poll_budget_seconds": args.seconds,
                       "cleanup_verified": bool(events and events[-1]["name"] == "verify-delete"
                                                and events[-1].get("status") in {404, 410}),
                       "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            (args.out / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
            print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
