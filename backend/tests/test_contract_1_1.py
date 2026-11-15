"""Focused tests for the additive 1.1.0 contract and real saved observations.

The 1.1.0 freeze adds optional telemetry, LVF geometry, objective difference
candidates, display-core provenance, and per-channel photometry/aperture
provenance.  Existing 1.0.0 golden data must remain valid through the model
defaults; real golden API responses exercise the new fields end to end.
"""

from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from models import (
    DetectedCandidate,
    Epoch,
    LVFGeometry,
    SkyResponse,
    SpectrumChannel,
    SpectrumResponse,
    TelemetryAsset,
)
from models.version import API_CONTRACT_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "golden_cache"
GRID_WIDTH = 240
GRID_HEIGHT = 240
TELEMETRY_BYTES = GRID_WIDTH * GRID_HEIGHT * (2 + 4)  # float16 + uint32 LE
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _real_response(endpoint: str) -> dict:
    from fastapi.testclient import TestClient
    from app.main import app
    from core.targets import get_target

    target = get_target("wise_0855")
    with TestClient(app) as client:
        response = client.get(f"/api/v1/{endpoint}", params={
            "source": "saved", "target_id": target.id, "ra": target.ra_epoch2025,
            "dec": target.dec_epoch2025,
        })
    assert response.status_code == 200
    return response.json()


def _real_manifest() -> dict:
    return _real_response("sky")


def _real_spectrum() -> dict:
    return _real_response("spectrum")


def _telemetry_path(url: str) -> Path:
    return GOLDEN_DIR / "wise_0855" / Path(url).name


def test_contract_and_openapi_are_the_current_version() -> None:
    assert API_CONTRACT_VERSION == "1.6.0"
    spec = _load_json(REPO_ROOT / "backend" / "openapi.json")
    assert spec["info"]["version"] == "1.6.0"
    schemas = spec["components"]["schemas"]
    for name in ("TelemetryAsset", "LVFGeometry", "DetectedCandidate"):
        assert name in schemas
    epoch_properties = schemas["Epoch"]["properties"]
    for key in ("telemetry", "lvf_geometry", "candidates", "core_inpainted"):
        assert key in epoch_properties
    assert (
        schemas["TelemetryAsset"]["properties"]["format"]["const"]
        == "float16_uint32_le_gzip"
    )
    assert schemas["DetectedCandidate"]["additionalProperties"] is False
    assert "confidence" not in schemas["DetectedCandidate"]["properties"]
    assert schemas["SpectrumChannel"]["properties"]["photometry_method"]["enum"] == [
        "aperture_12.3",
        "crowded_diff_6.8",
    ]


def test_telemetry_asset_requires_sidecar_format_and_bounds() -> None:
    base = {
        "url": "/api/v1/assets/wise_0855/telemetry_2025_E1.bin.gz",
        "format": "float16_uint32_le_gzip",
        "width": GRID_WIDTH,
        "height": GRID_HEIGHT,
        "byte_size": 90127,
    }
    asset = TelemetryAsset(**base)
    assert asset.flux_band == "all"
    assert TelemetryAsset(**base, flux_band="thermal").flux_band == "thermal"
    assert TelemetryAsset(**{**base, "byte_size": 0}).byte_size == 0
    assert TelemetryAsset(**{**base, "width": 1, "height": 1}).width == 1

    for missing in ("url", "format", "width", "height", "byte_size"):
        with pytest.raises(ValidationError):
            TelemetryAsset(**{key: value for key, value in base.items() if key != missing})
    for field, value in (
        ("format", "float32_uint32_le_gzip"),
        ("width", 0),
        ("height", 0),
        ("byte_size", -1),
        ("flux_band", "optical"),
    ):
        with pytest.raises(ValidationError):
            TelemetryAsset(**{**base, field: value})


