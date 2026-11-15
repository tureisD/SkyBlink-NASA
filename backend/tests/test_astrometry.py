"""Astrometry tests: contract coordinates, proper motion, and WCS.

The stored 2025.8 values are the frozen query centers (LAW 5).  The tests
recompute them with ``SkyCoord.apply_space_motion`` (the production path),
check the motion direction against the catalog proper motions, and validate the
240 x 240 north-up 3.075"/pixel output grid used by every golden frame.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

from core.targets import (
    EPOCH_2025_8,
    TARGETS,
    angular_separation_arcsec,
    get_target,
    match_target,
    propagated_coordinates,
)
from services.spherex_pipeline import (
    CDELT_DEG,
    CRPIX,
    GRID_HEIGHT,
    GRID_WIDTH,
    NATIVE_PIXEL_SCALE_ARCSEC,
    PIXEL_SCALE_ARCSEC,
    output_wcs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "golden_cache"

# ROADMAP.md Appendix A (2025.8 propagated positions).
EXPECTED_2025_8 = {
    "wise_0855": (133.75921, -7.24216),
    "barnards_star": (269.4463, 4.7676),
    "eps_indi_b": (331.0962, -56.8005),
    "rw_aurigae": (76.9561, 30.4011),
    "r_draconis": (248.1674, 66.7548),
}


def test_stored_2025_8_values_match_roadmap_appendix() -> None:
    assert {target.id for target in TARGETS} == set(EXPECTED_2025_8)
    for target in TARGETS:
        expected_ra, expected_dec = EXPECTED_2025_8[target.id]
        assert target.ra_epoch2025 == pytest.approx(expected_ra, abs=1e-5)
        assert target.dec_epoch2025 == pytest.approx(expected_dec, abs=1e-5)


def test_propagated_2025_8_matches_stored_contract_values() -> None:
    for target in TARGETS:
        propagated = propagated_coordinates(target, EPOCH_2025_8)
        separation = angular_separation_arcsec(
            float(propagated.ra.deg),
            float(propagated.dec.deg),
            target.ra_epoch2025,
            target.dec_epoch2025,
        )
        # The contract stores rounded values; the pre-event audit found
        # <0.3" residuals for all five targets.
        assert separation < 0.5, f"{target.id}: {separation:.3f} arcsec"


def test_proper_motion_direction_matches_catalog() -> None:
    for target in TARGETS:
        reference = SkyCoord(
            ra=target.ra_ref * u.deg,
            dec=target.dec_ref * u.deg,
            frame="icrs",
        )
        propagated = propagated_coordinates(target, EPOCH_2025_8)
        delta_ra_cosdec = (
            (propagated.ra - reference.ra)
            * np.cos(reference.dec.to_value(u.rad))
        ).to_value(u.arcsec)
        delta_dec = (propagated.dec - reference.dec).to_value(u.arcsec)

        assert np.sign(delta_ra_cosdec) == np.sign(target.pm_ra_mas_yr), (
            f"{target.id}: RA* motion {delta_ra_cosdec:+.2f}\" does not match "
            f"pm_ra* {target.pm_ra_mas_yr:+.1f} mas/yr"
        )
        assert np.sign(delta_dec) == np.sign(target.pm_dec_mas_yr), (
            f"{target.id}: Dec motion {delta_dec:+.2f}\" does not match "
            f"pm_dec {target.pm_dec_mas_yr:+.1f} mas/yr"
        )
        # The total motion must equal PM × Δt to within the rounded epoch.
        elapsed_years = EPOCH_2025_8 - (
            2010.0 if target.ref_epoch == "2010.0" else 2000.0
        )
        expected = np.hypot(target.pm_ra_mas_yr, target.pm_dec_mas_yr) * elapsed_years / 1000.0
        total = np.hypot(delta_ra_cosdec, delta_dec)
        assert total == pytest.approx(expected, rel=0.02), (
            f"{target.id}: total motion {total:.2f}\" vs expected {expected:.2f}\""
        )


def test_wise_0855_moves_west_and_north_since_2010() -> None:
    target = get_target("wise_0855")
    assert target is not None
    reference = SkyCoord(
        ra=target.ra_ref * u.deg, dec=target.dec_ref * u.deg, frame="icrs"
    )
    propagated = propagated_coordinates(target)
    delta_ra_cosdec = (
        (propagated.ra - reference.ra) * np.cos(reference.dec.to_value(u.rad))
    ).to_value(u.arcsec)
    delta_dec = (propagated.dec - reference.dec).to_value(u.arcsec)
    # μ_α cos δ = -8118 mas/yr, μ_δ = +680 mas/yr.
    assert delta_ra_cosdec < 0
    assert delta_dec > 0
    assert np.hypot(delta_ra_cosdec, delta_dec) > 120.0  # ~15.8 yr × 8.1"/yr


def test_output_wcs_is_the_contract_grid() -> None:
    ra, dec = 133.75921, -7.24216
    wcs = output_wcs(ra, dec)
    assert [str(value) for value in wcs.wcs.ctype] == ["RA---TAN", "DEC--TAN"]
    assert [str(value) for value in wcs.wcs.cunit] == ["deg", "deg"]
    assert wcs.wcs.crval == pytest.approx([ra, dec])
    assert wcs.wcs.crpix == pytest.approx([CRPIX, CRPIX])
    assert wcs.wcs.cdelt == pytest.approx([-CDELT_DEG, CDELT_DEG])
    assert (GRID_WIDTH, GRID_HEIGHT) == (240, 240)
    assert CRPIX == pytest.approx(120.5)
    assert CDELT_DEG == pytest.approx(3.075 / 3600.0)
    assert PIXEL_SCALE_ARCSEC == pytest.approx(3.075)
    assert NATIVE_PIXEL_SCALE_ARCSEC == pytest.approx(6.15)


def test_output_wcs_round_trip_and_orientation() -> None:
    ra, dec = 133.75921, -7.24216
    wcs = output_wcs(ra, dec)
    center = wcs.pixel_to_world(CRPIX - 1.0, CRPIX - 1.0)
    assert center.separation(
        SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
    ).to_value(u.arcsec) < 1e-6

    # East (higher RA) must move to lower x because cdelt1 is negative.
    east = SkyCoord(
        ra=(ra + 10.0 / 3600.0 / np.cos(np.deg2rad(dec))) * u.deg,
        dec=dec * u.deg,
        frame="icrs",
    )
    x_east, y_east = wcs.world_to_pixel(east)
    assert x_east < CRPIX - 1.0
    assert y_east == pytest.approx(CRPIX - 1.0, abs=1e-4)

    # North (higher Dec) must move to higher y because cdelt2 is positive.
    north = SkyCoord(ra=ra * u.deg, dec=(dec + 10.0 / 3600.0) * u.deg, frame="icrs")
    x_north, y_north = wcs.world_to_pixel(north)
    assert y_north > CRPIX - 1.0
    assert x_north == pytest.approx(CRPIX - 1.0, abs=1e-4)

    # One native 6.15" pixel spans exactly two output pixels.
    start = wcs.pixel_to_world(CRPIX - 1.0, CRPIX - 1.0)
    two_pixels = wcs.pixel_to_world(CRPIX + 1.0, CRPIX - 1.0)
    assert start.separation(two_pixels).to_value(u.arcsec) == pytest.approx(
        2.0 * PIXEL_SCALE_ARCSEC, rel=0.01
    )
    assert 2.0 * PIXEL_SCALE_ARCSEC == pytest.approx(NATIVE_PIXEL_SCALE_ARCSEC)


def test_match_target_uses_the_2025_8_position_and_1_arcsec_tolerance() -> None:
    target = get_target("wise_0855")
    assert target is not None
    exact = SkyCoord(
        ra=target.ra_epoch2025 * u.deg, dec=target.dec_epoch2025 * u.deg, frame="icrs"
    )
    assert match_target(exact.ra.deg, exact.dec.deg) is target

    inside = exact.directional_offset_by(45 * u.deg, 0.9 * u.arcsec)
    assert match_target(inside.ra.deg, inside.dec.deg) is target

    outside = exact.directional_offset_by(45 * u.deg, 2.0 * u.arcsec)
    assert match_target(outside.ra.deg, outside.dec.deg) is None


def test_angular_separation_helper() -> None:
    assert angular_separation_arcsec(10.0, 20.0, 10.0, 20.0) == pytest.approx(0.0)
    assert angular_separation_arcsec(10.0, 20.0, 10.0, 20.0 + 1.0 / 3600.0) == pytest.approx(
        1.0, abs=1e-3
    )


def test_golden_manifests_use_the_contract_coordinates() -> None:
    for target in TARGETS:
        manifest_path = GOLDEN_DIR / target.id / "manifest.json"
        assert manifest_path.is_file(), f"missing {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["query"]["ra"] == pytest.approx(target.ra_epoch2025, abs=1e-6)
        assert manifest["query"]["dec"] == pytest.approx(target.dec_epoch2025, abs=1e-6)
        assert manifest["query"]["cutout_size_deg"] == pytest.approx(0.2)
        assert manifest["pipeline"]["cutout_size_deg"] == pytest.approx(0.2)
