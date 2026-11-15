"""Spectrum validation: extraction fields, clean fraction, and golden spectra.

The ``/spectrum`` contract (``AGENTS.md`` §3.5, O1 decisions §1) requires:

* ``flags`` at the channel's extraction center (not an aperture OR);
* ``is_flagged_bad`` from ``HARD_BAD_MASK`` only;
* full-aperture and local-sky support for current measurement eligibility;
* nullable flux/error when no clean aperture pixels remain.

The additive 1.1.0 freeze adds ``photometry_method``, ``aperture_mode`` and
``aperture_radius_arcsec`` with standard-12.3 defaults.  Existing 1.0.0
golden spectra omit those optional fields and must still validate.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from core import flags as flag_policy
from models import SpectrumChannel, SpectrumEpoch, SpectrumProvenance, SpectrumResponse
from services.spherex_pipeline import ParsedCutout
from services.spectrophotometry import (
    APERTURE_RADIUS_ARCSEC,
    MOLECULAR_FEATURES,
    WAVELENGTH_CALIBRATION,
    extract_channel,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "golden_cache"
TARGET_IDS = (
    "wise_0855",
    "barnards_star",
    "eps_indi_b",
    "rw_aurigae",
    "r_draconis",
)
NATIVE_SCALE = 6.15
APERTURE_PIXELS = APERTURE_RADIUS_ARCSEC / NATIVE_SCALE

#: Fields present in the 1.0.0 golden spectra.  The 1.1.0 additions are
#: optional, so old data must contain these keys but may omit the new ones.
O1_SPECTRUM_CHANNEL_KEYS = {
    "detector",
    "wavelength_um",
    "bandwidth_um",
    "flux_ujy",
    "flux_err_ujy",
    "flags",
    "is_flagged_bad",
    "clean_fraction",
    "is_used_in_photometry",
}


def _parsed_cutout(flags: int = flag_policy.BIT_SOURCE) -> ParsedCutout:
    """A 21x21 native cutout with a uniform aperture and a clean annulus."""
    shape = (21, 21)
    yy, xx = np.indices(shape)
    distance = np.hypot(xx - 10.0, yy - 10.0)
    aperture = distance <= APERTURE_PIXELS

    image = np.zeros(shape, dtype=np.float64)
    image[aperture] = 1.0
    variance = np.full(shape, 0.01, dtype=np.float64)
    flag_array = np.zeros(shape, dtype=np.uint32)
    flag_array[10, 10] = flags

    return ParsedCutout(
        image_mjy_sr=image,
        variance_mjy_sr2=variance,
        flags=flag_array,
        warning_mask=(flag_array & flag_policy.ARTIFACT_WARNING_MASK) != 0,
        source_mask=(flag_array & flag_policy.BIT_SOURCE) != 0,
        hard_bad_mask=(flag_array & flag_policy.HARD_BAD_MASK) != 0,
        spatial_wcs=None,  # type: ignore[arg-type] - extraction does not use it
        spectral_wavelength_um=4.682,
        spectral_bandwidth_um=0.037,
        local_background_mjy_sr=0.0,
        variance_floor_mjy_sr2=0.01,
        native_pixel_scale_arcsec=NATIVE_SCALE,
        target_x=10.0,
        target_y=10.0,
        native_shape=(shape[1], shape[0]),
        native_finite_count=int(np.count_nonzero(np.isfinite(image))),
        aperture_pixel_count=int(np.count_nonzero(aperture)),
        aperture_warning_names=(),
        aperture_source_bit=True,
        halo_pixel_count=0,
        halo_aperture_pixel_count=0,
    )


def _aperture_mask(parsed: ParsedCutout) -> np.ndarray:
    yy, xx = np.indices(parsed.flags.shape)
    return np.hypot(xx - parsed.target_x, yy - parsed.target_y) <= APERTURE_PIXELS


@pytest.mark.parametrize("changes,reason", [
    ({"spectral_wavelength_um": None}, "MISSING_SPECTRAL_COORDINATES"),
    ({"spectral_bandwidth_um": None}, "MISSING_SPECTRAL_COORDINATES"),
    ({"spectral_wavelength_um": float("nan")}, "INVALID_WAVELENGTH"),
    ({"spectral_wavelength_um": 0.0}, "INVALID_WAVELENGTH"),
    ({"spectral_bandwidth_um": float("inf")}, "INVALID_BANDWIDTH"),
    ({"spectral_bandwidth_um": -0.1}, "INVALID_BANDWIDTH"),
    ({"target_x": -2.0}, "EXTRACTION_CENTRE_OUTSIDE_NATIVE_IMAGE"),
    ({"target_x": 10.5, "target_y": 10.5, "native_pixel_scale_arcsec": 100.0}, "NO_NATIVE_APERTURE_PIXELS"),
])
def test_omitted_channels_retain_reason_without_fabricating_measurement(changes, reason):
    parsed = replace(_parsed_cutout(), **changes)
    diagnostics = {}
    assert extract_channel(parsed, 6, diagnostics=diagnostics) is None
    assert diagnostics == {"omission_reason": reason}
    assert extract_channel(parsed, 6) is None


def test_extract_channel_happy_path() -> None:
    parsed = _parsed_cutout()
    channel = extract_channel(parsed, 6)
    assert channel is not None
    assert channel["detector"] == 6
    assert channel["wavelength_um"] == pytest.approx(4.682)
    assert channel["bandwidth_um"] == pytest.approx(0.037)
    assert channel["flags"] == flag_policy.BIT_SOURCE
    assert channel["is_flagged_bad"] is False
    assert channel["clean_fraction"] == pytest.approx(1.0)
    assert channel["is_used_in_photometry"] is True
    assert channel["flux_ujy"] is not None and np.isfinite(channel["flux_ujy"])
    assert channel["flux_err_ujy"] is not None and np.isfinite(channel["flux_err_ujy"])
    assert channel["flux_ujy"] > 0
    assert channel["flux_err_ujy"] > 0


def test_warning_center_is_not_flagged_bad() -> None:
    parsed = _parsed_cutout(flags=flag_policy.FLAG_VALUES["DICHROIC"])
    channel = extract_channel(parsed, 3)
    assert channel is not None
    assert channel["flags"] == flag_policy.FLAG_VALUES["DICHROIC"]
    # DICHROIC is a warning, not hard-bad.
    assert channel["is_flagged_bad"] is False
    assert 0.5 <= channel["clean_fraction"] < 1.0
    assert channel["is_used_in_photometry"] is False
    assert channel["flux_ujy"] is not None  # Retained exploratory partial sum.
    assert "PARTIAL_CLEAN_APERTURE" in channel["measurement_reasons"]


def test_hard_bad_center_is_flagged_bad() -> None:
    parsed = _parsed_cutout(flags=flag_policy.FLAG_VALUES["SUR_ERROR"])
    channel = extract_channel(parsed, 2)
    assert channel is not None
    assert channel["flags"] == flag_policy.FLAG_VALUES["SUR_ERROR"]
    assert channel["is_flagged_bad"] is True
    assert channel["is_used_in_photometry"] is False
    assert channel["clean_fraction"] < 1.0


def test_full_aperture_without_local_sky_is_exploratory() -> None:
    parsed = _parsed_cutout()
    yy, xx = np.indices(parsed.flags.shape)
    distance = np.hypot(xx - parsed.target_x, yy - parsed.target_y)
    flags = parsed.flags.copy()
    flags[(distance >= 3) & (distance <= 5)] |= flag_policy.BIT_SOURCE
    diagnostics = {}
    channel = extract_channel(replace(parsed, flags=flags), 6, diagnostics=diagnostics)
    assert channel["clean_fraction"] == 1.0
    assert channel["flux_ujy"] is not None
    assert channel["is_used_in_photometry"] is False
    assert "FIELD_BACKGROUND_FALLBACK" in channel["measurement_reasons"]
    assert diagnostics["annulus_evaluated"] is True
    assert diagnostics["annulus_clean_pixels"] == 0


def test_clean_but_clipped_aperture_is_not_a_full_measurement() -> None:
    parsed = replace(_parsed_cutout(), target_x=0.0)
    channel = extract_channel(parsed, 6)
    assert channel["clean_fraction"] == 1.0
    assert channel["flux_ujy"] is not None
    assert channel["is_used_in_photometry"] is False
    assert "APERTURE_OUTSIDE_NATIVE_IMAGE" in channel["measurement_reasons"]


def test_flags_are_the_extraction_center_not_an_aperture_or() -> None:
    parsed = _parsed_cutout(flags=flag_policy.BIT_SOURCE)
    aperture = _aperture_mask(parsed)
    # Flag one aperture row (not the center row) hard-bad.
    row = np.indices(parsed.flags.shape)[0]
    hard_elsewhere = aperture & (row == 9)
    flag_array = np.where(
        hard_elsewhere, flag_policy.FLAG_VALUES["SUR_ERROR"], parsed.flags
    ).astype(np.uint32)
    parsed = replace(
        parsed,
        flags=flag_array,
        hard_bad_mask=(flag_array & flag_policy.HARD_BAD_MASK) != 0,
    )
    channel = extract_channel(parsed, 1)
    assert channel is not None
    # The center is clean SOURCE; hard-bad pixels elsewhere in the aperture
    # must not turn the channel bad or change the reported center flags.
    assert channel["flags"] == flag_policy.BIT_SOURCE
    assert channel["is_flagged_bad"] is False
    assert 0.0 < channel["clean_fraction"] < 1.0


def test_no_clean_aperture_pixels_yields_null_flux() -> None:
    parsed = _parsed_cutout(flags=flag_policy.FLAG_VALUES["DICHROIC"])
    aperture = _aperture_mask(parsed)
    flag_array = parsed.flags.copy()
    flag_array[aperture] = flag_policy.FLAG_VALUES["DICHROIC"]
    parsed = replace(
        parsed,
        flags=flag_array,
        warning_mask=(flag_array & flag_policy.ARTIFACT_WARNING_MASK) != 0,
        hard_bad_mask=(flag_array & flag_policy.HARD_BAD_MASK) != 0,
    )
    channel = extract_channel(parsed, 4)
    assert channel is not None
    assert channel["clean_fraction"] == pytest.approx(0.0)
    assert channel["flux_ujy"] is None
    assert channel["flux_err_ujy"] is None
    assert channel["is_used_in_photometry"] is False
    assert channel["is_flagged_bad"] is False  # center is DICHROIC, not hard


def test_clean_fraction_below_threshold_is_not_used() -> None:
    parsed = _parsed_cutout()
    aperture = _aperture_mask(parsed)
    flag_array = parsed.flags.copy()
    # Flag all but six aperture pixels as DICHROIC -> clean_fraction < 0.5.
    flagged = np.argwhere(aperture)[6:]
    for y, x in flagged:
        flag_array[y, x] = flag_policy.FLAG_VALUES["DICHROIC"]
    parsed = replace(
        parsed,
        flags=flag_array,
        warning_mask=(flag_array & flag_policy.ARTIFACT_WARNING_MASK) != 0,
        hard_bad_mask=(flag_array & flag_policy.HARD_BAD_MASK) != 0,
    )
    channel = extract_channel(parsed, 5)
    assert channel is not None
    assert 0.0 < channel["clean_fraction"] < 0.5
    assert channel["is_used_in_photometry"] is False
    assert channel["is_flagged_bad"] is False
    assert channel["flux_ujy"] is not None


def test_missing_wavelength_or_center_outside_returns_none() -> None:
    parsed = _parsed_cutout()
    assert extract_channel(replace(parsed, spectral_wavelength_um=None), 1) is None
    assert extract_channel(replace(parsed, spectral_bandwidth_um=None), 1) is None
    assert extract_channel(replace(parsed, target_x=-1.0), 1) is None
    assert extract_channel(replace(parsed, target_y=99.0), 1) is None


def test_spectrum_channel_fields_are_the_1_1_contract() -> None:
    assert set(SpectrumChannel.model_fields) == {
        "detector",
        "wavelength_um",
        "bandwidth_um",
        "flux_ujy",
        "flux_err_ujy",
        "flags",
        "is_flagged_bad",
        "clean_fraction",
        "is_used_in_photometry",
        # Additive 1.1.0 photometry/aperture provenance.
        "photometry_method",
        "aperture_mode",
        "aperture_radius_arcsec",
        "input_id",
        "extraction_ra",
        "extraction_dec",
        "measurement_reasons",
    }
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
    assert channel.clean_fraction == 0.0
    assert channel.photometry_method == "aperture_12.3"
    assert channel.aperture_mode == "standard_12.3"
    assert channel.aperture_radius_arcsec == 12.3


# ---------------------------------------------------------------------------
# Golden spectra (B3 cache copied into golden_cache/<target>/spectrum.json)
# ---------------------------------------------------------------------------
def _load_spectrum(target_id: str) -> dict:
    path = GOLDEN_DIR / target_id / "spectrum.json"
    assert path.is_file(), f"missing {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_golden_spectra_are_real_and_internally_consistent() -> None:
    for target_id in TARGET_IDS:
        payload = _load_spectrum(target_id)
        assert payload["version"] == 2
        assert payload["confidence"] == "high"
        provenance = payload["provenance"]
        assert provenance["is_simulated_fallback"] is False
        assert provenance["zodi_subtracted"] is True
        assert provenance["background_subtracted"] is True
        epochs = payload["epochs"]
        assert len(epochs) >= 3
        for epoch in epochs:
            assert epoch["collection"] in {
                "spherex_dr1",
                "spherex_qr2",
                "spherex_qr3",
                "mixed",
            }
            assert epoch["release"] in {"DR1", "DR1+QR3", "QR2", "QR3", "QR2+QR3"}
            assert epoch["channels"], f"{target_id} {epoch['epoch_id']} has no channels"
            for channel in epoch["channels"]:
                # 1.0.0 golden spectra contain every O1 field and may omit the
                # optional 1.1.0 additions; unknown fields are still rejected.
                assert O1_SPECTRUM_CHANNEL_KEYS <= set(channel) <= set(
                    SpectrumChannel.model_fields
                )
                model = SpectrumChannel(**channel)
                assert model.photometry_method == "aperture_12.3"
                assert model.aperture_mode == "standard_12.3"
                assert model.aperture_radius_arcsec == 12.3
                assert 1 <= channel["detector"] <= 6
                assert channel["wavelength_um"] > 0
                assert channel["bandwidth_um"] > 0
                assert 0.0 <= channel["clean_fraction"] <= 1.0
                hard_bad = bool(channel["flags"] & flag_policy.HARD_BAD_MASK)
                assert channel["is_flagged_bad"] is hard_bad
                expected_used = (
                    channel["clean_fraction"] >= 0.5 and not channel["is_flagged_bad"]
                )
                assert channel["is_used_in_photometry"] is expected_used
                if channel["flux_ujy"] is None:
                    assert channel["flux_err_ujy"] is None
                    assert channel["clean_fraction"] == pytest.approx(0.0)
                else:
                    assert np.isfinite(channel["flux_ujy"])
                    assert channel["flux_err_ujy"] is not None
                    assert np.isfinite(channel["flux_err_ujy"])
                    assert channel["flux_err_ujy"] >= 0


def test_golden_spectrum_satisfies_response_contract() -> None:
    for target_id in TARGET_IDS:
        payload = _load_spectrum(target_id)
        response = SpectrumResponse(
            target_id=target_id,
            ra=payload["query"]["ra"],
            dec=payload["query"]["dec"],
            aperture_radius_arcsec=APERTURE_RADIUS_ARCSEC,
            wavelength_calibration=WAVELENGTH_CALIBRATION,
            confidence="high",
            epochs=[
                SpectrumEpoch(
                    epoch_id=epoch["epoch_id"],
                    label=epoch["label"],
                    collection=epoch["collection"],
                    release=epoch["release"],
                    channels=[SpectrumChannel(**channel) for channel in epoch["channels"]],
                )
                for epoch in payload["epochs"]
            ],
            molecular_features=MOLECULAR_FEATURES,
            provenance=SpectrumProvenance(
                source=payload["provenance"]["source"],
                collection=payload["provenance"]["collection"],
                release=payload["provenance"]["release"],
                zodi_subtracted=payload["provenance"]["zodi_subtracted"],
                background_subtracted=payload["provenance"]["background_subtracted"],
                is_simulated_fallback=payload["provenance"]["is_simulated_fallback"],
                generated_at=payload["generated_at"],
                citation=payload["provenance"]["citation"],
            ),
        )
        assert response.target_id == target_id
        assert response.confidence.value == "high"
        assert len(response.epochs) >= 3
        assert len(response.molecular_features) == len(MOLECULAR_FEATURES)


def test_golden_spectra_cover_the_sky_epochs() -> None:
    for target_id in TARGET_IDS:
        manifest = json.loads(
            (GOLDEN_DIR / target_id / "manifest.json").read_text(encoding="utf-8")
        )
        spectrum = _load_spectrum(target_id)
        sky_epochs = {epoch["epoch_id"] for epoch in manifest["epochs"]}
        spectrum_epochs = {epoch["epoch_id"] for epoch in spectrum["epochs"]}
        assert spectrum_epochs <= sky_epochs
        assert spectrum_epochs == sky_epochs, (
            f"{target_id}: spectrum is missing {sorted(sky_epochs - spectrum_epochs)}"
        )
