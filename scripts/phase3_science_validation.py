#!/usr/bin/env python3
"""Reproducible raw-observation audit; never rebuilds shipped golden products."""
from __future__ import annotations
import argparse
import ast
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import logging
import math
import re
from pathlib import Path
import sys
import tempfile
import time

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.time import Time
from astropy.stats import sigma_clipped_stats
from astropy.table import Table
from photutils.aperture import CircularAperture, CircularAnnulus, aperture_photometry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from core.config import Settings
from core import flags as policy
from services.irsa_client import ArtifactRecord, IrsaClient

CACHE = ROOT / "backend/.cache/phase3"
OUTPUT = ROOT / "docs/evidence/phase3/phase3-science-results.json"
TARGETS = ("wise_0855", "barnards_star", "rw_aurigae", "r_draconis", "eps_indi_b")
THRESHOLDS = {
    "registered_before_raw_download": "2026-11-14",
    "matched_aperture_relative_tolerance": 1e-8,
    "minimum_static_controls": 3,
    "max_abs_median_standardized_control_residual": 1.0,
    "max_robust_control_scatter": 2.0,
    "max_abs_individual_control_sigma": 5.0,
    "spectral_tolerance_fraction_narrower_bandwidth": .25,
    "minimum_bandwidth_ratio": .8,
    "aperture_radius_arcsec": 12.3,
    "annulus_inner_native_pixels": 3.0,
    "annulus_outer_native_pixels": 5.0,
    "minimum_annulus_pixels": 10,
    "minimum_control_clean_fraction": 1.0,
    "minimum_control_snr_each_visit": 5.0,
    "control_g_mag_range": [10,15.5],
    "max_control_proper_motion_mas_year": 100,
    "known_neighbor_exclusion_arcsec": 12.3,
    "max_controls_sorted_by_source_id": 10,
    "max_temporal_drift_arcsec": 1.5375,
    "exclude_control_radius_around_target_arcsec": 30.0,
    "note": "Fixed engineering audit gates, not calibrated false-positive probabilities; no tuning after target flux inspection.",
}

OFFICIAL_URL = "https://raw.githubusercontent.com/Caltech-IPAC/irsa-tutorials/main/tutorials/spherex/spherex_source_discovery/spherex_source_discovery_tool/aperture_photometry.py"
OFFICIAL_SHA256 = "d89cbe1042383a8e1d03747e9728d4ec310d8201d05ca150367917b3b1a1270d"


def finite(value):
    return float(value) if value is not None and np.isfinite(value) else None