def test_lvf_geometry_detector_bounds_and_finite_real_values() -> None:
    for detector in (1, 6):
        geometry = LVFGeometry(
            detector=detector,
            pa_deg=25.0,
            grad_um_per_arcsec=0.047,
        )
        assert math.isfinite(geometry.pa_deg)
        assert math.isfinite(geometry.grad_um_per_arcsec)
    for detector in (0, 7):
        with pytest.raises(ValidationError):
            LVFGeometry(detector=detector, pa_deg=25.0, grad_um_per_arcsec=0.047)

    manifest = _real_manifest()
    for epoch in manifest["epochs"]:
        geometries = epoch["lvf_geometry"]
        assert len(geometries) == 6
        assert {item["detector"] for item in geometries} == set(range(1, 7))
        for item in geometries:
            geometry = LVFGeometry(**item)
            assert 1 <= geometry.detector <= 6
            assert math.isfinite(geometry.pa_deg)
            assert math.isfinite(geometry.grad_um_per_arcsec)


def test_detected_candidate_is_objective_and_forbids_confidence() -> None:
    base = {
        "id": "candidate-1",
        "ra": 133.75921,
        "dec": -7.24216,
        "x_px": 122.0,
        "y_px": 118.0,
        "kind": "dipole",
        "snr": 5.2,
        "label": "Objective difference-frame dipole",
    }
    candidate = DetectedCandidate(**base)
    assert candidate.kind == "dipole"
    assert candidate.snr == pytest.approx(5.2)
    assert candidate.is_artifact_clean is True
    assert "confidence" not in DetectedCandidate.model_fields
    assert DetectedCandidate(**{**base, "kind": "variable"}).kind == "variable"

    with pytest.raises(ValidationError):
        DetectedCandidate(**{**base, "kind": "transit"})
    with pytest.raises(ValidationError):
        DetectedCandidate(**{key: value for key, value in base.items() if key != "snr"})
    with pytest.raises(ValidationError):
        DetectedCandidate(**base, confidence=0.99)


def test_spectrum_channel_1_1_defaults_and_modes() -> None:
    base = {
        "detector": 6,
        "wavelength_um": 4.682,
        "bandwidth_um": 0.037,
        "flags": 2097152,
        "is_flagged_bad": False,
        "clean_fraction": 0.86,
        "is_used_in_photometry": True,
    }
    channel = SpectrumChannel(**base)
    assert channel.photometry_method == "aperture_12.3"
    assert channel.aperture_mode == "standard_12.3"
    assert channel.aperture_radius_arcsec == 12.3

    crowded = SpectrumChannel(
        **base,
        photometry_method="crowded_diff_6.8",
        aperture_mode="crowded_diff_6.8",
        aperture_radius_arcsec=6.76,
    )
    assert crowded.photometry_method == "crowded_diff_6.8"
    assert crowded.aperture_mode == "crowded_diff_6.8"
    assert crowded.aperture_radius_arcsec == pytest.approx(6.76)

    with pytest.raises(ValidationError):
        SpectrumChannel(**base, photometry_method="psf_wing_fit")
    with pytest.raises(ValidationError):
        SpectrumChannel(**base, aperture_mode="psf_wing_fit")
    with pytest.raises(ValidationError):
        SpectrumChannel(**base, aperture_radius_arcsec=0.0)


