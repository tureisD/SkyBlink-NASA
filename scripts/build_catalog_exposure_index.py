"""Extract bounded real exposure metadata from five verified analysis records.

This does not query IRSA, download images, or build observation products. The
index is an explicitly historical lookup, never a current archive inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.provenance import validate_record  # noqa: E402

TARGETS = ("wise_0855", "barnards_star", "eps_indi_b", "rw_aurigae", "r_draconis")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(source: Path) -> dict:
    targets = {}
    for target in TARGETS:
        path = source / f"{target}-analysis.json"
        raw = path.read_bytes()
        record = json.loads(raw)
        validate_record(record)
        identity = record["identity"]
        selection = identity["selection"]
        discovered = {item["uri"]: item for item in selection["discovered_records"]}
        inputs = identity["inputs"]
        urls = set()
        for item in inputs:
            url = urlsplit(item["source_url"])
            if url.scheme != "https" or url.netloc != "irsa.ipac.caltech.edu" or not url.path.startswith(("/ibe/data/spherex/dr1/level2/", "/ibe/data/spherex/qr3/level2/")):
                raise ValueError(f"Noncanonical real source URI: {item['source_url']}")
            stored = ROOT / "backend/.cache/analysis-inputs" / item["store_key"]
            if sha(stored.read_bytes()) != item["sha256"]:
                raise ValueError(f"Retained input hash mismatch: {stored}")
            urls.add(f"{url.scheme}://{url.netloc}{url.path}")
        selected = {item["uri"] for epoch in selection["selected_epochs"] for item in epoch["records"]}
        if not selected <= urls:
            raise ValueError(f"Selected pair missing retained bytes: {target}")
        rows = [discovered[url] for url in urls]
        rows.sort(key=lambda item: (item["mjd_lower"], item["band"], item["uri"]))
        if any(not row.get("s_region") for row in rows):
            raise ValueError(f"Unrecorded footprint: {target}")
        targets[target] = {
            "analysis_id": record["analysis_id"],
            "analysis_record_sha256": sha(raw),
            "record_created_at": record["created_at"],
            "query": {"ra": identity["query"]["ra"], "dec": identity["query"]["dec"]},
            "source_record_path": path.resolve().relative_to(ROOT).as_posix(),
            "records": rows,
        }
    return {
        "schema_version": "skyblink.catalog-exposure-index/1",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "completeness": "Bounded previously verified exposures only; not a current or complete archive inventory.",
        "usage": "Explicit catalog recovery only. Download FITS fresh and rerun all current compatibility and usability gates. No cached observation products are included.",
        "targets": targets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "backend/.cache/phase5/recurrent-download-diagnosis/final")
    parser.add_argument("--out", type=Path, default=ROOT / "data/catalog-exposure-index.json")
    args = parser.parse_args()
    result = build(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.out), "sha256": sha(args.out.read_bytes()), "records": {k: len(v["records"]) for k, v in result["targets"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