def mad(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return float(1.4826*np.median(np.abs(values-np.median(values)))) if values.size else None


def matched_aperture_reference(parsed):
    """Photutils center-pixel geometry, independently of extract_channel summation."""
    image, variance, flags = parsed.image_mjy_sr, parsed.variance_mjy_sr2, parsed.flags
    yy, xx = np.indices(image.shape)
    d = np.hypot(xx-parsed.target_x, yy-parsed.target_y)
    radius = 12.3 / parsed.native_pixel_scale_arcsec
    finite_data = np.isfinite(image) & np.isfinite(variance) & (variance > 0)
    good = finite_data & ((flags & policy.PHOTOMETRY_EXCLUDE_MASK) == 0)
    aperture = d <= radius
    annulus = (d >= 3) & (d <= 5) & good & ((flags & policy.BIT_SOURCE) == 0)
    n = int((aperture & good).sum())
    background = float(np.median(image[annulus])) if annulus.sum() >= 10 else 0.0
    omega = (parsed.native_pixel_scale_arcsec*np.pi/(180*3600))**2
    if n == 0:
        return {"flux_ujy": None, "error_ujy": None, "clean_pixels": 0, "annulus_pixels": int(annulus.sum())}
    ap = CircularAperture([(parsed.target_x, parsed.target_y)], r=radius)
    flux = aperture_photometry(np.nan_to_num(image-background), ap, mask=~good, method="center")["aperture_sum"][0]
    var = aperture_photometry(np.nan_to_num(variance), ap, mask=~good, method="center")["aperture_sum"][0]
    return {"flux_ujy": float(flux*omega*1e12), "error_ujy": float(np.sqrt(var)*omega*1e12),
            "clean_pixels": n, "aperture_pixels": int(aperture.sum()), "annulus_pixels": int(annulus.sum()),
            "annulus_background_mjy_sr": background,
            "assumptions": "Same center-pixel aperture/annulus, masks, local background and constant WCS-determinant pixel area as SkyBlink; independent Photutils sum."}


def fractional_aperture_diagnostic(parsed):
    """Change only aperture boundary integration; lock the center-mask sky estimate."""
    reference = matched_aperture_reference(parsed)
    if not reference.get("clean_pixels"):
        return None
    good = ((parsed.flags & policy.PHOTOMETRY_EXCLUDE_MASK) == 0)&np.isfinite(parsed.image_mjy_sr)&np.isfinite(parsed.variance_mjy_sr2)&(parsed.variance_mjy_sr2 > 0)
    image = parsed.image_mjy_sr-reference.get("annulus_background_mjy_sr",0)
    aperture = CircularAperture([(parsed.target_x,parsed.target_y)],r=12.3/parsed.native_pixel_scale_arcsec)
    summed = aperture_photometry(np.nan_to_num(image),aperture,mask=~good,method="subpixel",subpixels=5)["aperture_sum"][0]
    omega = (parsed.native_pixel_scale_arcsec*np.pi/(180*3600))**2
    return finite(summed*omega*1e12)


def official_aperture_comparison(parsed):
    """Run reviewed upstream extraction function, with assumptions explicit."""
    path = CACHE / "official_aperture_photometry.py"
    if not path.exists():
        return {"status": "not_run", "reason": "Official source file not cached", "url": OFFICIAL_URL}
    source = path.read_text(encoding="utf-8")
    if hashlib.sha256(path.read_bytes()).hexdigest() != OFFICIAL_SHA256:
        raise ValueError("Official aperture source changed; review it before execution")
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "extract_photometry")
    namespace = {"np": np, "Table": Table, "CircularAperture": CircularAperture,
                 "CircularAnnulus": CircularAnnulus, "aperture_photometry": aperture_photometry,
                 "sigma_clipped_stats": sigma_clipped_stats}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    yy, xx = np.indices(parsed.image_mjy_sr.shape)
    d = np.hypot(xx-parsed.target_x, yy-parsed.target_y)
    bad = ((parsed.flags & policy.PHOTOMETRY_EXCLUDE_MASK) != 0) | ~np.isfinite(parsed.variance_mjy_sr2)
    image = parsed.image_mjy_sr.copy()
    image[bad | ((d >= 3) & ((parsed.flags & policy.BIT_SOURCE) != 0))] = np.nan
    radius = 12.3 / parsed.native_pixel_scale_arcsec
    result = namespace["extract_photometry"](image, [(parsed.target_x, parsed.target_y)], [radius], 3, 5, mask=bad)
    omega = (parsed.native_pixel_scale_arcsec*np.pi/(180*3600))**2
    return {"status": "executed", "source_url": OFFICIAL_URL, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "flux_ujy": finite(result[f"aper_sum_bkgsub_r{radius:.1f}"][0]*omega*1e12),
            "annulus_median_mjy_sr": finite(result["annulus_median"][0]),
            "assumptions": "Reviewed actual IRSA function: 5x5 subpixel aperture, sigma-clipped median annulus. Radius/annulus adapted to SkyBlink 12.3arcsec and3-5pixels; masked pixels setNaN including SOURCE only in annulus. Constant WCS pixel area, not SAPM. Not IRSA Tractor photometry; no aperture correction.",
            "limitation": "IRSA function subtracts full geometric aperture area, SkyBlink only retained center pixels; flagged or fractional boundary apertures need not agree."}


def background_trial(raw, flags):
    good = np.isfinite(raw) & ((flags & policy.BACKGROUND_EXCLUDE_MASK) == 0)
    if good.sum() < 11:
        return {"status": "insufficient", "clean_pixels": int(good.sum())}
    scalar = float(np.median(raw[good]))
    yy, xx = np.indices(raw.shape)
    cells = []
    for iy, ys in enumerate(np.array_split(np.arange(raw.shape[0]), 4)):
        for ix, xs in enumerate(np.array_split(np.arange(raw.shape[1]), 4)):
            mask = good[np.ix_(ys, xs)]
            values = raw[np.ix_(ys, xs)][mask]
            if values.size >= 11:
                cells.append((ix, iy, float(xs.mean()), float(ys.mean()), float(np.median(values)), int(values.size)))
    result = {"clean_pixels": int(good.sum()), "valid_cells": len(cells), "scalar_mjy_sr": scalar,
              "scalar_pixel_mad_mjy_sr": mad(raw[good]-scalar)}
    if len(cells) < 8:
        return dict(result, status="insufficient_spatial_support")
    array = np.array(cells)
    design = np.column_stack([np.ones(len(cells)), array[:,2], array[:,3]])
    train = ((array[:,0]+array[:,1]) % 2) == 0
    if train.sum() < 3 or (~train).sum() < 3:
        return dict(result, status="insufficient_holdout_support")
    coefficients = np.linalg.lstsq(design[train], array[train,4], rcond=None)[0]
    heldout = array[~train,4]-design[~train]@coefficients
    baseline = array[~train,4]-np.median(array[train,4])
    result.update(status="measured", scalar_heldout_rms_mjy_sr=float(np.sqrt(np.mean(baseline**2))),
                  plane_heldout_rms_mjy_sr=float(np.sqrt(np.mean(heldout**2))),
                  plane_gradient_across_frame_mjy_sr=float(abs(coefficients[1])*raw.shape[1]+abs(coefficients[2])*raw.shape[0]),
                  note="Independent fixed4x4 checkerboard holdout trial; scalar and plane evaluated on same held-out cells, not fit residuals. Does not establish diffuse emission is sky background.")
    return result