def test_real_manifest_round_trips_with_1_1_fields() -> None:
    manifest = _real_manifest()
    response = SkyResponse.model_validate(manifest)
    assert response.provenance.is_simulated_fallback is False
    assert [epoch.epoch_id for epoch in response.epochs] == ["2025_E1", "2025_E2", "2026_E1"]
    for epoch in response.epochs:
        assert epoch.telemetry is not None
        assert epoch.telemetry.format == "float16_uint32_le_gzip"
        assert epoch.telemetry.width == GRID_WIDTH
        assert epoch.telemetry.height == GRID_HEIGHT
        assert epoch.telemetry.byte_size >= 0
        assert epoch.telemetry.flux_band in {"thermal", "all"}
        assert epoch.lvf_geometry is not None
        assert len(epoch.lvf_geometry) == 6
        assert {item.detector for item in epoch.lvf_geometry} == set(range(1, 7))
        for item in epoch.lvf_geometry:
            assert math.isfinite(item.pa_deg)
            assert math.isfinite(item.grad_um_per_arcsec)
        assert epoch.core_inpainted is False

    assert all(epoch.candidates is None for epoch in response.epochs)

    assert {
        "optical_dss2_red",
        "mid_ir_wise_w1",
        "gaia_sources_url",
        "attribution",
    } <= set(response.reference_overlays)

    dumped = response.model_dump(mode="json")
    assert dumped["epochs"][0]["telemetry"]["format"] == "float16_uint32_le_gzip"
    assert dumped["epochs"][0]["core_inpainted"] is False
    assert set(dumped["epochs"][0]) == set(Epoch.model_fields)


def test_real_telemetry_sidecars_are_gzip_float16_uint32_le() -> None:
    manifest = _real_manifest()
    for epoch in manifest["epochs"]:
        telemetry = epoch["telemetry"]
        path = _telemetry_path(telemetry["url"])
        assert path.is_file(), f"missing telemetry sidecar {path}"
        content = path.read_bytes()
        assert content[:2] == b"\x1f\x8b"
        assert len(content) == telemetry["byte_size"]
        assert telemetry["width"] == GRID_WIDTH
        assert telemetry["height"] == GRID_HEIGHT
        decoded = gzip.decompress(content)
        assert len(decoded) == TELEMETRY_BYTES
        assert len(decoded) == telemetry["width"] * telemetry["height"] * (2 + 4)


def test_real_spectrum_round_trips_with_1_1_aperture_modes() -> None:
    payload = _real_spectrum()
    response = SpectrumResponse.model_validate(payload)
    assert [epoch.epoch_id for epoch in response.epochs] == ["2025_E1", "2025_E2", "2026_E1"]
    assert response.provenance.is_simulated_fallback is False
    for epoch in response.epochs:
        assert epoch.channels
        for channel in epoch.channels:
            assert channel.photometry_method == "aperture_12.3"
            assert channel.aperture_mode == "standard_12.3"
            assert channel.aperture_radius_arcsec == pytest.approx(12.3)


def test_golden_manifests_carry_real_1_1_telemetry() -> None:
    for target_id in TARGET_IDS:
        manifest = _load_json(GOLDEN_DIR / target_id / "manifest.json")
        assert manifest["epochs"]
        expected_band = "thermal" if target_id == "wise_0855" else "all"
        for epoch_payload in manifest["epochs"]:
            epoch = Epoch.model_validate(
                {
                    key: value
                    for key, value in epoch_payload.items()
                    if key in Epoch.model_fields
                }
            )
            # Stage 2 rebuilt the golden cache with B8 telemetry and LVF data.
            assert epoch.telemetry is not None, (target_id, epoch.epoch_id)
            assert epoch.telemetry.format == "float16_uint32_le_gzip"
            assert epoch.telemetry.width == GRID_WIDTH
            assert epoch.telemetry.height == GRID_HEIGHT
            assert epoch.telemetry.byte_size > 0
            assert epoch.telemetry.url.startswith(
                f"/api/v1/assets/{target_id}/telemetry_"
            )
            assert epoch.telemetry.flux_band == expected_band
            assert epoch.lvf_geometry is not None, (target_id, epoch.epoch_id)
            detectors = {item.detector for item in epoch.lvf_geometry}
            assert detectors and detectors <= set(range(1, 7))
            for item in epoch.lvf_geometry:
                assert math.isfinite(item.pa_deg)
                assert math.isfinite(item.grad_um_per_arcsec)
                assert item.grad_um_per_arcsec > 0.0
            # B9 candidate triage and display-only inpainting are not built.
            assert epoch.candidates is None
            assert epoch.core_inpainted is False
