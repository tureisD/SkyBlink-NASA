"""Reproduce the Phase 3 calibration, flag-table, and target-coordinate audit.

This audit consumes real upstream products only and never edits runtime data.
Run from the repository root with backend dependencies plus pypdf installed:
    python scripts/phase3_calibration_audit.py [--download]
The optional download flag retrieves missing inputs into ignored .cache only.
Science-agent cutouts are reused from docs/evidence/phase3/phase3-science-results.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import httpx
import numpy as np
from astropy.coordinates import SkyCoord, get_body_barycentric
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from erfa import ErfaWarning

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from core.flags import (  # noqa: E402
    ARTIFACT_WARNING_MASK, FLAG_BITS, HARD_BAD_MASK, PHOTOMETRY_EXCLUDE_MASK,
)
from core.targets import TARGETS  # noqa: E402

CACHE = ROOT / "backend/.cache/phase3"
OUTPUT = ROOT / "docs/evidence/phase3/phase3-calibration-audit.json"
SUPPLEMENT_URL = "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf"
PRODUCT_DOC_URL = "https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/"
CALIBRATION_KEY = "dr1/spectral_wcs/cal-swcs-v5-2026-191/6/spectral_wcs_D6_spx_cal-swcs-v5-2026-191.fits"
CALIBRATION_URL = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/" + CALIBRATION_KEY
CALIBRATION_PATH = CACHE / CALIBRATION_KEY.rsplit("/", 1)[-1]
GAIA_URL = "https://gea.esac.esa.int/tap-server/tap/sync"
GAIA_IDS = {
    "barnards_star": "4472832130942575872",
    "eps_indi_b": "6412596012146801152",
    "rw_aurigae": "156430822114424576",
    "r_draconis": "1648328016354496384",
}
GAIA_QUERY = (
    "SELECT source_id,ra,dec,ref_epoch,pmra,pmdec,parallax,ruwe,"
    "astrometric_excess_noise,phot_g_mean_mag FROM gaiadr3.gaia_source "
    "WHERE source_id IN (" + ",".join(GAIA_IDS.values()) + ")"
)
WISE_PAPER_URL = "https://arxiv.org/pdf/1605.06655"
WISE_CATALOG_URL = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv"
WISE_CATALOG_PARAMS = {"-source": "J/ApJS/253/7/plx", "FName": "*0855*", "-out.all": "1", "-out.max": "10"}
# Real HST measurements, transcribed from Luhman & Esplin (2016), Table 2.
# Columns are observed ICRS RA (deg), Dec (deg), MJD. These are not test fixtures.
WISE_HST = np.array([
    [133.7851503, -7.2443041, 56986.82],
    [133.7843602, -7.2442366, 57084.82],
    [133.7840688, -7.2441796, 57123.17],
    [133.7819058, -7.2440115, 57474.62],
    [133.7818923, -7.2440157, 57475.41],
    [133.7818300, -7.2440063, 57484.38],
])


def file_evidence(path: Path, url: str | None = None) -> dict:
    result = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if url:
        result["url"] = url
    return result


def download_missing(path: Path, url: str, params: dict | None = None) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    try:
        with httpx.stream("GET", url, params=params, timeout=60, follow_redirects=True) as response:
            response.raise_for_status()
            total = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 40_000_000:
                        raise ValueError("Audit input exceeds 40 MB per-product limit")
                    handle.write(chunk)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def audit_flags() -> dict:
    from pypdf import PdfReader

    path = CACHE / "SPHEREx_Expsupp.pdf"
    reader = PdfReader(path)
    pages = [page.extract_text() for page in reader.pages]
    start = next(i for i, text in enumerate(pages) if "Table 16: Image pixel flags" in text)
    table = "\n".join(pages[start:start + 3]).split("3.2.6 Dark Subtraction")[0]
    official = {name: int(bit) for name, bit in re.findall(r"(?m)^([A-Z][A-Z_]+)\s+(\d+)\s", table)}
    version = re.search(r"Version ([\d.]+), ([\d-]+)", pages[0])
    flags = []
    for bit in range(32):
        name = next((name for name, value in official.items() if value == bit), None)
        flags.append({
            "bit": bit, "official_name": name,
            "defined_in_table16": name is not None,
            "backend_name": next((name for name, value in FLAG_BITS.items() if value == bit), None),
            "hard_mask": bool(HARD_BAD_MASK & (1 << bit)),
            "warning_mask": bool(ARTIFACT_WARNING_MASK & (1 << bit)),
            "excluded_from_photometry": bool(PHOTOMETRY_EXCLUDE_MASK & (1 << bit)),
        })
    return {
        "status": "verified" if official == FLAG_BITS else "mismatch",
        "source": file_evidence(path, SUPPLEMENT_URL),
        "supplement_version": version.group(1) if version else None,
        "supplement_date": version.group(2) if version else None,
        "pages_one_based": [start + 1, start + 2, start + 3],
        "official_defined_count": len(official), "all_bits": flags,
        "policy_notes": [
            "DICHROIC has low throughput and is unsuitable for photometry; measurement mask excludes it.",
            "SOURCE identifies known objects and is retained in measurement/display, excluded only for background.",
            "FULLSAMPLE is informational; no runtime bad-pixel mask contains it.",
            "HALO is a caution in Table 16; the application's hard measurement exclusion is conservative policy.",
            "GHOST_FPA is unused and scheduled for removal in Year 2 processing; retaining its warning bit is conservative.",
            "Undeclared bit numbers are not invented flag definitions.",
        ],
    }


def distribution(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not values.size:
        return {"count": 0, "median": None, "p95": None, "p99": None, "max": None}
    q = np.percentile(values, [50, 95, 99, 100])
    return dict(zip(["count", "median", "p95", "p99", "max"], [int(values.size), *map(float, q)]))


def audit_wavelengths() -> dict:
    inventory = json.loads((ROOT / "docs/evidence/phase3/phase3-science-results.json").read_text(encoding="utf-8"))
    samples = [sample for sample in inventory["samples"]
               if sample.get("download_status") == "success" and sample["band"] == 6
               and sample["release"] == "DR1"]
    results = []
    with fits.open(CALIBRATION_PATH, memmap=True) as calibration:
        cwave = calibration["CWAVE"].data
        cband = calibration["CBAND"].data
        for sample in samples:
            path = ROOT / sample["path"]
            with fits.open(path, memmap=False) as hdul:
                header = hdul["IMAGE"].header
                same_table = all(np.array_equal(hdul["WCS-WAVE"].data[name], calibration["WCS-WAVE"].data[name])
                                 for name in ["X", "Y", "VALUES"])
                same_orientation = header.get("DETCOORD") == calibration["CWAVE"].header.get("DETCOORD") == "sky"
                if not same_table or not same_orientation:
                    results.append({"sample_id": sample["id"], "status": "calibration_pairing_unverified"})
                    continue
                yy, xx = np.indices(hdul["IMAGE"].data.shape)
                # Alternate A WCS is original active detector coordinates, zero based.
                # Official cutout docs give x_original = 1 + x_cutout - CRPIX1A.
                x_original = 1 + xx - header["CRPIX1A"]
                y_original = 1 + yy - header["CRPIX2A"]
                if not np.all(x_original == np.rint(x_original)) or not np.all(y_original == np.rint(y_original)):
                    raise ValueError("Noninteger detector mapping: per-pixel lookup would be ambiguous")
                x_original = x_original.astype(int)
                y_original = y_original.astype(int)
                valid = ((x_original >= 0) & (y_original >= 0)
                         & (x_original < cwave.shape[1]) & (y_original < cwave.shape[0]))
                spectral_wcs = WCS(header, fobj=hdul, key="W")
                spectral_wcs.sip = None
                wave, bandwidth = spectral_wcs.pixel_to_world_values(xx, yy)
                exact_wave = cwave[y_original[valid], x_original[valid]]
                exact_band = cband[y_original[valid], x_original[valid]]
                dw = np.abs(wave[valid] - exact_wave)
                db = np.abs(bandwidth[valid] - exact_band)
                # A fractional click does not itself define a detector pixel.
                # Report the nearest native pixel explicitly, matching flag semantics.
                spatial_wcs = WCS(header, fobj=hdul).celestial
                x, y = spatial_wcs.world_to_pixel_values(sample["ra"], sample["dec"])
                ix, iy = int(np.rint(x)), int(np.rint(y))
                target_pixel = None
                if 0 <= iy < yy.shape[0] and 0 <= ix < xx.shape[1] and valid[iy, ix]:
                    ox, oy = int(x_original[iy, ix]), int(y_original[iy, ix])
                    target_pixel = {
                        "cutout_xy_zero_based": [ix, iy], "original_xy_zero_based": [ox, oy],
                        "cwave_um": float(cwave[oy, ox]), "cband_um": float(cband[oy, ox]),
                        "lookup_wave_um": float(wave[iy, ix]), "lookup_bandwidth_um": float(bandwidth[iy, ix]),
                        "wave_error_nm": float(abs(wave[iy, ix] - cwave[oy, ox]) * 1000),
                        "bandwidth_error_nm": float(abs(bandwidth[iy, ix] - cband[oy, ox]) * 1000),
                    }
                results.append({
                    "sample_id": sample["id"], "status": "measured",
                    "source": file_evidence(path, "https://irsa.ipac.caltech.edu/" + sample["uri"]),
                    "calibration_pairing": "DR1/D6/sky orientation and exact equality of all X,Y,VALUES lookup arrays",
                    "spectral_calibration_history": [str(v) for v in header.get("HISTORY", []) if "spectral_wcs" in str(v)],
                    "original_pixel_bounds_xy": [int(x_original.min()), int(x_original.max()), int(y_original.min()), int(y_original.max())],
                    "absolute_wave_error_nm": distribution(dw * 1000),
                    "absolute_bandwidth_error_nm": distribution(db * 1000),
                    "bandwidth_relative_error_fraction": distribution(db / exact_band),
                    "target_nearest_native_pixel": target_pixel,
                })
        advertised = {key: calibration[0].header.get(key) for key in ["WLERRMAX", "BWERRMAX", "WLERRP99", "BWERRP99"]}
    return {
        "status": "measured_subset" if results else "unavailable",
        "source": file_evidence(CALIBRATION_PATH, CALIBRATION_URL),
        "calibration_version": "cal-swcs-v5-2026-191", "release": "DR1", "detector": 6,
        "official_guidance": PRODUCT_DOC_URL,
        "header_approximation_error_um": advertised,
        "mapping": "Original zero-based active detector pixel = 1 + cutout zero-based pixel - CRPIXnA; DETCOORD sky already accounts for MWIR X flip.",
        "samples": results,
        "limitation": "One detector calibration and available DR1 sample cutouts only; not all bands/releases. WCS-WAVE remains visualization-only regardless of measured error.",
    }


def audit_gaia_targets() -> dict:
    path = CACHE / "gaia.csv"
    rows = {row["source_id"]: row for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines())}
    results = []
    for target in TARGETS:
        if target.id not in GAIA_IDS:
            continue
        row = rows[GAIA_IDS[target.id]]
        catalog = SkyCoord(
            ra=float(row["ra"]) * u.deg, dec=float(row["dec"]) * u.deg,
            pm_ra_cosdec=float(row["pmra"]) * u.mas / u.yr, pm_dec=float(row["pmdec"]) * u.mas / u.yr,
            obstime=Time(float(row["ref_epoch"]), format="jyear", scale="tcb"), frame="icrs",
        )
        at_query = catalog.apply_space_motion(new_obstime=Time(2025.8, format="decimalyear", scale="tt"))
        at_ref = catalog.apply_space_motion(new_obstime=Time(2000.0, format="jyear", scale="tt"))
        stored = SkyCoord(target.ra_epoch2025 * u.deg, target.dec_epoch2025 * u.deg)
        original = SkyCoord(target.ra_ref * u.deg, target.dec_ref * u.deg)
        direction = SkyCoord(at_query.ra, at_query.dec, frame="icrs")
        dra, ddec = stored.spherical_offsets_to(direction)
        results.append({
            "target_id": target.id, "source_id": row["source_id"],
            "gaia_dr3": {key: float(value) for key, value in row.items() if key != "source_id"},
            "stored_reference": {"ra": target.ra_ref, "dec": target.dec_ref, "epoch": target.ref_epoch,
                                 "pm_ra_mas_yr": target.pm_ra_mas_yr, "pm_dec_mas_yr": target.pm_dec_mas_yr},
            "gaia_back_propagated_j2000": {"ra": float(at_ref.ra.deg), "dec": float(at_ref.dec.deg),
                                          "stored_reference_separation_arcsec": float(original.separation(at_ref).arcsec)},
            "gaia_propagated_2025_8": {"ra": float(at_query.ra.deg), "dec": float(at_query.dec.deg),
                                       "stored_center_separation_arcsec": float(stored.separation(at_query).arcsec),
                                       "stored_to_gaia_offset_arcsec": [float(dra.arcsec), float(ddec.arcsec)]},
            "proper_motion_delta_mas_yr": [float(row["pmra"]) - target.pm_ra_mas_yr,
                                          float(row["pmdec"]) - target.pm_dec_mas_yr],
        })
    return {
        "status": "verified_catalog_records", "source": file_evidence(path, GAIA_URL), "adql": GAIA_QUERY,
        "method": "Gaia DR3 ICRS epoch2016.0 TCB; Astropy space motion to decimal2025.8 TT; no parallax/reflex or perspective acceleration applied, matching current product convention.",
        "targets": results,
        "cautions": [
            "Epsilon Indi B is Gaia DR3 6412596012146801152; previous no-Gaia-B claim was incorrect. RUWE approximately4.30 and binary photocenter make it unsuitable as a precision static control.",
            "R Draconis stored proper motion differs from Gaia; its reference position nevertheless matches Gaia back-propagated to J2000. The mixed-source trajectory needs a documented catalog decision.",
            "Gaia point-source astrometry and unresolved IR photocenters need not coincide for binaries/variables.",
        ],
    }


def audit_wise_reference() -> dict:
    """Diagnostic only: remove measured motion/parallax from actual HST positions."""
    target = next(target for target in TARGETS if target.id == "wise_0855")
    time = Time(WISE_HST[:, 2], format="mjd", scale="utc")
    reference_time = Time(2010.0, format="decimalyear", scale="tt")
    dt = (time - reference_time).to_value(u.yr)
    alpha, delta = np.deg2rad([target.ra_ref, target.dec_ref])
    earth = get_body_barycentric("earth", time).xyz.to_value(u.au)
    factor_ra = earth[0] * np.sin(alpha) - earth[1] * np.cos(alpha)
    factor_dec = (earth[0] * np.cos(alpha) * np.sin(delta)
                  + earth[1] * np.sin(alpha) * np.sin(delta) - earth[2] * np.cos(delta))
    # Table4: -8.118,+0.680 arcsec/yr and parallax0.449 arcsec.
    ref_ra = WISE_HST[:, 0] + (8.118 * dt - 0.449 * factor_ra) / np.cos(delta) / 3600
    ref_dec = WISE_HST[:, 1] - (0.680 * dt + 0.449 * factor_dec) / 3600
    mean_ra, mean_dec = float(ref_ra.mean()), float(ref_dec.mean())
    reversed_ra = WISE_HST[:, 0] + (8.118 * dt + 0.449 * factor_ra) / np.cos(delta) / 3600
    reversed_dec = WISE_HST[:, 1] - (0.680 * dt - 0.449 * factor_dec) / 3600
    # Independent weighted five-parameter fit to the same six real epochs.
    # Center time near the observations; do not rescale input errors to fit.
    design = np.zeros((12, 5))
    fit_reference = Time(2015.5, format="decimalyear", scale="tt")
    fit_dt = (time - fit_reference).to_value(u.yr)
    design[:6, 0], design[6:, 1] = 1, 1
    design[:6, 2], design[6:, 3] = fit_dt, fit_dt
    design[:6, 4], design[6:, 4] = factor_ra, factor_dec
    values = np.concatenate([(WISE_HST[:, 0] - 133.78) * np.cos(delta) * 3600,
                             (WISE_HST[:, 1] + 7.244) * 3600])
    # Table2 gives 0.025 arcsec for the first HST visit, 0.020 for the others.
    sigma = np.tile([0.025, 0.020, 0.020, 0.020, 0.020, 0.020], 2)
    weighted_design, weighted_values = design / sigma[:, None], values / sigma
    fit, *_ = np.linalg.lstsq(weighted_design, weighted_values, rcond=None)
    covariance = np.linalg.inv(weighted_design.T @ weighted_design)
    fit_errors = np.sqrt(np.diag(covariance))
    residual = (values - design @ fit) / sigma
    # Conservative illustrative input-error budget: the published PM errors
    # accumulate when extrapolating away from the actual HST mean epoch.
    mean_epoch = float(np.mean(time.decimalyear))
    motion_error_2025_mas = [8.0 * abs(2025.8 - mean_epoch), 7.0 * abs(2025.8 - mean_epoch)]
    inferred = SkyCoord(ra=mean_ra * u.deg, dec=mean_dec * u.deg,
                        pm_ra_cosdec=-8118 * u.mas / u.yr, pm_dec=680 * u.mas / u.yr,
                        obstime=reference_time, frame="icrs")
    propagated = inferred.apply_space_motion(new_obstime=Time(2025.8, format="decimalyear", scale="tt"))
    stored = SkyCoord(target.ra_epoch2025 * u.deg, target.dec_epoch2025 * u.deg)
    return {
        "status": "reference_epoch_inconsistent_with_primary_astrometry",
        "source": file_evidence(CACHE / "luhman2016.pdf", WISE_PAPER_URL),
        "citation": "Luhman & Esplin 2016, AJ152:78, Tables2 and4, doi:10.3847/0004-6256/152/3/78",
        "measurements_columns": ["observed_ra_deg", "observed_dec_deg", "mjd_utc"],
        "real_hst_measurements": WISE_HST.tolist(),
        "table4_pm_mas_yr": [-8118.0, 680.0], "table4_parallax_mas": 449.0,
        "inferred_reference_2010_0": {"ra": mean_ra, "dec": mean_dec},
        "scatter_about_inferred_reference_mas": [float(np.std(ref_ra) * np.cos(delta) * 3_600_000),
                                                  float(np.std(ref_dec) * 3_600_000)],
        "opposite_parallax_sign_scatter_mas": [float(np.std(reversed_ra) * np.cos(delta) * 3_600_000),
                                               float(np.std(reversed_dec) * 3_600_000)],
        "independent_hst_only_five_parameter_fit": {
            "fit_epoch_decimalyear": 2015.5,
            "pm_ra_cosdec_mas_yr": float(fit[2] * 1000), "pm_dec_mas_yr": float(fit[3] * 1000),
            "parallax_mas": float(fit[4] * 1000),
            "formal_errors_pmra_pmdec_parallax": list(map(float, fit_errors[2:] * 1000)),
            "chi_square": float(np.sum(residual ** 2)), "degrees_of_freedom": 7,
            "note": "Diagnostic fit only, Earth observer approximation; errors from published Table2 uncertainties, not rescaled by residuals.",
        },
        "published_pm_error_contribution_at_2025_8_mas": motion_error_2025_mas,
        "uncertainty_note": "The 13-16 mas epoch scatter is not total uncertainty. Published PM errors alone contribute roughly80masRA*/70masDec to extrapolation from mean HST epoch to2025.8; calibration frame and observer approximations are additional. This cannot support sub-mas coordinate replacement.",
        "inferred_barycentric_2025_8": {"ra": float(propagated.ra.deg), "dec": float(propagated.dec.deg)},
        "stored_center_separation_arcsec": float(stored.separation(propagated).arcsec),
        "method": "Subtract Table4 linear proper motion and parallax from six Table2 HST positions; use Astropy builtin Earth barycentric ephemeris as HST observer approximation; average inferred2010.0 coordinates. No Spitzer positions are treated as Earth observations.",
        "limitations": "Diagnostic, not a new astrometric solution. HST orbital baseline is omitted; paper coordinates are rounded; tangent-plane parallax removal is approximate. Adopt a published complete solution before changing query coordinates/rebuilding cache. Report barycentric centers separately from date-dependent apparent parallax.",
    }


def audit_wise_published_solution() -> dict:
    path = CACHE / "kirkpatrick2021_plx.tsv"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    # ASU-TSV has a header, units row, dashed separator, then catalogue rows.
    rows = list(csv.DictReader([lines[0], *lines[3:]], delimiter="\t"))
    row = next(row for row in rows if row["PName"].strip() == "0855-0714")
    keys = ["RA_ICRS", "DE_ICRS", "e_RA_ICRS", "e_DE_ICRS", "MJD", "plx", "e_plx",
            "pmRA", "e_pmRA", "pmDE", "e_pmDE", "chisq", "dof", "chisq/dof", "NSp", "NGDR2"]
    values = {key: float(row[key]) for key in keys}
    epoch = Time(values["MJD"], format="mjd", scale="utc")
    coord = SkyCoord(ra=values["RA_ICRS"] * u.deg, dec=values["DE_ICRS"] * u.deg,
                     pm_ra_cosdec=values["pmRA"] * u.mas / u.yr, pm_dec=values["pmDE"] * u.mas / u.yr,
                     obstime=epoch, frame="icrs")
    query_time = Time(2025.8, format="decimalyear", scale="tt")
    propagated = coord.apply_space_motion(new_obstime=query_time)
    at_ref = coord.apply_space_motion(new_obstime=Time(2010.0, format="decimalyear", scale="tt"))
    target = next(target for target in TARGETS if target.id == "wise_0855")
    stored = SkyCoord(target.ra_epoch2025 * u.deg, target.dec_epoch2025 * u.deg)
    dt = (query_time - epoch).to_value(u.yr)
    return {
        "status": "published_solution_confirms_reference_epoch_problem",
        "source": file_evidence(path, WISE_CATALOG_URL), "query_parameters": WISE_CATALOG_PARAMS,
        "citation": "Kirkpatrick et al.2021 ApJS253:7 Table5; doi:10.3847/1538-4365/abd107; CDS J/ApJS/253/7/plx",
        "object": row["FName"].strip(), "quality": row["q_plx"].strip(), "published_values": values,
        "epoch_decimalyear": float(epoch.decimalyear),
        "published_barycentric_2025_8": {"ra": float(propagated.ra.deg), "dec": float(propagated.dec.deg)},
        "published_back_propagated_2010_0": {"ra": float(at_ref.ra.deg), "dec": float(at_ref.dec.deg)},
        "stored_center_separation_arcsec": float(stored.separation(propagated).arcsec),
        "diagonal_only_position_uncertainty_2025_8_mas": [
            float(np.hypot(values["e_RA_ICRS"], dt * values["e_pmRA"])),
            float(np.hypot(values["e_DE_ICRS"], dt * values["e_pmDE"])),
        ],
        "proposed_phase4_source": "Adopt the complete published epoch/coordinate/proper-motion solution together, then regenerate target centers, reticles, traces and cache. No current product value changed by this audit.",
        "limitations": "Barycentric position, not date-dependent apparent location. Parallax439mas is not added; covariance unavailable in this table, so diagonal-only propagated errors are indicative. MJD interpreted asUTC; any time-scale ambiguity is negligible compared with the3.6arcsec discrepancy.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download missing real audit inputs")
    args = parser.parse_args()
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    logging.getLogger("astropy").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=ErfaWarning)
    if args.download:
        download_missing(CACHE / "SPHEREx_Expsupp.pdf", SUPPLEMENT_URL)
        download_missing(CALIBRATION_PATH, CALIBRATION_URL)
        download_missing(CACHE / "gaia.csv", GAIA_URL,
                         {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": GAIA_QUERY})
        download_missing(CACHE / "luhman2016.pdf", WISE_PAPER_URL)
        download_missing(CACHE / "kirkpatrick2021_plx.tsv", WISE_CATALOG_URL, WISE_CATALOG_PARAMS)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "is_real_data_audit": True}
    for name, audit in [("flags", audit_flags), ("wavelengths", audit_wavelengths),
                        ("gaia_targets", audit_gaia_targets), ("wise_reference", audit_wise_reference),
                        ("wise_published_solution", audit_wise_published_solution)]:
        try:
            result[name] = audit()
        except Exception as exc:
            result[name] = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}
        print(name, result[name]["status"])
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 1 if any(value.get("status") == "unavailable" for value in result.values() if isinstance(value, dict)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
