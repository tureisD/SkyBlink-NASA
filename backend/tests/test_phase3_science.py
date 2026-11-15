"""Science regressions on cached real inputs; no archive calls in pytest.

Raw inputs are ignored local research files, not shipped fixtures. Controlled
flag/variance mutations below are explicitly test-only and never products.
"""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path

from astropy.io import fits
import numpy as np
import pytest

from core import flags as policy
from services.background import estimate_background
from services.spherex_pipeline import parse_cutout, reproject_to_grid, output_wcs, render_webp, _coadd_band, _apply_normalization
from services.irsa_client import ArtifactRecord
from services.spectrophotometry import extract_channel
from scripts.phase3_science_validation import matched_aperture_reference

ROOT = Path(__file__).resolve().parents[2]


def real_input(sample_id):
    report = ROOT / "docs/evidence/phase3/phase3-science-results.json"
    if not report.exists():
        pytest.skip("Run phase3_science_validation.py to obtain ignored real inputs")
    samples = json.loads(report.read_text())["samples"]
    sample = next((sample for sample in samples if sample["id"] == sample_id),None)
    if not sample or not sample.get("path") or not (ROOT/sample["path"]).exists():
        pytest.skip(f"Real input not cached: {sample_id}")
    content = (ROOT/sample["path"]).read_bytes()
    parsed = parse_cutout(content,sample["ra"],sample["dec"],display_bad_mask=policy.HALO_DISPLAY_BAD_MASK)
    return sample,content,parsed


@pytest.mark.parametrize("sample_id", ["wise_0855_2025_E1_D6","wise_0855_2025_E1_D1","wise_0855_2025_E2_D6",
                                       "rw_aurigae_2025_E1_D3","eps_indi_b_2024_E1_D3"])
def test_real_flux_matches_independent_center_pixel_reference(sample_id):
    sample,_,parsed = real_input(sample_id)
    channel = extract_channel(parsed,sample["band"])
    reference = matched_aperture_reference(parsed)
    assert channel["flux_ujy"] == pytest.approx(reference["flux_ujy"],rel=1e-8,abs=1e-8)
    assert channel["flux_err_ujy"] >= reference["error_ujy"]*(1-1e-12)


@pytest.mark.parametrize("sample_id", ["barnards_star_2025_E1_D3","r_draconis_2024_E1_D3"])
def test_real_saturated_core_retains_null_and_bad_status(sample_id):
    sample,_,parsed = real_input(sample_id)
    channel = extract_channel(parsed,sample["band"])
    assert channel["is_used_in_photometry"] is False
    assert channel["is_flagged_bad"] is True
    assert channel["flux_ujy"] is None


def test_real_source_survives_measurement_and_halo_remains_display_only():
    sample,_,parsed = real_input("wise_0855_2025_E1_D6")
    frame = reproject_to_grid(parsed,output_wcs(sample["ra"],sample["dec"]))
    source_only = ((frame.flags & policy.BIT_SOURCE) != 0) & ((frame.flags & policy.PHOTOMETRY_EXCLUDE_MASK) == 0)
    halo = (frame.flags & policy.HALO_BIT) != 0
    assert np.count_nonzero(np.isfinite(frame.measurement_image_mjy_sr[source_only])) > 0
    assert np.count_nonzero(np.isfinite(frame.image_mjy_sr[halo])) > 0
    assert not np.any(np.isfinite(frame.measurement_image_mjy_sr[halo]))


def test_real_dichroic_warning_is_visible_but_not_measured():
    sample,_,parsed = real_input("wise_0855_2025_E1_D3_visit2")
    assert np.count_nonzero(parsed.flags & policy.FLAG_VALUES["DICHROIC"]) > 0
    frame = reproject_to_grid(parsed,output_wcs(sample["ra"],sample["dec"]))
    dichroic = (frame.flags & policy.FLAG_VALUES["DICHROIC"]) != 0
    assert np.count_nonzero(np.isfinite(frame.image_mjy_sr[dichroic])) > 0
    assert not np.any(np.isfinite(frame.measurement_image_mjy_sr[dichroic]))


def test_real_coadd_masks_measurements_and_normalizes_display_only():
    sample,content,_ = real_input("wise_0855_2025_E1_D3_visit2")
    record = ArtifactRecord(sample["uri"],sample["recorded_epoch_mjd_mean"],None,3,"SPHEREx-D3",sample["id"],"DR1","spherex_dr1")
    coadd = _coadd_band("audit",3,[record],{record:content},output_wcs(sample["ra"],sample["dec"]),
                        sample["ra"],sample["dec"],display_bad_mask=policy.HALO_DISPLAY_BAD_MASK)
    assert coadd is not None
    dichroic = (coadd.flags & policy.FLAG_VALUES["DICHROIC"]) != 0
    assert np.any(np.isfinite(coadd.display_image_mjy_sr[dichroic]))
    assert not np.any(np.isfinite(coadd.image_mjy_sr[dichroic]))
    raw = coadd.image_mjy_sr.copy()
    variance = coadd.variance_mjy_sr2.copy()
    _apply_normalization({("audit",3):coadd},{"scale_by_epoch_band":{"audit":{"3":2.0}}})
    assert np.array_equal(coadd.image_mjy_sr,raw,equal_nan=True)
    assert np.array_equal(coadd.variance_mjy_sr2,variance,equal_nan=True)
    assert np.allclose(coadd.normalized_image_mjy_sr,coadd.display_image_mjy_sr*2,equal_nan=True)


