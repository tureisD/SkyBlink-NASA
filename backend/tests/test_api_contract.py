"""API contract tests (``AGENTS.md`` §3, O1 decisions + additive 1.1.0 freeze).

These tests pin the frozen 1.1.0 schema, check that extra fields are rejected,
exercise query validation, enforce the O1 nullable spectrum fields, and
validate the committed golden cache  against
the contract.  The 1.1.0 fields are optional/additive, so existing 1.0.0
golden data still validates with the model defaults.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from models import (
    Epoch,
    ErrorResponse,
    FlagSummary,
    FluxNormalization,
    HealthResponse,
    SkyProvenance,
    SkyQuery,
    SkyResponse,
    SpectrumChannel,
    WCS,
)
from models.version import API_CONTRACT_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "golden_cache"
GRID = (240, 240)
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)

SKY_TOP_KEYS = {
    "query",
    "target",
    "wcs",
    "epochs",
    "differences",
    "reference_overlays",
    "provenance",
}
SKY_QUERY_KEYS = {"ra", "dec", "size_deg", "target_id"}
WCS_KEYS = {
    "crval1",
    "crval2",
    "crpix1",
    "crpix2",
    "cdelt1",
    "cdelt2",
    "width",
    "height",
    "pixel_scale_arcsec",
    "native_pixel_scale_arcsec",
}
EPOCH_KEYS = {
    "epoch_id",
    "label",
    "collection",
    "release",
    "mjd_mean",
    "date_iso",
    "frames",
    "flag_summary",
    # Additive 1.1.0 fields; optional in the model, so old golden data
    # validates with defaults.
    "telemetry",
    "lvf_geometry",
    "candidates",
    "core_inpainted",
    "observation_range",
}
FLAG_SUMMARY_KEYS = {
    "status",
    "source_bit_set",
    "artifact_pixel_fraction",
    "active_warning_flags",
    "human_explanation",
}
PROVENANCE_KEYS = {
    "source",
    "collection",
    "release",
    "zodi_subtracted",
    "background_subtracted",
    "flux_normalization",
    "is_simulated_fallback",
    "generated_at",
    "citation",
    "analysis_id",
    "analysis_record_url",
    "processing_version", "data_access", "comparison_status", "comparison_reason",
    "discovery_status", "missing_collections", "discovery_mode",
}
FLUX_NORMALIZATION_KEYS = {
    "method",
    "scope",
    "reference_epoch",
    "applied",
    "status",
    "clamped",
    "raw_stats_location",
}
TARGET_KEYS = {
    "id",
    "name",
    "category",
    "ra_ref",
    "dec_ref",
    "ref_epoch",
    "ra_epoch2025",
    "dec_epoch2025",
    "pm_ra_mas_yr",
    "pm_dec_mas_yr",
    "recommended_bands",
    "story_headline",
    "story_body",
}


# ---------------------------------------------------------------------------
# Frozen schema
# ---------------------------------------------------------------------------
def test_contract_version_1_2_0_is_frozen() -> None:
    """1.2.0 adds the DR1/QR3 data values; no 1.0.0/1.1.0 field changed."""
    assert API_CONTRACT_VERSION == "1.7.0"


def test_sky_response_field_sets_are_exact() -> None:
    assert set(SkyResponse.model_fields) == SKY_TOP_KEYS
    assert set(SkyResponse.model_fields["query"].annotation.model_fields) == SKY_QUERY_KEYS
    assert set(SkyResponse.model_fields["wcs"].annotation.model_fields) == WCS_KEYS
    assert set(Epoch.model_fields) == EPOCH_KEYS
    assert set(FlagSummary.model_fields) == FLAG_SUMMARY_KEYS
    assert set(SkyProvenance.model_fields) == PROVENANCE_KEYS
    assert set(FluxNormalization.model_fields) == FLUX_NORMALIZATION_KEYS
    assert set(WCS.model_fields) == WCS_KEYS


def test_target_and_error_shapes() -> None:
    from models import Target, TargetListResponse

    assert set(Target.model_fields) == TARGET_KEYS
    assert set(TargetListResponse.model_fields) == {"targets"}
    assert set(HealthResponse.model_fields) == {
        "status",
        "version",
        "irsa_reachable",
        "cache_entries",
    }
    assert set(ErrorResponse.model_fields) == {"error"}
    assert set(ErrorResponse.model_fields["error"].annotation.model_fields) == {
        "code",
        "message",
        "detail",
    }


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FlagSummary(
            status="NOMINAL",
            source_bit_set=False,
            artifact_pixel_fraction=0.0,
            active_warning_flags=[],
            human_explanation="x",
            discovery_probability=0.99,
        )


def test_flag_summary_bounds_and_status_enum() -> None:
    with pytest.raises(ValidationError):
        FlagSummary(
            status="NOMINAL",
            source_bit_set=False,
            artifact_pixel_fraction=1.5,
            active_warning_flags=[],
            human_explanation="x",
        )
    with pytest.raises(ValidationError):
        FlagSummary(
            status="MAYBE",
            source_bit_set=False,
            artifact_pixel_fraction=0.0,
            active_warning_flags=[],
            human_explanation="x",
        )


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------
def test_sky_query_clamps_size_and_normalizes_bands_epochs() -> None:
    assert SkyQuery(ra=10.0, dec=20.0, size=0.9).size == pytest.approx(0.2)
    assert SkyQuery(ra=10.0, dec=20.0, size=0.001).size == pytest.approx(0.05)
    assert SkyQuery(ra=10.0, dec=20.0, bands="6,2,2").bands == "2,6"
    assert (
        SkyQuery(ra=10.0, dec=20.0, epochs="2025_E2,2025_E1").epochs
        == "2025_E1,2025_E2"
    )
    with pytest.raises(ValidationError):
        SkyQuery(ra=-1.0, dec=20.0)
    with pytest.raises(ValidationError):
        SkyQuery(ra=10.0, dec=91.0)
    with pytest.raises(ValidationError):
        SkyQuery(ra=10.0, dec=20.0, bands="all,5")
    with pytest.raises(ValidationError):
        SkyQuery(ra=10.0, dec=20.0, bands="7")
    with pytest.raises(ValidationError):
        SkyQuery(ra=10.0, dec=20.0, epochs="E1")
    with pytest.raises(ValidationError):
        SkyQuery(ra=10.0, dec=20.0, target_id="not_a_target")


def test_spectrum_channel_allows_null_flux_per_o1() -> None:
    channel = SpectrumChannel(
        detector=6,
        wavelength_um=4.682,
        bandwidth_um=0.037,
        flux_ujy=None,
        flux_err_ujy=None,
        flags=2097152,
        is_flagged_bad=False,
        clean_fraction=0.0,
        is_used_in_photometry=False,
    )
    assert channel.flux_ujy is None
    assert channel.clean_fraction == pytest.approx(0.0)
    assert channel.is_flagged_bad is False


# ---------------------------------------------------------------------------
# Golden cache (real data) against the contract
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_real_1_1_epoch(epoch, target_id: str) -> None:
    """Stage 2 golden epochs carry real telemetry/LVF data (contract 1.1.0)."""
    assert epoch.telemetry is not None, f"{target_id} {epoch.epoch_id}"
    assert epoch.telemetry.format == "float16_uint32_le_gzip"
    assert epoch.telemetry.width == GRID[0]
    assert epoch.telemetry.height == GRID[1]
    assert epoch.telemetry.byte_size > 0
    assert epoch.telemetry.url.startswith(
        f"/api/v1/assets/{target_id}/telemetry_"
    )
    assert epoch.telemetry.flux_band == (
        "thermal" if target_id == "wise_0855" else "all"
    )
    assert epoch.lvf_geometry is not None, f"{target_id} {epoch.epoch_id}"
    detectors = {item.detector for item in epoch.lvf_geometry}
    assert detectors and detectors <= set(range(1, 7))
    for item in epoch.lvf_geometry:
        assert math.isfinite(item.pa_deg)
        assert math.isfinite(item.grad_um_per_arcsec)
        assert item.grad_um_per_arcsec > 0.0
    # B9 candidate triage and display-only inpainting are not implemented.
    assert epoch.candidates is None
    assert epoch.core_inpainted is False


def _project_sky_payload(manifest: dict, *, size_deg: float = 0.2) -> dict:
    query = manifest["query"]
    return {
        "query": {
            "ra": query["ra"],
            "dec": query["dec"],
            "size_deg": size_deg,
            "target_id": manifest.get("target_id", manifest.get("query", {}).get("target_id")),
        },
        "target": manifest["target"],
        "wcs": {
            "crval1": query["ra"],
            "crval2": query["dec"],
            "crpix1": 120.5,
            "crpix2": 120.5,
            "cdelt1": -0.0008541667,
            "cdelt2": 0.0008541667,
            "width": GRID[0],
            "height": GRID[1],
            "pixel_scale_arcsec": 3.075,
            "native_pixel_scale_arcsec": 6.15,
        },
        # Existing golden/fallback manifests predate the additive 1.1.0 epoch
        # fields.  Only project keys that are actually present; SkyResponse
        # fills telemetry/lvf_geometry/candidates/core_inpainted defaults.
        "epochs": [
            {key: epoch[key] for key in EPOCH_KEYS if key in epoch}
            for epoch in manifest["epochs"]
        ],
        "differences": {
            key: pair["frames"] if isinstance(pair.get("frames"), dict) else pair
            for key, pair in manifest.get("differences", {}).items()
        },
        "reference_overlays": manifest.get("reference_overlays", {}),
        "provenance": manifest["provenance"],
    }


def _assert_frames_integrity(manifest: dict, directory: Path) -> None:
    hashes = manifest["assets"]["sha256"]
    filenames: list[str] = []
    for epoch in manifest["epochs"]:
        filenames.extend(epoch["frames"].values())
    for pair in manifest.get("differences", {}).values():
        if isinstance(pair.get("frames"), dict):
            filenames.extend(pair["frames"].values())
        else:
            filenames.extend(pair.values())
    # Real golden caches store contract asset URLs for reference overlays;
    # legacy local filenames are also supported.  Only local filenames belong
    # to the WebP frame-integrity map.
    # Reference overlay values are asset URLs or prose metadata; only local
    # filename values belong to the WebP
    # frame-integrity map.  `attribution` is prose, not an asset.
    for key, value in manifest.get("reference_overlays", {}).items():
        if key == "attribution":
            continue
        if isinstance(value, str) and not value.startswith(("/", "http://", "https://")):
            filenames.append(value)

    assert filenames, "manifest references no frames"
    assert len(set(filenames)) == len(filenames), "duplicate frame references"
    for name in filenames:
        path = directory / name
        assert path.is_file(), f"missing frame {path}"
        content = path.read_bytes()
        assert content.startswith(b"RIFF") and content[8:12] == b"WEBP"
        assert hashlib.sha256(content).hexdigest() == hashes[name]
        with Image.open(path) as image:
            assert image.size == GRID


def test_golden_cache_manifest_satisfies_sky_contract() -> None:
    manifest_path = GOLDEN_DIR / "wise_0855" / "manifest.json"
    assert manifest_path.is_file(), (
        "Run scripts/build_golden_cache.py --target wise_0855 before pytest"
    )
    manifest = _load_json(manifest_path)

    assert manifest["provenance"]["is_simulated_fallback"] is False
    assert manifest["target_id"] == "wise_0855"
    assert manifest["query"]["ra"] == pytest.approx(133.75921)
    assert manifest["query"]["dec"] == pytest.approx(-7.24216)

    response = SkyResponse.model_validate(_project_sky_payload(manifest))
    dumped = response.model_dump(mode="json")
    assert set(dumped) == SKY_TOP_KEYS
    assert set(dumped["epochs"][0]) == EPOCH_KEYS
    assert dumped["provenance"]["is_simulated_fallback"] is False
    assert dumped["provenance"]["flux_normalization"]["status"] == "ok"
    assert dumped["provenance"]["zodi_subtracted"] is True
    assert dumped["provenance"]["background_subtracted"] is True
    assert len(response.epochs) >= 2
    for epoch in response.epochs:
        # WISE 0855 is fully covered by DR1 in revision 3; it has no QR3 rows.
        assert epoch.collection == "spherex_dr1"
        assert epoch.release == "DR1"
        assert set(epoch.frames) >= {"1", "2", "3", "4", "5", "6", "all", "thermal", "flag_overlay"}
        assert epoch.flag_summary.status in {"NOMINAL", "CAUTION", "ALERT"}
        _assert_real_1_1_epoch(epoch, "wise_0855")
    assert response.differences


def test_golden_cache_frames_are_real_webp_assets() -> None:
    directory = GOLDEN_DIR / "wise_0855"
    manifest = _load_json(directory / "manifest.json")
    _assert_frames_integrity(manifest, directory)

    from scripts.build_golden_cache import verify_target

    summary = verify_target("wise_0855", golden_dir=GOLDEN_DIR)
    assert summary["frames"] == manifest["assets"]["count"]
    assert summary["normalization_status"] == "ok"


def test_all_five_golden_caches_satisfy_the_contract_and_halo_decision() -> None:
    from scripts.build_golden_cache import verify_target

    for target_id in TARGET_IDS:
        directory = GOLDEN_DIR / target_id
        manifest = _load_json(directory / "manifest.json")

        assert manifest["target_id"] == target_id
        assert manifest["provenance"]["is_simulated_fallback"] is False
        assert manifest["provenance"]["zodi_subtracted"] is True
        assert manifest["provenance"]["background_subtracted"] is True
        assert manifest["epochs"]
        assert manifest["normalization"]["status"] in {
            "ok",
            "fallback_all_pixels",
            "clamped",
            "insufficient_static_pixels",
        }

        decision = manifest["halo_decision"]
        assert decision["evaluated"] is True
        assert decision["halo_display_mode"] == bool(decision["triggered"])
        if decision["triggered"]:
            expected = decision["hard_bad_mask"] & ~decision["halo_bit"]
            assert decision["display_bad_mask"] == expected
            assert decision["photometry_exclude_mask"] & decision["halo_bit"]
            assert decision["is_flagged_bad_includes_halo"] is True
            assert decision["frames_rebuilt"] is True
        else:
            assert decision["display_bad_mask"] == decision["hard_bad_mask"]

        response = SkyResponse.model_validate(_project_sky_payload(manifest))
        assert response.provenance.is_simulated_fallback is False
        assert len(response.epochs) >= 2
        for epoch in response.epochs:
            # Stage 2 golden data carries real 1.1.0 telemetry and LVF data.
            _assert_real_1_1_epoch(epoch, target_id)
        if target_id == "r_draconis":
            # 2024_E1 has only bands 3 and 6 in the current QR2 data.
            assert response.epochs[0].epoch_id == "2024_E1"
            assert set(response.epochs[0].frames) == {
                "3",
                "6",
                "all",
                "thermal",
                "flag_overlay",
            }

        summary = verify_target(target_id, golden_dir=GOLDEN_DIR)
        assert summary["frames"] == manifest["assets"]["count"]
        assert summary["spectrum_available"] is True

        spectrum = _load_json(directory / "spectrum.json")
        assert spectrum["version"] == 2
        assert spectrum["confidence"] == "high"
        assert spectrum["provenance"]["is_simulated_fallback"] is False
        assert spectrum["epochs"]
