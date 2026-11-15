"""Bitmask policy tests (Table 16; ``AGENTS.md`` §4.2).

The regression this file exists to prevent: using *any* non-zero flag as a
bad-pixel mask erases every cataloged source, including the demo targets.
Only ``HARD_BAD_MASK`` may set a pixel to ``NaN``; ``BIT_SOURCE`` is excluded
only from the local-background estimate.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from core import flags

# ---------------------------------------------------------------------------
# Table 16 — Image pixel flags used in spectral images at Level 2
# ---------------------------------------------------------------------------
EXPECTED_FLAG_BITS = {
    "TRANSIENT": 0,
    "OVERFLOW": 1,
    "SUR_ERROR": 2,
    "NONFUNC": 6,
    "DICHROIC": 7,
    "MISSING_DATA": 9,
    "HOT": 10,
    "COLD": 11,
    "FULLSAMPLE": 12,
    "PHANMISS": 14,
    "NONLINEAR": 15,
    "PERSIST": 17,
    "OUTLIER": 19,
    "CROSSTALK": 20,
    "SOURCE": 21,
    "GHOST": 22,
    "GHOST_FPA": 23,
    "GHOST_EXT": 24,
    "STREAK": 25,
    "BLOOM": 26,
    "SNOWBALL": 27,
    "HALO": 28,
    "SATELLITE_HALO": 29,
}

HARD_BITS = (2, 6, 9, 10, 11, 14, 15, 26, 27, 28, 29)
WARNING_BITS = (0, 1, 7, 17, 19, 20, 22, 23, 24, 25)


def _mask(bits: tuple[int, ...]) -> int:
    value = 0
    for bit in bits:
        value |= 1 << bit
    return value


def test_table_16_names_and_bits_are_exact() -> None:
    assert flags.FLAG_BITS == EXPECTED_FLAG_BITS
    for name, bit in EXPECTED_FLAG_BITS.items():
        assert flags.FLAG_VALUES[name] == 1 << bit
    assert len(flags.FLAG_BITS) == 23


def test_hard_and_warning_masks_match_table_16() -> None:
    assert flags.HARD_BAD_MASK == _mask(HARD_BITS)
    assert flags.ARTIFACT_WARNING_MASK == _mask(WARNING_BITS)
    # Bit 23 GHOST_FPA is currently unused but must be a *warning* bit.
    assert flags.FLAG_VALUES["GHOST_FPA"] == 8388608
    assert flags.ARTIFACT_WARNING_MASK & (1 << 23)
    assert not flags.HARD_BAD_MASK & (1 << 23)


def test_source_and_fullsample_are_never_masked() -> None:
    assert flags.BIT_SOURCE == 2097152
    assert flags.BIT_FULLSAMPLE == 4096
    assert flags.NEVER_MASK == flags.BIT_SOURCE | flags.BIT_FULLSAMPLE

    for mask in (
        flags.HARD_BAD_MASK,
        flags.ARTIFACT_WARNING_MASK,
        flags.PHOTOMETRY_EXCLUDE_MASK,
        flags.DISPLAY_BAD_MASK,
    ):
        assert mask & flags.BIT_SOURCE == 0
    assert flags.BACKGROUND_EXCLUDE_MASK & flags.BIT_SOURCE  # only here


def test_masks_are_disjoint_and_consistent() -> None:
    assert flags.HARD_BAD_MASK & flags.ARTIFACT_WARNING_MASK == 0
    assert flags.PHOTOMETRY_EXCLUDE_MASK == (
        flags.HARD_BAD_MASK | flags.ARTIFACT_WARNING_MASK
    )
    assert flags.BACKGROUND_EXCLUDE_MASK == (
        flags.HARD_BAD_MASK | flags.ARTIFACT_WARNING_MASK | flags.BIT_SOURCE
    )
    # O1 decision §9: HALO stays hard for display by default.
    assert flags.DISPLAY_BAD_MASK == flags.HARD_BAD_MASK


def test_predicates_keep_source_and_fullsample_clean() -> None:
    source_only = flags.BIT_SOURCE
    assert flags.is_hard_bad(source_only) is False
    assert flags.is_warning(source_only) is False
    assert flags.is_photometry_clean(source_only) is True
    assert flags.is_photometry_clean(flags.BIT_FULLSAMPLE) is True
    assert flags.is_hard_bad(flags.BIT_SOURCE | flags.FLAG_VALUES["SUR_ERROR"])
    assert flags.is_warning(flags.BIT_SOURCE | flags.FLAG_VALUES["TRANSIENT"])
    assert flags.is_photometry_clean(flags.FLAG_VALUES["DICHROIC"]) is False
    assert flags.is_hard_bad(flags.FLAG_VALUES["HALO"]) is True


def test_names_for_and_union_names() -> None:
    value = (
        flags.FLAG_VALUES["TRANSIENT"]
        | flags.FLAG_VALUES["SOURCE"]
        | flags.FLAG_VALUES["HALO"]
    )
    assert flags.names_for(value) == ["TRANSIENT", "SOURCE", "HALO"]
    assert flags.names_for(flags.BIT_FULLSAMPLE) == ["FULLSAMPLE"]
    assert flags.union_names(
        [flags.FLAG_VALUES["TRANSIENT"], flags.FLAG_VALUES["DICHROIC"]]
    ) == ["TRANSIENT", "DICHROIC"]
    assert flags.describe_mask(flags.BIT_SOURCE) == "SOURCE"
    assert flags.describe_mask(0) == "none"


def test_flag_status_aggregation() -> None:
    assert flags.flag_status([], 0.001) == "NOMINAL"
    assert flags.flag_status(["TRANSIENT"], 0.0) == "ALERT"
    assert flags.flag_status(["GHOST_FPA"], 0.0) == "ALERT"
    assert flags.flag_status(["DICHROIC"], 0.0) == "CAUTION"
    assert flags.flag_status(["OUTLIER"], 0.0) == "CAUTION"
    assert flags.flag_status([], 0.0101) == "CAUTION"
    assert flags.flag_status([], 0.01) == "NOMINAL"
    # HALO alone never escalates to ALERT; in display-only mode it is CAUTION.
    assert flags.flag_status(["HALO"], 0.0) == "NOMINAL"
    assert flags.flag_status(["HALO"], 0.0, halo_display_mode=True) == "CAUTION"


# ---------------------------------------------------------------------------
# Pipeline-level check on a synthetic MEF: BIT_SOURCE survives preparation
# ---------------------------------------------------------------------------
def _synthetic_cutout() -> bytes:
    """A tiny Level-2-shaped MEF with a source, a warning, and hard defects."""
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.cunit = ["deg", "deg"]
    wcs.wcs.crval = [10.0, 20.0]
    wcs.wcs.crpix = [2.0, 2.0]
    wcs.wcs.cdelt = [-0.0017, 0.0017]
    wcs.wcs.set()

    image = np.zeros((4, 4), dtype=np.float32)
    image[0, 0] = 0.5  # catalog source
    image[0, 1] = 0.5  # source that is also hard-bad
    zodi = np.zeros((4, 4), dtype=np.float32)

    flag_array = np.zeros((4, 4), dtype=np.int32)
    flag_array[0, 0] = flags.BIT_SOURCE
    flag_array[0, 1] = flags.BIT_SOURCE | flags.FLAG_VALUES["SUR_ERROR"]
    flag_array[1, 0] = flags.FLAG_VALUES["DICHROIC"]
    flag_array[1, 1] = flags.HARD_BAD_MASK

    variance = np.ones((4, 4), dtype=np.float32)
    hdul = fits.HDUList(
        [
            fits.PrimaryHDU(),
            fits.ImageHDU(data=image, header=wcs.to_header(), name="IMAGE"),
            fits.ImageHDU(data=flag_array, name="FLAGS"),
            fits.ImageHDU(data=variance, name="VARIANCE"),
            fits.ImageHDU(data=zodi, name="ZODI"),
            fits.ImageHDU(data=np.zeros((1, 1), dtype=np.float32), name="PSF"),
        ]
    )
    buffer = io.BytesIO()
    hdul.writeto(buffer)
    return buffer.getvalue()


def test_pipeline_preserves_bit_source_and_masks_only_hard_bad() -> None:
    from services.spherex_pipeline import parse_cutout

    # Target coordinate far outside the tiny cutout: the spatial/spectral WCS
    # block is skipped, but image preparation and flag handling still run.
    parsed = parse_cutout(_synthetic_cutout(), target_ra=0.0, target_dec=0.0)

    # BIT_SOURCE pixel is preserved in the prepared image.
    assert np.isfinite(parsed.image_mjy_sr[0, 0])
    assert parsed.image_mjy_sr[0, 0] == pytest.approx(0.5)
    assert parsed.source_mask[0, 0]
    assert not parsed.hard_bad_mask[0, 0]
    assert not parsed.warning_mask[0, 0]

    # Only HARD_BAD_MASK pixels become NaN.
    assert np.isnan(parsed.image_mjy_sr[0, 1])  # SOURCE | SUR_ERROR
    assert np.isnan(parsed.image_mjy_sr[1, 1])  # hard-bad only
    # A warning-only pixel survives in the displayed image.
    assert np.isfinite(parsed.image_mjy_sr[1, 0])
    assert parsed.warning_mask[1, 0]
    assert not parsed.hard_bad_mask[1, 0]

    # The source is excluded from the background estimate, not from the image.
    assert parsed.local_background_mjy_sr == pytest.approx(0.0)

    # Document the failure mode: a blanket "any flag" mask would drop the source.
    naive_mask = parsed.flags.astype(bool)
    assert bool(naive_mask[0, 0]) is True
    assert np.isfinite(parsed.image_mjy_sr[0, 0])