def test_live_coadd_crop_excludes_unvalidated_pixels_from_all_products():
    sample,content,_ = real_input("wise_0855_2025_E1_D6")
    record = ArtifactRecord(sample["uri"],sample["recorded_epoch_mjd_mean"],None,6,"SPHEREx-D6",sample["id"],"DR1","spherex_dr1")
    coadd = _coadd_band("audit",6,[record],{record:content},output_wcs(sample["ra"],sample["dec"]),
                        sample["ra"],sample["dec"],field_size_deg=.05)
    mask = np.zeros((240,240),dtype=bool)
    mask[91:149,91:149] = True
    assert np.count_nonzero(np.isfinite(coadd.image_mjy_sr[mask])) > 10
    assert not np.any(np.isfinite(coadd.image_mjy_sr[~mask]))
    assert not np.any(np.isfinite(coadd.display_image_mjy_sr[~mask]))
    assert not np.any(coadd.flags[~mask])
    assert not np.any(coadd.footprint[~mask])


def test_measured_gradient_selects_2d_only_with_heldout_support():
    _,_,parsed = real_input("wise_0855_2025_E2_D6")
    assert parsed.background_metadata["status"] == "ok_2d"
    assert parsed.background_metadata["subtracted"] is True


def test_insufficient_background_never_claims_subtraction_or_usable_flux():
    _,content,parsed = real_input("wise_0855_2025_E1_D6")
    with fits.open(BytesIO(content)) as hdul:
        raw = hdul["IMAGE"].data.astype(float)-hdul["ZODI"].data
    # Test-only mutation preserves real pixels and removes all eligible sky.
    flags = parsed.flags | policy.BIT_SOURCE
    estimate = estimate_background(raw,flags)
    assert estimate.metadata["status"] == "insufficient"
    assert estimate.metadata["subtracted"] is False
    result = extract_channel(replace(parsed,background_metadata=estimate.metadata),6)
    assert result["clean_fraction"] > 0
    assert result["flux_ujy"] is None
    assert result["is_used_in_photometry"] is False


def test_corner_only_real_background_support_is_explicitly_insufficient():
    _,content,parsed = real_input("wise_0855_2025_E1_D6")
    with fits.open(BytesIO(content)) as hdul:
        raw = hdul["IMAGE"].data.astype(float)-hdul["ZODI"].data
    flags = parsed.flags | policy.BIT_SOURCE
    height,width = flags.shape
    flags[:height//2,:width//2] = parsed.flags[:height//2,:width//2]
    estimate = estimate_background(raw,flags)
    assert estimate.metadata["clean_pixels"] >= 11
    assert estimate.metadata["status"] == "insufficient_spatial_support"
    assert estimate.metadata["subtracted"] is False


def test_real_background_variance_increases_approximate_flux_error():
    _,_,parsed = real_input("wise_0855_2025_E1_D6")
    yy,xx = np.indices(parsed.flags.shape)
    distance = np.hypot(xx-parsed.target_x,yy-parsed.target_y)
    annulus = (distance >= 3)&(distance <= 5)
    baseline = extract_channel(parsed,6)
    variance = parsed.variance_mjy_sr2.copy()
    variance[annulus] *= 100  # Controlled variance-only perturbation of a real cutout.
    noisier = extract_channel(replace(parsed,variance_mjy_sr2=variance),6)
    assert noisier["flux_ujy"] == baseline["flux_ujy"]
    assert noisier["flux_err_ujy"] > baseline["flux_err_ujy"]


def test_actual_renderer_stretches_do_not_change_raw_photometry(tmp_path):
    _,_,parsed = real_input("wise_0855_2025_E1_D6")
    original = parsed.image_mjy_sr.copy()
    before = extract_channel(parsed,6)
    previews = []
    for upper in (.1,1,10):
        path = tmp_path/f"stretch{upper}.webp"
        render_webp(parsed.image_mjy_sr,path,limits=(0,upper))
        previews.append(path.read_bytes())
    assert len(set(previews)) == 3
    assert np.array_equal(parsed.image_mjy_sr,original,equal_nan=True)
    assert extract_channel(parsed,6) == before