def analyze_sample(sample, content):
    from services.spherex_pipeline import parse_cutout, render_webp
    from services.spectrophotometry import extract_channel
    parsed = parse_cutout(content, sample["ra"], sample["dec"], display_bad_mask=policy.HALO_DISPLAY_BAD_MASK)
    with fits.open(BytesIO(content), memmap=False) as hdul:
        raw = np.array(hdul["IMAGE"].data, dtype=float)-np.array(hdul["ZODI"].data, dtype=float)
        header = hdul["IMAGE"].header
        dates = {key: header.get(key) for key in ("MJD-BEG", "MJD-END", "MJD-AVG", "DATE-OBS")}
    yy, xx = np.indices(raw.shape)
    aperture = np.hypot(xx-parsed.target_x, yy-parsed.target_y) <= 12.3/parsed.native_pixel_scale_arcsec
    bits = {name:policy.FLAG_BITS[name] for name in ("SOURCE", "DICHROIC", "HALO", "OVERFLOW", "SUR_ERROR")}
    coverage = {name:{"whole_frame":int(np.count_nonzero(parsed.flags & (1<<bit))),
                      "target_aperture":int(np.count_nonzero((parsed.flags & (1<<bit))[aperture]))} for name,bit in bits.items()}
    channel = extract_channel(parsed, sample["band"])
    reference = matched_aperture_reference(parsed)
    agreement = None
    if channel and channel["flux_ujy"] is not None and reference["flux_ujy"] is not None:
        agreement = bool(np.isclose(channel["flux_ujy"],reference["flux_ujy"],rtol=THRESHOLDS["matched_aperture_relative_tolerance"],atol=1e-8))
    # Display transformations operate on copies; physical extraction is repeated.
    before = None if channel is None else channel["flux_ujy"]
    original = parsed.image_mjy_sr.copy()
    image_hashes = []
    upper = max(float(np.nanpercentile(original,99)),1e-6)
    with tempfile.TemporaryDirectory(prefix="stretch-audit-",dir=CACHE) as temporary:
        for stretch in (.5, 2, 10):
            preview = Path(temporary)/f"stretch-{stretch}.webp"
            render_webp(parsed.image_mjy_sr,preview,limits=(0,upper*stretch))
            image_hashes.append(hashlib.sha256(preview.read_bytes()).hexdigest())
    after_channel = extract_channel(parsed, sample["band"])
    after = None if after_channel is None else after_channel["flux_ujy"]
    error_ratio = channel["flux_err_ujy"]/reference["error_ujy"] if channel and channel["flux_err_ujy"] is not None and reference["error_ujy"] else None
    return {"dates": dates, "shape": list(raw.shape), "flag_coverage": coverage,
            "background_comparison": background_trial(raw, parsed.flags),
            "production_background": getattr(parsed,"background_metadata",None),
            "pipeline_channel": channel, "matched_aperture_reference": reference,
            "matched_aperture_agrees": agreement, "official_irsa_aperture": official_aperture_comparison(parsed),
            "error_ratio_including_background_to_native_floor":error_ratio,
            "display_stretch_independent": before == after and np.array_equal(original,parsed.image_mjy_sr,equal_nan=True),
            "distinct_display_hashes": len(set(image_hashes)),
            "display_test_scope": "Actual production WebP renderer at three fixed-relative displaylimits; raw-unit arrays unchanged and extraction repeated; previews discarded."}


