"""Verify, acquire, or replay a pinned scientific record without discovery.

Run from any working directory; see docs/reference/phase4-replay-schema.md. Replay writes
only into a newly created output directory and defaults to offline execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services.provenance import (  # noqa: E402
    ProvenanceError, acquire_inputs, canonical_json, capture_code_identity,
    capture_environment, content_hash, native_method, read_record, utc_now,
    validate_record, verify_channels, verify_inputs,
)


def _new_output(path: Path, store_dir: Path) -> Path:
    output = Path(path).resolve()
    # A replay never writes into saved assets, even when a caller names a new
    # descendant. Also keep content retention separate from output generation.
    forbidden = [ROOT / "golden_cache", Path(store_dir).resolve()]
    from core.config import settings
    forbidden.append(settings.golden_cache_dir.resolve())
    if any(output == directory or output.is_relative_to(directory) for directory in forbidden):
        raise ProvenanceError("Replay output must be outside approved assets and the input store")
    output.mkdir(parents=True, exist_ok=False)
    return output


def replay(record: dict[str, Any], store_dir: Path, output_dir: Path, *,
           allow_code_drift: bool = False, allow_environment_drift: bool = False) -> dict[str, Any]:
    """Offline replay only; acquisition is an explicit separate operation."""
    validate_record(record)
    identity = record["identity"]
    code = capture_code_identity()
    environment = capture_environment()
    # Content identity, rather than git dirty status or local commit ancestry,
    # determines whether the actual processing implementation matches.
    code_matches = code["source_digest"] == identity["code"].get("source_digest")
    environment_matches = environment == identity["environment"]
    if not code_matches and not allow_code_drift:
        raise ProvenanceError("Processing source differs; restore recorded files, or explicitly use --allow-code-drift for a comparison run")
    if not environment_matches and not allow_environment_drift:
        raise ProvenanceError("Replay environment differs; restore recorded versions/platform, or explicitly use --allow-environment-drift")
    paths = verify_inputs(record, store_dir)
    output = _new_output(output_dir, store_dir)
    report: dict[str, Any] = {
        "analysis_id": record["analysis_id"], "replayed_at": utc_now(),
        "kind": identity["kind"], "input_hashes_verified": sorted(paths),
        "code_matches": code_matches, "environment_matches": environment_matches,
        "actual_code": code, "actual_environment": environment,
        "scientific_validation": "not_established_by_replay",
        "strict_replay": code_matches and environment_matches,
    }
    if identity["kind"] == "spectrum":
        if identity["method"] != native_method():
            raise ProvenanceError("Recorded extraction method/masks differ from the supported native method")
        from services.spherex_pipeline import parse_cutout
        from services.spectrophotometry import extract_channel
        channels = []
        failures = []
        for index, exposure in enumerate(identity["exposures"]):
            position = exposure["extraction"]
            parsed = parse_cutout(paths[exposure["input_sha256"]].read_bytes(),
                                  float(position["ra"]), float(position["dec"]))
            channel = extract_channel(parsed, exposure["detector"])
            differences = verify_channels(exposure["expected_channel"], channel)
            channels.append({"exposure_index": index, "input_sha256": exposure["input_sha256"],
                             "epoch_id": exposure["epoch_id"], "extraction": position,
                             "channel": channel, "background": parsed.background_metadata,
                             "differences": differences})
            failures.extend(f"exposure {index}: {item}" for item in differences)
        result_bytes = canonical_json({"analysis_id": record["analysis_id"], "exposures": channels}) + b"\n"
        (output / "channels.json").write_bytes(result_bytes)
        report.update({"numerical_match": not failures, "differences": failures,
                       "outputs": {"channels.json": {"sha256": content_hash(result_bytes),
                                                     "size_bytes": len(result_bytes)}}})
    else:
        from services import spherex_pipeline
        adapter = getattr(spherex_pipeline, "replay_image_record", None)
        if adapter is None:
            raise ProvenanceError("Image replay adapter unavailable; this record is input-verifiable only")
        image_result = adapter(record, {digest: path.read_bytes() for digest, path in paths.items()}, output)
        report["image_replay"] = image_result
        # An adapter must explicitly attest comparison, not just successful rendering.
        report["numerical_match"] = image_result.get("numerical_match") is True
    report["verified"] = report["strict_replay"] and report["numerical_match"]
    (output / "replay-report.json").write_bytes(canonical_json(report) + b"\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "acquire", "replay"))
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="New directory; required for replay")
    parser.add_argument("--timeout", type=float, default=120.0, help="Total acquisition budget in seconds")
    parser.add_argument("--allow-code-drift", action="store_true", help="Comparison only; cannot pass strict replay")
    parser.add_argument("--allow-environment-drift", action="store_true", help="Comparison only; cannot pass strict replay")
    args = parser.parse_args(argv)
    try:
        record = read_record(args.record)
        if args.action == "replay":
            if args.output is None:
                parser.error("--output is required for replay")
            result = replay(record, args.store, args.output, allow_code_drift=args.allow_code_drift,
                            allow_environment_drift=args.allow_environment_drift)
            print(json.dumps({"analysis_id": record["analysis_id"], "verified": result["verified"],
                              "numerical_match": result["numerical_match"],
                              "report": str(args.output / "replay-report.json")}))
            return 0 if result["verified"] else 1
        paths = (acquire_inputs(record, args.store, timeout_seconds=args.timeout)
                 if args.action == "acquire" else verify_inputs(record, args.store))
        print(json.dumps({"analysis_id": record["analysis_id"], "verified_inputs": len(paths),
                          "scope": "input_identity_only; not numerical or scientific validation"}))
        return 0
    except (ProvenanceError, OSError) as exc:
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
