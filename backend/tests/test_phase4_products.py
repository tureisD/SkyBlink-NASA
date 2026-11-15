"""Phase 4 stored-time, explicit staging coordinates and real image replay."""
from dataclasses import replace
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path

from astropy.io import fits
from fastapi.testclient import TestClient
import pytest

from app.main import app
from core.config import settings
from core.targets import TARGETS, get_target, propagated_coordinates
from core.target_profiles import corrected_targets
from services import spherex_pipeline as pipeline, recording
from services.irsa_client import ArtifactRecord
from services.product_metadata import creation_time
from services.provenance import read_record, verify_inputs

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("target", TARGETS, ids=lambda t: t.id)
@pytest.mark.parametrize("endpoint,filename", [("sky", "manifest.json"), ("spectrum", "spectrum.json")])
def test_saved_creation_time_is_stable_and_old_lineage_is_not_invented(target, endpoint, filename):
    product = json.loads((ROOT / "golden_cache" / target.id / filename).read_text(encoding="utf-8"))
    with TestClient(app) as client:
        params = {"ra": target.ra_epoch2025, "dec": target.dec_epoch2025, "target_id": target.id, "source": "saved"}
        first = client.get(f"/api/v1/{endpoint}", params=params)
        second = client.get(f"/api/v1/{endpoint}", params=params)
    assert first.status_code == second.status_code == 200
    first_prov = first.json()["provenance"]
    assert first_prov["generated_at"] == second.json()["provenance"]["generated_at"]
    assert datetime.fromisoformat(first_prov["generated_at"].replace("Z", "+00:00")) == creation_time(product).replace(microsecond=0)
    assert first_prov["analysis_id"] is None
    assert first_prov["analysis_record_url"] is None
    if endpoint == "spectrum" and target.id == "r_draconis":
        assert all(epoch["measurement_availability"]["usable_channels"] == 0 for epoch in first.json()["epochs"])


def test_creation_metadata_cannot_be_invented():
    for product in ({}, {"generated_at": "2026-11-14T00:00:00"}):
        with pytest.raises(ValueError):
            creation_time(product)


def test_corrected_astrometry_is_explicit_and_does_not_mutate_production():
    revised = {target.id: target for target in corrected_targets()}
    assert get_target("wise_0855").ra_epoch2025 == 133.75921
    assert revised["wise_0855"].ra_epoch2025 == pytest.approx(133.76021647484097, abs=1e-10)
    assert revised["r_draconis"].dec_epoch2025 == pytest.approx(66.7550234840942, abs=1e-10)
    assert revised["wise_0855"].reference_time_format == "mjd"
    assert revised["r_draconis"].reference_time_scale == "tcb"
    for target in revised.values():
        position = propagated_coordinates(target)
        assert position.ra.deg == target.ra_epoch2025
        assert position.dec.deg == target.dec_epoch2025


def test_pinned_real_images_replay_without_archive_or_golden_writes(monkeypatch, tmp_path):
    audit = json.loads((ROOT / "docs/evidence/phase3/phase3-science-results.json").read_text(encoding="utf-8"))
    samples = [s for s in audit["samples"] if s["target_id"] == "eps_indi_b" and s["band"] == 3]
    if len(samples) != 2 or any(not (ROOT / sample["path"]).exists() for sample in samples):
        pytest.skip("Acquire the real Phase 3 input files before image replay validation")
    records, contents = [], {}
    for sample in samples:
        content = (ROOT / sample["path"]).read_bytes()
        with fits.open(BytesIO(content), memmap=False) as hdul:
            header = hdul["IMAGE"].header
            assert header["TIMESYS"] == "UTC"
            record = ArtifactRecord(sample["uri"], header["MJD-BEG"], header["MJD-END"],
                                    3, "SPHEREx-D3", header["OBSID"], sample["release"], sample["collection"])
        records.append(record)
        contents[record] = content
    class PinnedArchive:
        discovery_metadata = {"source": "two_real_audit_inputs", "complete_archive_search": False}
        def query_artifacts(self, *args, **kwargs):
            return records
        def fetch_cutouts(self, chosen, ra, dec, size):
            assert ra == samples[0]["ra"] and dec == samples[0]["dec"]
            assert size == pytest.approx(samples[0]["fetch_size_deg"])
            return {record: contents[record] for record in chosen}
    isolated = replace(settings, cache_dir=tmp_path / "cache")
    monkeypatch.setattr(pipeline, "settings", isolated)
    monkeypatch.setattr(recording, "settings", isolated)
    manifest = pipeline._build_manifest("live_0123456789abcdef", samples[0]["ra"], samples[0]["dec"],
                                        cutout_size_deg=.2, live_mode=True, force_refresh=True,
                                        archive_client=PinnedArchive())
    directory = isolated.live_cache_dir / manifest["asset_key"]
    record = read_record(directory / "image_analysis.json")
    inputs = verify_inputs(record, isolated.cache_dir / "analysis-inputs")
    replay = pipeline.replay_image_record(record, {key: path.read_bytes() for key, path in inputs.items()}, tmp_path / "replay")
    assert replay["numerical_match"] is True
    assert replay["artifact_hashes_match"] is True
    assert len(record["identity"]["exposures"]) == 2
    assert manifest["provenance"]["analysis_id"] == record["analysis_id"]
    fingerprint_filename = f"analysis_{record['analysis_id'].removeprefix('sha256:')}.json"
    assert manifest["analysis_record"] == fingerprint_filename
    assert manifest["provenance"]["analysis_record_url"] == f"/api/v1/assets/{manifest['asset_key']}/{fingerprint_filename}"
    assert read_record(directory / fingerprint_filename) == record
    assert all(epoch["observation_range"]["time_scale"] == "utc" for epoch in manifest["epochs"])
    assert all(epoch["telemetry"]["quantity"] == "normalized_display_intensity" for epoch in manifest["epochs"])