def temporal_audit():
    result = []
    for target in TARGETS:
        manifest = json.loads((ROOT/"golden_cache"/target/"manifest.json").read_text())
        record = manifest["target"]
        speed = math.hypot(record["pm_ra_mas_yr"],record["pm_dec_mas_yr"])/1000
        for epoch in manifest["epochs"]:
            weeks = []
            means = []
            band_spans = {}
            for detector,band in epoch["band_stats"].items():
                band_weeks = []
                means.append(band["mjd_mean"])
                for uri in band["artifact_uris"]:
                    match = re.search(r"level2_(\d{4})W(\d{2})_",uri)
                    if match:
                        day = datetime.fromisocalendar(int(match[1]),int(match[2]),1)
                        weeks.append(day)
                        band_weeks.append(day)
                if band_weeks:
                    days = (max(band_weeks)-min(band_weeks)).days+7
                    band_spans[detector] = {"planning_week_span_upper_bound_days":days,
                                           "drift_upper_bound_arcsec":speed*days/365.25}
            span = (max(weeks)-min(weeks)).days+7 if weeks else None
            drift = speed*span/365.25 if span is not None else None
            result.append({"target_id":target,"epoch_id":epoch["epoch_id"],"recorded_uri_count":len(weeks),
                           "planning_week_span_upper_bound_days":span,"proper_motion_arcsec_year":speed,
                           "predicted_drift_upper_bound_arcsec":drift,
                           "exceeds_half_output_pixel":drift>THRESHOLDS["max_temporal_drift_arcsec"] if drift is not None else None,
                           "between_band_mean_date_span_days":max(means)-min(means),
                           "per_band":band_spans,
                           "method":"Conservative ISO planning-week bounds from all recorded image URIs; not exact per-exposure dates. Per-downloaded exposure FITS dates recorded separately."})
    return result


