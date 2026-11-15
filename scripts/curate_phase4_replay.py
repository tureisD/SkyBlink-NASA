"""Create a real offline image/native-spectrum replay example from audit inputs.

The two Epsilon Indi D3 exposures are visualization-compatible at the original
fixed audit coordinates. This is not corrected-target astrometric validation
or a science-valid variability claim; independent static-control gates apply.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from core.config import settings  # noqa: E402
from scripts.stage_phase4 import record_from_fits  # noqa: E402
from services import recording, spectrophotometry, spherex_pipeline  # noqa: E402
from services.provenance import (ProvenanceError, canonical_json, content_hash, make_record,
                                 native_method, read_record, utc_now, verify_inputs)  # noqa: E402


def curate(output: Path) -> dict:
    output = output.resolve()
    protected = [settings.golden_cache_dir.resolve(), (ROOT / "golden_cache").resolve()]
    if any(output == path or output.is_relative_to(path) for path in protected):
        raise ProvenanceError("Curated replay output must be outside approved products")
    output.mkdir(parents=True, exist_ok=False)
    audit_path = ROOT / "docs/evidence/phase3/phase3-science-results.json"
    audit_bytes = audit_path.read_bytes()
    audit = json.loads(audit_bytes)
    samples = [sample for sample in audit["samples"] if sample["target_id"] == "eps_indi_b" and sample["band"] == 3]
    if len(samples) != 2:
        raise ProvenanceError("Expected the two explicitly audited Epsilon Indi D3 exposures")
    ra, dec = samples[0]["ra"], samples[0]["dec"]
    padded_size = samples[0]["fetch_size_deg"]
    records, contents = [], {}
    for sample in samples:
        if (sample["ra"], sample["dec"], sample["fetch_size_deg"]) != (ra, dec, padded_size):
            raise ProvenanceError("Curated inputs have different recorded cutout parameters")
        path = (ROOT / sample["path"]).resolve()
        if not path.is_relative_to((ROOT / "backend/.cache/phase3").resolve()):
            raise ProvenanceError("Audit input path escapes its real-input cache")
        content = path.read_bytes()
        if content_hash(content) != sample["sha256"] or len(content) != sample["bytes"]:
            raise ProvenanceError("Curated real source hash/size differs from the audit")
        record, _ = record_from_fits(sample["uri"], content)
        records.append(record)
        contents[record] = content
    class AuditArchive:
        discovery_metadata = {
            "source": "two_hash_verified_phase3_eps_indi_b_D3_inputs",
            "audit_manifest_sha256": content_hash(audit_bytes),
            "complete_archive_search": False,
            "selection_scope": "curated_visualization_replay_only",
            "scientific_validation": "no_passing_independent_static_control_claim",
            "fixed_query": {"ra": ra, "dec": dec},
            "target_astrometry": None,
        }
        def query_artifacts(self, query_ra, query_dec, **kwargs):
            if (query_ra, query_dec) != (ra, dec):
                raise ProvenanceError("Curated query must equal its actual input coordinates")
            return list(records)
        def fetch_cutouts(self, selected, query_ra, query_dec, size_deg, **kwargs):
            if ((query_ra, query_dec) != (ra, dec)
                    or not math.isclose(size_deg, padded_size, rel_tol=0, abs_tol=1e-12)
                    or any(record not in contents for record in selected)):
                raise ProvenanceError("Requested input differs from retained curated bytes")
            return {record: contents[record] for record in selected}
    isolated = replace(settings, cache_dir=output / "cache")
    isolated.ensure_dirs()
    spherex_pipeline.settings = isolated
    spectrophotometry.settings = isolated
    recording.settings = isolated
    asset_key = "live_" + content_hash(canonical_json({"ra": ra, "dec": dec, "purpose": "phase4_curated_eps"}))[:16]
    manifest = spherex_pipeline._build_manifest(asset_key, ra, dec, cutout_size_deg=.2,
                                               live_mode=True, force_refresh=True,
                                               archive_client=AuditArchive())
    directory = isolated.live_cache_dir / asset_key
    image_record = read_record(directory / "image_analysis.json")
    descriptors = recording.retain_inputs(contents, ra, dec, padded_size)
    epoch_payloads, exposures = [], []
    for epoch in spherex_pipeline.group_epochs(records):
        channels = []
        for record in epoch.records:
            parsed = spherex_pipeline.parse_cutout(contents[record], ra, dec)
            diagnostics = {}
            channel = spectrophotometry.extract_channel(parsed, record.band, diagnostics=diagnostics)
            exposures.append({"input_sha256": descriptors[record]["sha256"],
                              "epoch_id": epoch.epoch_id, "detector": record.band,
                              "extraction": {"ra": ra, "dec": dec}, "artifact": asdict(record),
                              "expected_channel": channel,
                              "diagnostics": recording.json_values(diagnostics)})
            if channel is not None:
                channels.append(channel)
        collection, release = spherex_pipeline.epoch_collection_release(epoch)
        epoch_payloads.append({"epoch_id": epoch.epoch_id, "label": epoch.label,
                               "collection": collection, "release": release, "channels": channels})
    created_at = utc_now()
    spectrum_record = make_record(kind="spectrum", query={"ra": ra, "dec": dec},
        inputs=recording.unique_inputs(descriptors), exposures=exposures, method=native_method(),
        selection={**AuditArchive.discovery_metadata,
                   "cutout_policy": "native extraction from the same retained padded image inputs; no extra crop",
                   "image_analysis_id": image_record["analysis_id"],
                   "image_input_overlap": "all inputs shared by content hash",
                   "observation_mjd_scale": "utc"}, outputs={"epochs": epoch_payloads}, created_at=created_at)
    spectrum = {"version": spectrophotometry.SPECTRUM_CACHE_VERSION, "asset_key": asset_key,
                "query": {"ra": ra, "dec": dec}, "target_id": None, "generated_at": created_at,
                "confidence": "low", "epochs": epoch_payloads,
                "provenance": {"is_simulated_fallback": False,
                               "scope": "curated_native_extraction_from_padded_real_inputs",
                               "scientific_validation": "not_established_by_replay"}}
    recording.publish_record(directory, spectrum, spectrum_record, "spectrum_analysis.json")
    spectrophotometry._write_spectrum(asset_key, spectrum)
    inputs = verify_inputs(image_record, isolated.cache_dir / "analysis-inputs")
    verify_inputs(spectrum_record, isolated.cache_dir / "analysis-inputs")
    summary = {"status": "curated_unpromoted", "promotion_eligible": False,
               "source": "real Phase 3 Epsilon Indi D3 audit pair",
               "scientific_scope": "visualization-compatible image pair and native extraction replay; no calibrated variability acceptance",
               "query": {"ra": ra, "dec": dec, "size_deg": .2, "target": None},
               "cutout_size_deg": padded_size, "shared_input_hashes": sorted(inputs),
               "image_record": str((directory / "image_analysis.json").relative_to(output).as_posix()),
               "spectrum_record": str((directory / "spectrum_analysis.json").relative_to(output).as_posix()),
               "image_analysis_id": image_record["analysis_id"],
               "spectrum_analysis_id": spectrum_record["analysis_id"],
               "store": "cache/analysis-inputs", "reference_overlays": "not included"}
    (output / "curated-summary.json").write_bytes(canonical_json(summary) + b"\n")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(curate(args.output), indent=2))
        return 0
    except (ProvenanceError, OSError) as exc:
        print(f"Curated replay build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
