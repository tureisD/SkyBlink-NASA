"""Isolated mathematical/protocol tests, not generated observation products.

Constant test intensities, controlled flags and seeded noise validate numerical
integration/error handling. Real-input acceptance remains a separate report.
"""
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from phase4_science_validation import measure, weights, stability, table_rows, read_json, preserve_result
from core import flags as policy


def input_array(x=10.37, y=10.21):
    yy, xx = np.indices((21,21))
    return SimpleNamespace(image_mjy_sr=np.where(np.hypot(xx-x,yy-y)<2.8,10.,0.),
                           variance_mjy_sr2=np.full((21,21),4.), flags=np.zeros((21,21),dtype=np.uint32),
                           target_x=x,target_y=y,native_pixel_scale_arcsec=6.15,
                           background_metadata={"subtracted": True})


def test_fractional_area_tracks_geometric_aperture_across_pixel_phase():
    # Uniform brightness is analytically area*pi*r², regardless of pixel phase.
    areas = [weights((21,21),10+offset,10.21,2,"fractional").sum() for offset in (0,.2,.4,.6,.8)]
    assert np.max(np.abs(np.asarray(areas)-4*np.pi)) < .2
    center_areas = [weights((21,21),10+offset,10.21,2,"center").sum() for offset in (0,.2,.4,.6,.8)]
    assert np.ptp(center_areas) > np.ptp(areas)


def test_fractional_uncertainty_matches_independent_noise_trials():
    parsed = input_array()
    result = measure(parsed,"fractional")
    weight = weights((21,21),parsed.target_x,parsed.target_y,2,"fractional")
    positive_weights = weight[weight>0]
    rng = np.random.default_rng(20261114)
    # Independent repeated Gaussian pixel and annulus measurements, not formula restatement.
    draws = 30000
    aperture_noise = rng.normal(0,2,(draws,len(positive_weights))) @ positive_weights
    estimated_sky = np.median(rng.normal(0,2,(draws,result["annulus_pixels"])),axis=1)
    empirical_sd = np.std(aperture_noise-positive_weights.sum()*estimated_sky)
    unit = 1e12*(6.15*np.pi/(180*3600))**2
    assert result["error_ujy"]/unit == pytest.approx(empirical_sd,rel=.035)


def test_missing_annulus_is_insufficient_and_never_global_fallback_for_holdout():
    parsed = input_array()
    yy,xx = np.indices(parsed.flags.shape)
    parsed.flags[np.hypot(xx-parsed.target_x,yy-parsed.target_y)>=3] = policy.BIT_SOURCE
    result = measure(parsed,"fractional")
    assert result["reason"] == "insufficient_clean_annulus"
    assert result["flux_ujy"] is None


def test_fractional_boundary_warning_disqualifies_full_aperture():
    parsed = input_array()
    weighted = weights(parsed.flags.shape,parsed.target_x,parsed.target_y,2,"fractional")
    center = weights(parsed.flags.shape,parsed.target_x,parsed.target_y,2,"center")
    boundary = np.argwhere((weighted>0)&(center==0))[0]
    parsed.flags[tuple(boundary)] = 1 << 7
    assert measure(parsed,"center")["flux_ujy"] is not None
    assert measure(parsed,"fractional")["reason"] == "incomplete_aperture_support"


def test_unsupported_background_or_truncated_aperture_never_passes():
    parsed = input_array()
    parsed.background_metadata = {"subtracted":False}
    assert measure(parsed,"fractional")["reason"] == "unsupported_field_background"
    parsed = input_array(x=1)
    assert measure(parsed,"fractional")["reason"] == "annulus_or_aperture_outside_image"


def test_empty_holdout_and_overflow_catalog_fail_closed():
    assert stability([],"fractional")["status"] == "insufficient"
    with pytest.raises(ValueError,match="Incomplete"):
        table_rows(b'<VOTABLE><RESOURCE><INFO name="QUERY_STATUS" value="OVERFLOW">cap reached</INFO></RESOURCE></VOTABLE>')


def test_locked_holdout_excludes_all_previous_controls():
    plan = read_json(ROOT/"docs/evidence/phase4/phase4-science-preregistration.json")
    lock = read_json(ROOT/"docs/evidence/phase4/phase4-science-control-lock.json")
    ids = {row["gaia"]["source_id"] for row in lock["shortlist"]}
    assert ids.isdisjoint(plan["excluded_phase3_source_ids"])
    assert len(plan["excluded_phase3_source_ids"]) == 10
    assert plan["measurement_gates"]["max_abs_z"] == 5


def test_replay_preserves_original_evidence_and_rejects_changed_result(tmp_path):
    path = tmp_path/"result.json"
    preserve_result(path,{"created_at":"original", "status":"failed"})
    original = path.read_bytes()
    preserve_result(path,{"created_at":"later", "status":"failed"})
    assert path.read_bytes() == original
    with pytest.raises(ValueError,match="never overwrite"):
        preserve_result(path,{"created_at":"later", "status":"pass"})
    assert path.read_bytes() == original