def static_control_audit(successful):
    from services.live_selection import spectral_signature, dense_spectral_signature, compatible
    from services.spherex_pipeline import parse_cutout
    from services.spectrophotometry import extract_channel
    results = []
    for target in TARGETS:
        band = 6 if target == "wise_0855" else 3
        pair = [sample for sample in successful if sample["target_id"] == target and sample["band"] == band]
        result = {"target_id":target, "band":band, "controls":[], "status":"not_established"}
        results.append(result)
        if len(pair) != 2:
            result["reason"] = "Two real inputs not available"
            continue
        data = [(ROOT/sample["path"]).read_bytes() for sample in pair]
        signatures = [spectral_signature(content,pair[0]["ra"],pair[0]["dec"],.2) for content in data]
        result["sample_ids"] = [sample["id"] for sample in pair]
        result["coarse_wavelength_compatible"] = compatible(*signatures)
        result["center_wavelength_um"] = [finite(signature[0][4]) for signature in signatures]
        result["center_bandwidth_um"] = [finite(signature[1][4]) for signature in signatures]
        if not result["coarse_wavelength_compatible"]:
            result["reason"] = "Recorded exposures fail spectral compatibility; no variability inference or unmatched control subtraction performed"
            continue
        dense = [dense_spectral_signature(content,pair[0]["ra"],pair[0]["dec"],.2) for content in data]
        result["dense_wavelength_compatible"] = compatible(*dense)
        result["dense_samples_per_exposure"] = int(dense[0].shape[1])
        if not result["dense_wavelength_compatible"]:
            result["reason"] = "Coarse samples passed but dense field compatibility failed; no control subtraction accepted"
            continue
        # These controls are selected from recorded Gaia metadata, before reading
        # their infrared flux. The saved G<16 catalog cannot screen all faint blends.
        sources = json.loads((ROOT/"golden_cache"/target/"gaia_dr3.json").read_text())["sources"]
        center = SkyCoord(pair[0]["ra"],pair[0]["dec"],unit="deg")
        for source in sorted(sources,key=lambda source:source["source_id"]):
            if source.get("pmra") is None or source.get("pmdec") is None:
                continue
            if not (10 <= source["g_mag"] <= 15.5) or math.hypot(source["pmra"],source["pmdec"]) > 100:
                continue
            coord = SkyCoord(ra=source["ra"]*u.deg,dec=source["dec"]*u.deg,pm_ra_cosdec=source["pmra"]*u.mas/u.yr,
                             pm_dec=source["pmdec"]*u.mas/u.yr,obstime=Time(2016,format="jyear"))
            if coord.separation(center).arcsec < 30:
                continue
            lon,lat = center.spherical_offsets_to(SkyCoord(coord.ra,coord.dec,frame="icrs"))
            if max(abs(lon.deg),abs(lat.deg)) > .1-12.3/3600:
                continue  # Entire control aperture must lie inside the matched .2deg field.
            neighbors = [(coord.separation(SkyCoord(other["ra"],other["dec"],unit="deg")).arcsec,other["source_id"])
                         for other in sources if other["source_id"] != source["source_id"]]
            nearest = min(neighbors) if neighbors else None
            if nearest and nearest[0] < 12.3:
                continue
            channels = []
            diagnostics = []
            for sample,content in zip(pair,data):
                moved = coord.apply_space_motion(new_obstime=Time(sample["analysis"]["dates"]["MJD-AVG"],format="mjd"))
                parsed = parse_cutout(content,moved.ra.deg,moved.dec.deg)
                channel = extract_channel(parsed,band)
                if (not channel or not channel["is_used_in_photometry"] or channel["clean_fraction"] < 1
                        or channel["flux_ujy"] is None or not channel["flux_err_ujy"]
                        or channel["flux_ujy"]/channel["flux_err_ujy"] < 5):
                    break
                channels.append(channel)
                yy,xx = np.indices(parsed.flags.shape)
                region = np.hypot(xx-parsed.target_x,yy-parsed.target_y) <= 2
                positive = np.where(region & np.isfinite(parsed.image_mjy_sr),np.maximum(parsed.image_mjy_sr,0),0)
                total = positive.sum()
                centroid = [float((positive*xx).sum()/total-parsed.target_x),float((positive*yy).sum()/total-parsed.target_y)] if total>0 else None
                diagnostics.append({"reference":matched_aperture_reference(parsed),
                                    "official_irsa":official_aperture_comparison(parsed),
                                    "same_background_fractional_flux_ujy":fractional_aperture_diagnostic(parsed),
                                    "center_x":parsed.target_x,"center_y":parsed.target_y,
                                    "positive_aperture_centroid_offset_pixels":centroid,
                                    "flags_at_extraction_center":channel["flags"]})
            if len(channels) != 2:
                continue
            difference = channels[1]["flux_ujy"]-channels[0]["flux_ujy"]
            error = math.hypot(channels[0]["flux_err_ujy"],channels[1]["flux_err_ujy"])
            result["controls"].append({"gaia_source_id":source["source_id"],"flux_ujy":[c["flux_ujy"] for c in channels],
                                       "difference_ujy":difference,"approx_error_ujy":error,"standardized_residual":difference/error,
                                       "catalog_ra":source["ra"],"catalog_dec":source["dec"],"g_mag":source["g_mag"],
                                       "nearest_saved_gaia_neighbor":{"distance_arcsec":float(nearest[0]),"source_id":nearest[1]} if nearest else None,
                                       "exploratory_diagnostics":diagnostics,
                                       "exploratory_note":"Same locked controls; no rejection based on residual. Official/subpixel alternatives are diagnostic, not a new acceptance threshold. Centroid is positive-pixel aperture moment, not a PSF fit."})
            if len(result["controls"]) == 10:
                break
        result["limitation"] = "Saved Gaia G<16 metadata and proper motions; faint blends/IR variability not excluded. Approximate errors include background-estimate uncertainty but not all covariance/model error. Not independently certified static sources."
        z = [control["standardized_residual"] for control in result["controls"]]
        if len(z) < 3:
            result["reason"] = "Fewer than three clean high-SNR candidate controls"
            continue
        result.update(median_standardized_residual=float(np.median(z)),robust_scatter=mad(z),max_abs_residual=float(np.max(np.abs(z))))
        result["status"] = "diagnostic_pass" if abs(np.median(z)) <= 1 and mad(z) <= 2 and np.max(np.abs(z)) <= 5 else "failed"
        alternative = [(control["exploratory_diagnostics"][1]["same_background_fractional_flux_ujy"]-
                        control["exploratory_diagnostics"][0]["same_background_fractional_flux_ujy"])/control["approx_error_ujy"]
                       for control in result["controls"]]
        result["exploratory_fractional_aperture"] = {"median_using_original_errors":float(np.median(alternative)),
                                                    "robust_scatter_using_original_errors":mad(alternative),
                                                    "max_abs_using_original_errors":float(np.max(np.abs(alternative))),
                                                    "acceptance":"not_retested; exploratory geometry diagnosis on same locked controls, not independent validation"}
    return results


