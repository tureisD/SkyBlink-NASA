#!/usr/bin/env python3
"""Exercise measured spectral WCS on a recorded real SPHEREx input cutout."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import numpy as np
from core.config import Settings
from services.irsa_client import ArtifactRecord, IrsaClient
from services.live_selection import spectral_signature


def main():
    manifest = json.loads((ROOT / "golden_cache/wise_0855/manifest.json").read_text())
    epoch = manifest["epochs"][0]
    uri = epoch["band_stats"]["6"]["artifact_uris"][0]
    ra, dec = manifest["query"]["ra"], manifest["query"]["dec"]
    record = ArtifactRecord(uri, epoch["mjd_mean"], None, 6, "SPHEREx-D6", uri, epoch["release"], epoch["collection"])
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "source_uri": uri,
              "source_metadata": "golden_cache/wise_0855/manifest.json#epochs[0].band_stats.6.artifact_uris[0]",
              "ra": ra, "dec": dec, "cases": [],
              "limitation": "One recorded input exercises actual spectral WCS; not proof of pair compatibility or whole-field science correctness."}
    with tempfile.TemporaryDirectory(prefix="skyblink-real-wcs-") as cache:
        for size in (.05, .2):
            start = time.monotonic()
            padded = math.sqrt(2) * size + 2 * 6.15 / 3600
            case = {"size_deg": size, "fetch_size_deg": padded}
            client = IrsaClient(replace(Settings(), cache_dir=Path(cache), retries=1,
                                       request_timeout_seconds=20), deadline_at=start + 45)
            try:
                content = client.fetch_cutout(record, ra, dec, padded)
                signature = spectral_signature(content, ra, dec, size)
                case.update(status="success", bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
                            wavelength_um=[float(v) if np.isfinite(v) else None for v in signature[0]],
                            bandwidth_um=[float(v) if np.isfinite(v) else None for v in signature[1]],
                            finite_samples=int(np.isfinite(signature).all(axis=0).sum()))
            except Exception as exc:
                case.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            case["seconds"] = round(time.monotonic() - start, 3)
            report["cases"].append(case)
    (ROOT / "docs/evidence/phase2/phase2-real-spectral-signature.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
