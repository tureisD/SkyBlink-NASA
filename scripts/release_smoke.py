#!/usr/bin/env python3
"""Verify the production HTTP surface using explicit saved observations only.

--offline declares an upstream-independent check; it does not disable networking
for the server. Run with unreachable upstream endpoints to prove that boundary.
No archive acquisition, generated observations or cache writes are requested.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"wise_0855", "barnards_star", "eps_indi_b", "rw_aurigae", "r_draconis"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--offline", action="store_true", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "base_url": base,
              "mode": "explicit_saved_only", "checks": [], "passed": False}

    def get(route: str, expected: int = 200) -> tuple[bytes, dict]:
        assert route.startswith("/") and not route.startswith("//")
        try:
            response = urllib.request.urlopen(base + route, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            status = response.status
            headers = {key.lower(): value for key, value in response.headers.items()}
        report["checks"].append({"path": route, "status": status,
                                 "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        assert status == expected, (route, status, expected)
        return data, headers

    try:
        html, headers = get("/")
        assert "text/html" in headers.get("content-type", ""), "Root must serve HTML"
        assets = re.findall(r'(?:src|href)="(/assets/[^\"]+\.(?:js|css))"', html.decode())
        assert any(path.endswith(".js") for path in assets)
        for path in sorted(set(assets)):
            data, _ = get(path)
            local = ROOT / "frontend/dist" / path.lstrip("/")
            assert local.read_bytes() == data, f"Built asset differs: {path}"
        health = json.loads(get("/api/v1/health")[0])
        report["api_version"] = health["version"]
        assert health["status"] == "ok"
        expected_version = json.loads((ROOT / "backend/openapi.json").read_text(encoding="utf-8"))["info"]["version"]
        assert health["version"] == expected_version, "Runtime API version differs from current contract"
        targets = json.loads(get("/api/v1/targets?source=saved")[0])["targets"]
        assert {item["id"] for item in targets} == TARGETS
        checked = set()
        for target in targets:
            query = urllib.parse.urlencode({"source": "saved", "target_id": target["id"],
                "ra": target["ra_epoch2025"], "dec": target["dec_epoch2025"]})
            for endpoint in ("sky", "spectrum"):
                data = json.loads(get(f"/api/v1/{endpoint}?{query}")[0])
                assert data["provenance"]["is_simulated_fallback"] is False
                assert data["provenance"]["data_access"] == "saved", "Offline check must use explicit saved data"
                assert data["epochs"], (target["id"], endpoint)
                if endpoint == "sky":
                    paths = [url for epoch in data["epochs"] for url in epoch["frames"].values()]
                    paths += [url for frames in data["differences"].values() for url in frames.values()]
                    paths += [value for key, value in data["reference_overlays"].items()
                              if key != "attribution"]
                    paths += [epoch["telemetry"]["url"] for epoch in data["epochs"] if epoch.get("telemetry")]
                    for path in paths:
                        if path in checked:
                            continue
                        checked.add(path)
                        body, _ = get(path)
                        prefix = f"/api/v1/assets/{target['id']}/"
                        assert path.startswith(prefix)
                        filename = path.removeprefix(prefix)
                        assert "/" not in filename and "\\" not in filename
                        assert body == (ROOT / "golden_cache" / target["id"] / filename).read_bytes(), path
        report["saved_assets_verified"] = len(checked)
        for path in ("/mock", "/mock/manifest.json", "/api/v1/assets/fallback_wise_0855/manifest.json",
                     "/api/v1/assets/mock/manifest.json", "/api/v1/nonexistent-release-route"):
            get(path, 404)
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("passed", "api_version", "saved_assets_verified", "error")}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