def samples():
    result = []
    for target in TARGETS:
        manifest = json.loads((ROOT / "golden_cache" / target / "manifest.json").read_text())
        for index, epoch in enumerate(manifest["epochs"][:2]):
            bands = [6] if target == "wise_0855" else [3]
            if target == "wise_0855" and index == 0:
                bands.extend([1,3])  # D3 from recorded DICHROIC warning, not flux.
            for band in bands:
                uri = epoch["band_stats"][str(band)]["artifact_uris"][0]
                result.append({"id": f"{target}_{epoch['epoch_id']}_D{band}", "target_id": target,
                               "epoch_id": epoch["epoch_id"], "band": band, "uri": uri,
                               "ra": manifest["query"]["ra"], "dec": manifest["query"]["dec"],
                               "recorded_epoch_mjd_mean": epoch["mjd_mean"], "release": epoch["release"],
                               "collection": epoch["collection"], "requested_size_deg": .2,
                               "fetch_size_deg": math.sqrt(2)*.2 + 2*6.15/3600,
                               "selection": "First recorded URI, first two stored epochs; WISE D3 additional flag-coverage sample from manifest DICHROIC warning. Not chosen by measured flux."})
                if target == "wise_0855" and index == 0 and band == 3:
                    for visit,extra in enumerate(epoch["band_stats"]["3"]["artifact_uris"][1:],start=2):
                        result.append(dict(result[-1],id=f"{target}_{epoch['epoch_id']}_D3_visit{visit}",uri=extra,
                                           selection="Additional recorded D3 contributors to the manifest's DICHROIC warning; first contributor has no DICHROIC in this cutout. Flag coverage only."))
    return result


def download(sample):
    record = ArtifactRecord(sample["uri"], sample["recorded_epoch_mjd_mean"], None,
                            sample["band"], f"SPHEREx-D{sample['band']}", sample["id"],
                            sample["release"], sample["collection"])
    start = time.monotonic()
    client = IrsaClient(replace(Settings(), cache_dir=CACHE, retries=1, request_timeout_seconds=25),
                        deadline_at=start + 55)
    content = client.fetch_cutout(record, sample["ra"], sample["dec"], sample["fetch_size_deg"])
    path = client._cutout_cache_path(record, sample["ra"], sample["dec"], sample["fetch_size_deg"])
    return content, {"path": path.relative_to(ROOT).as_posix(), "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest(), "seconds": round(time.monotonic()-start, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--analyze-only", action="store_true", help="Use cached inputs only; never retry network failures")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    CACHE.mkdir(parents=True, exist_ok=True)
    official = CACHE / "official_aperture_photometry.py"
    if not args.analyze_only and not official.exists():
        import httpx
        response = httpx.get(OFFICIAL_URL,timeout=25)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != OFFICIAL_SHA256:
            raise ValueError("Upstream aperture implementation changed; review required")
        official.write_bytes(response.content)
    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    saved = {sample["id"]:sample for sample in previous.get("samples",[])}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "thresholds": THRESHOLDS,
              "sample_selection": "11 preselected recorded input exposures plus three recorded WISE D3 contributors selected from manifest DICHROIC warning for actual flag coverage; raw units only; no golden rebuild.",
              "samples": [], "science_acceptance": "not_established"}
    for sample in samples():
        try:
            old = saved.get(sample["id"],{})
            if old.get("path") and (ROOT/old["path"]).exists():
                content = (ROOT/old["path"]).read_bytes()
                metadata = {key:old[key] for key in ("path","bytes","sha256","seconds")}
                assert hashlib.sha256(content).hexdigest() == old["sha256"], "Cached input hash mismatch"
            elif args.analyze_only:
                raise FileNotFoundError("Selected input not cached; analyze-only does not retry archive")
            else:
                content, metadata = download(sample)
            sample.update(download_status="success", **metadata)
            if not args.download_only:
                sample["analysis"] = analyze_sample(sample,content)
        except Exception as exc:
            sample.setdefault("download_status","failed")
            sample.update(error_type=type(exc).__name__, error=str(exc))
        report["samples"].append(sample)
        if args.download_only:
            OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        print(json.dumps({"id": sample["id"], "status": sample["download_status"], "path": sample.get("path"),"analysis_error":sample.get("error")}), flush=True)
    if not args.download_only:
        report["temporal_smearing"] = temporal_audit()
        report["static_controls"] = static_control_audit([s for s in report["samples"] if "analysis" in s])
        temporary = OUTPUT.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        temporary.replace(OUTPUT)


if __name__ == "__main__":
    main()
