"""Audit retained catalog responses without requesting new archive observations.

Verifies current processing-source identity, retained input bytes, fresh receipt
coverage, immutable output bytes, and (optionally) HTTP-served assets. This is
integrity evidence, not scientific target detection or stability validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.provenance import capture_code_identity, validate_record  # noqa: E402


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def audit(directory: Path, api_base: str | None, *, products_only: bool = False) -> dict:
    current = capture_code_identity()
    rows = []
    excluded_errors = []
    for response_path in sorted(directory.glob("*-response.json")):
        response = json.loads(response_path.read_bytes())
        if "error" in response:
            if products_only:
                excluded_errors.append({"path": str(response_path), "sha256": sha(response_path.read_bytes()),
                                        "error_envelope": response["error"]})
                continue
            rows.append({"target": response_path.name.removesuffix("-response.json"),
                         "response_sha256": sha(response_path.read_bytes()),
                         "errors": ["Archive acquisition returned an error; no successful product to verify"],
                         "error_envelope": response["error"], "passed": False})
            continue
        record_path = response_path.with_name(response_path.name.replace("-response.json", "-analysis.json"))
        record = json.loads(record_path.read_bytes())
        validate_record(record)
        identity = record["identity"]
        errors = []
        if identity["code"]["files"] != current["files"]:
            errors.append("Processing-source whitelist differs")
        if identity["code"]["source_digest"] != current["source_digest"]:
            errors.append("Processing source digest differs")
        discovery = record.get("acquisition", {}).get("discovery", {})
        discovery_responses = []
        for receipt in discovery.get("responses", []):
            relative = Path(receipt["cache_relative_path"])
            cache_root = (ROOT / "backend/.cache").resolve()
            path = (cache_root / relative).resolve()
            if not path.is_relative_to(cache_root):
                raise ValueError("Discovery receipt path escapes the input cache")
            data = path.read_bytes()
            valid = receipt.get("raw_response_retained") is True and sha(data) == receipt["sha256"] and len(data) == receipt["size_bytes"]
            if not valid:
                errors.append(f"Discovery response mismatch {relative}")
            discovery_responses.append({"source_url": receipt["source_url"], "sha256": receipt["sha256"],
                                        "retrieved_at": receipt.get("retrieved_at"), "http_status": receipt["http_status"], "verified": valid})
        known_index = None
        if discovery.get("mode") == "known":
            index_bytes = (ROOT / "data/catalog-exposure-index.json").read_bytes()
            index = json.loads(index_bytes)
            entry = index["targets"][discovery["target_id"]]
            verified = (
                discovery.get("status") == "partial"
                and discovery.get("method") == "recorded_exposure_index"
                and discovery.get("index_sha256") == sha(index_bytes)
                and discovery.get("source_analysis_id") == entry["analysis_id"]
                and discovery.get("source_record_sha256") == entry["analysis_record_sha256"]
                and discovery.get("source_record_created_at") == entry["record_created_at"]
                and response["provenance"].get("discovery_mode") == "known"
            )
            allowed = {item["uri"]: item for item in entry["records"]}
            selected_records = identity.get("selection", {}).get("discovered_records", [])
            if any(allowed.get(item["uri"]) != item for item in selected_records):
                verified = False
            if any(urlsplit(item["source_url"])._replace(query="", fragment="").geturl() not in allowed for item in identity["inputs"]):
                verified = False
            known_index = {"sha256": sha(index_bytes), "source_analysis_id": entry["analysis_id"],
                           "bounded_record_count": len(allowed), "verified": verified}
            if not verified:
                errors.append("Known exposure index/provenance mismatch")
        elif not discovery_responses:
            errors.append("No retained discovery response receipts")
        inputs = []
        receipts = record.get("acquisition", {}).get("cutouts", [])
        fresh = [r for r in receipts if r.get("outcome") == "fresh_archive_response"]
        by_hash = {r["sha256"]: r for r in fresh}
        for item in identity["inputs"]:
            path = ROOT / "backend/.cache/analysis-inputs" / item["store_key"]
            data = path.read_bytes()
            valid = sha(data) == item["sha256"] and len(data) == item["size_bytes"]
            receipt = by_hash.get(item["sha256"])
            receipt_ok = bool(receipt and receipt.get("from_cache") is False and receipt.get("source_url") == item["source_url"])
            if not valid or not receipt_ok:
                errors.append(f"Input/receipt mismatch {item['sha256']}")
            inputs.append({"sha256": item["sha256"], "bytes": len(data), "verified": valid, "fresh_receipt_verified": receipt_ok})
        if {r["sha256"] for r in fresh} != {i["sha256"] for i in identity["inputs"]}:
            errors.append("Successful fresh receipts and retained input set differ")
        urls = set()
        for epoch in response["epochs"]:
            urls.update(epoch.get("frames", {}).values())
            if epoch.get("telemetry"):
                urls.add(epoch["telemetry"]["url"])
        for bands in response.get("differences", {}).values():
            urls.update(bands.values())
        assets = []
        expected = identity.get("outputs", {}).get("assets", {})
        for url in sorted(urls):
            relative = url.split("/api/v1/assets/", 1)[1]
            path = ROOT / "backend/.cache/live" / relative
            digest = sha(path.read_bytes())
            valid = expected.get(path.name) == digest
            served = sha(urlopen(api_base.rstrip("/") + url, timeout=15).read()) if api_base else None
            if not valid or served is not None and served != digest:
                errors.append(f"Output mismatch {relative}")
            assets.append({"url": url, "sha256": digest, "record_verified": valid, "served_sha256": served})
        rows.append({"target": response_path.name.removesuffix("-response.json"), "response_sha256": sha(response_path.read_bytes()),
                     "record_path": str(record_path.relative_to(ROOT)), "analysis_id": record["analysis_id"],
                     "method": identity["method"]["version"], "source_digest": current["source_digest"],
                     "discovery_status": discovery.get("status"), "discovery_responses": discovery_responses,
                     "known_index": known_index,
                     "code_files_verified": not any("source" in e for e in errors), "inputs": inputs, "assets": assets,
                     "errors": errors, "passed": not errors})
    return {"verified_at": datetime.now(timezone.utc).isoformat(), "scope": "Local retained bytes and optional served assets only; no archive query; no astrophysical certification", "excluded_error_responses": excluded_errors, "results": rows, "passed": bool(rows) and all(r["passed"] for r in rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--api-base")
    parser.add_argument("--products-only", action="store_true", help="Audit successful products; retain excluded error envelopes separately, never count them as successes")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory.resolve(), args.api_base, products_only=args.products_only)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "targets": len(result["results"]), "errors": [r["errors"] for r in result["results"]]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
