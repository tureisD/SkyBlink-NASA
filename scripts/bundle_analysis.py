"""Export pinned real analysis inputs and source for independent offline replay.

The bundle is local and is not automatically published. Exact raw inputs and
source hashes are checked before copying; an existing output is never replaced.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.provenance import (ProvenanceError, capture_code_identity, capture_environment,
                                 content_hash, read_record, verify_inputs)


def bundle(record_paths: list[Path], store: Path, output: Path) -> dict:
    output = output.resolve()
    protected = (ROOT / "golden_cache", store.resolve())
    if output.exists() or any(output.is_relative_to(path.resolve()) or path.resolve().is_relative_to(output) for path in protected):
        raise ProvenanceError("Bundle must use a new directory outside approved products/input storage")
    records = [read_record(path) for path in record_paths]
    if not records:
        raise ProvenanceError("At least one pinned analysis record is required")
    code, environment = capture_code_identity(), capture_environment()
    checked = []
    for record in records:
        if record["identity"]["code"]["source_digest"] != code["source_digest"]:
            raise ProvenanceError("Cannot bundle changed processing source as the recorded implementation")
        if record["identity"]["environment"] != environment:
            raise ProvenanceError("Cannot freeze a different environment as the recorded one")
        checked.append(verify_inputs(record, store))
    # Record only package names and versions, never direct URLs or credentials.
    pins = {}
    for distribution in importlib.metadata.distributions():
        name, version = distribution.metadata.get("Name", ""), distribution.version
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or not re.fullmatch(r"[A-Za-z0-9.!+_-]+", version):
            raise ProvenanceError("Unexpected package identity in environment freeze")
        pins[name.lower()] = version
    output.mkdir(parents=True)
    index = {"schema_version": "skyblink.replay-bundle/1", "distribution": "local_unpublished",
             "scientific_validation": "not_established_by_packaging", "analyses": [], "files": {}}
    def put(relative: str, content: bytes):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        index["files"][relative] = {"sha256": content_hash(content), "size_bytes": len(content)}
    for relative, expected in code["files"].items():
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT) or source.is_symlink():
            raise ProvenanceError("Source path escapes repository")
        content = source.read_bytes()
        if content_hash(content) != expected:
            raise ProvenanceError("Source changed during bundle assembly")
        put("source/" + relative, content)
    for record, paths in zip(records, checked):
        digest = record["analysis_id"].removeprefix("sha256:")
        relative = f"records/{digest}.json"
        put(relative, (json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
        index["analyses"].append({"analysis_id": record["analysis_id"], "kind": record["identity"]["kind"], "record": relative})
        for descriptor in record["identity"]["inputs"]:
            name = "inputs/" + descriptor["store_key"]
            if name not in index["files"]:
                put(name, paths[descriptor["sha256"]].read_bytes())
    put("requirements-frozen.txt", ("\n".join(f"{name}=={version}" for name, version in sorted(pins.items())) + "\n").encode())
    put("environment.json", (json.dumps(environment, indent=2) + "\n").encode())
    put("REPLAY.txt", (
        "Create a fresh environment with the recorded Python version.\n"
        "Install: python -m pip install -r requirements-frozen.txt\n"
        "For each record listed in bundle.json, run from this directory:\n"
        "python source/scripts/replay_analysis.py replay --record records/<id>.json --store inputs --output results/<id>\n"
        "Inputs are retained locally; replay needs no archive network. Package installation may need network.\n"
        "Do not add drift overrides to claim a strict replay. Numerical agreement is not scientific validation.\n"
    ).encode())
    index["total_payload_bytes"] = sum(entry["size_bytes"] for entry in index["files"].values())
    (output / "bundle.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="append", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = bundle(args.record, args.store, args.output)
    except (ProvenanceError, OSError) as exc:
        print(f"Bundle failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"analyses": len(result["analyses"]), "bytes": result["total_payload_bytes"], "distribution": result["distribution"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
