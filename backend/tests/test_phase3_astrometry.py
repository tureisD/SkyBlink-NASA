"""Isolated mathematical centroid/summary tests, never observation products.

Generated Gaussian arrays and catalog coordinates exercise algorithm behavior;
the actual audit only downloads real exposures and real Gaia rows.
"""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from phase3_astrometry import detect, fit_centroid, propagate, summary


def gaussian():
    yy, xx = np.indices((35, 35), dtype=float)
    image = 2 + 100*np.exp(-.5*(((xx-17.32)/.9)**2 + ((yy-16.71)/1.1)**2))
    return image, np.ones_like(image), np.zeros_like(image, dtype=bool)


def test_centroid_is_measured_subpixel_from_image_peak():
    image, variance, bad = gaussian()
    peaks = detect(image, variance, bad, 6.15)
    assert len(peaks) == 1
    assert peaks[0]["x"] == pytest.approx(17.32, abs=1e-5)
    assert peaks[0]["y"] == pytest.approx(16.71, abs=1e-5)


def test_artifact_in_core_rejects_entire_star_not_shifted_centroid():
    image, variance, bad = gaussian()
    bad[17, 17] = True
    assert fit_centroid(image, variance, bad, 17, 17, 6.15) is None


def test_edges_and_low_signal_do_not_become_astrometric_references():
    image, variance, bad = gaussian()
    assert fit_centroid(image, variance, bad, 1, 1, 6.15) is None
    assert detect(np.full_like(image, 2), variance, bad, 6.15) == []


def test_robust_acceptance_keeps_systematic_offset_and_all_outliers():
    rows = [{"output_dra_cosdec_arcsec": 2.0, "output_ddec_arcsec": 0.0} for _ in range(4)]
    result = summary(rows, "output")
    assert result["status"] == "fail"
    assert result["robust_rms_including_bias_arcsec"] == pytest.approx(2)
    assert result["above_threshold"] == 4
    rows.append({"output_dra_cosdec_arcsec": 15, "output_ddec_arcsec": 0})
    result = summary(rows, "output")
    assert result["count"] == 5
    assert result["maximum_residual_arcsec"] == 15
    assert summary(rows[:2], "output")["status"] == "insufficient_stars"


def test_gaia_pmra_is_cosdec_motion_and_missing_pm_is_excluded():
    rows = [
        {"ra": 30., "dec": 60., "pmra": 1000., "pmdec": 0.},
        {"ra": 30., "dec": 60., "pmra": None, "pmdec": 0.},
    ]
    from astropy.time import Time
    moved, valid, missing = propagate(rows, Time(2026., format="jyear", scale="tcb").mjd, "tcb")
    assert len(valid) == 1 and missing == 1
    assert (moved[0].ra.deg - 30.)*3600 == pytest.approx(20., abs=.01)
