"""Preregistered independent control audit; never writes production or golden data.

Run --register first, --download to retain real catalog responses, then --analyze.
The fixed catalog shortlist is written before any holdout flux is inspected.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys
import warnings

import httpx
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from photutils.aperture import CircularAperture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from core import flags as policy

CACHE = ROOT / "backend/.cache/phase4/science"
PLAN = ROOT / "docs/evidence/phase4/phase4-science-preregistration.json"
RESULT = ROOT / "docs/evidence/phase4/phase4-science-results.json"
LOCK = ROOT / "docs/evidence/phase4/phase4-science-control-lock.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def preserve_result(path, value):
    """Replay can verify a result, but cannot rewrite its measured evidence."""
    if path.exists():
        old = read_json(path)
        comparable = lambda item: {key: val for key, val in item.items() if key != "created_at"}
        if comparable(old) != comparable(value):
            raise ValueError(f"Recorded result changed: {path.name}; use a separately reviewed/versioned report, never overwrite evidence")
        return old
    write_json(path, value)
    return value


def register():
    if PLAN.exists():
        return read_json(PLAN)
    previous = read_json(ROOT / "docs/evidence/phase3/phase3-science-results.json")
    samples = [{key: row[key] for key in ("id", "uri", "path", "sha256", "ra", "dec", "band", "release")}
               for row in previous["samples"] if row["target_id"] == "eps_indi_b" and row["band"] == 3]
    rejected_ids = [row["gaia_source_id"] for field in previous["static_controls"]
                    for row in field["controls"]]
    plan = {
        "registered_at": timestamp(), "status": "frozen_before_holdout_catalog_or_flux_inspection",
        "scope": "Strictly disjoint Gaia sources in recorded Epsilon Indi D3 pair; the shared pair is not an independent detector/systematics sample.",
        "phase3_report_sha256": digest((ROOT / "docs/evidence/phase3/phase3-science-results.json").read_bytes()),
        "samples": samples, "excluded_phase3_source_ids": sorted(set(rejected_ids)),
        "catalog_selection": {
            "gaia_query_radius_deg": .18, "gaia_neighborhood_g_limit": 20,
            "control_g_range": [10, 17], "max_ruwe": 1.4, "max_pm_mas_year": 100,
            "max_abs_parallax_mas": 10, "exclude_gaia_variable": True,
            "target_exclusion_arcsec": 30, "gaia_neighbor_exclusion_arcsec": 30.75,
            "allwise_match_arcsec": 3, "allwise_reference_decimalyear": 2010.5,
            "allwise_neighbor_exclusion_arcsec": 30.75,
            "allwise_quality": "W1/W2 ph_qual A or B, cc_flags00, var_flg digits0or1, ext_flg0, W1/W2 SNR>=10",
            "allwise_neighbors": "All returned source-catalog entries, no magnitude cut; unresolved/subthreshold blends remain possible",
            "max_controls": 20, "ordering": "numeric Gaia source_id ascending; lock first20 catalog-eligible; never replace flux/quality failures",
            "proper_motion": "Propagate controls and Gaia neighbors with measured PM to both FITS epochs; AllWISE match at2010.5. Missing neighbor PM retains catalog position and is counted as a completeness limitation.",
            "field": "Entire31arcsec neighborhood must lie within requested .2degree TAN square in both exposures",
        },
        "measurement_gates": {"complete_aperture_support_both_methods": True,
                              "minimum_clean_annulus_pixels": 10, "require_supported_field_background": True,
                              "minimum_snr_both_methods_both_visits": 5,
                              "minimum_controls": 3, "max_abs_median_z": 1, "max_robust_scatter_z": 2,
                              "max_abs_z": 5, "astrometry_minimum_stars_each_visit": 3,
                              "astrometry_max_robust_rms_arcsec": 1.5375,
                              "spectral_tolerance_narrower_bandwidth": .25, "minimum_bandwidth_ratio": .8},
        "methods": {"center": "distance<=12.3/native_scale_arcsec; weight1",
                    "fractional": "Photutils CircularAperture.to_mask(method=subpixel,subpixels=5)",
                    "annulus": "Same native pixel-center annulus3<=r<=5, excludeSOURCE/hard/warning, median; N>=10 mandatory",
                    "background_variance": "max[(pi/2)*mean(V_ann)/N_ann,(1.2533*MAD_scaled_ann)^2/N_ann]",
                    "flux": "1e12*Omega*sum(w*(I-background))",
                    "variance": "(1e12*Omega)^2*(sum(w^2*V)+sum(w)^2*background_variance)",
                    "unmodeled": "Detector/plane covariance, aperture correction, PSF variations, unresolved companions and infrared variability; no absolute calibrated-flux claim"},
        "failure_policy": "No threshold relaxation, no residual-based rejection, no replacement of unavailable inputs. Fewer than3 controls or failed prerequisite => insufficient, not pass.",
        "independence": "Excluded all Phase3controlIDs; no flux of new controls has been inspected. Samefield residual systematics may persist; validation does not generalize to all bands.",
    }
    write_json(PLAN, plan)
    print(json.dumps({"registered": str(PLAN.relative_to(ROOT)), "sha256": digest(PLAN.read_bytes())}), flush=True)
    return plan


def table_rows(content):
    # Trailing QUERY_STATUS is significant: never accept silently truncated catalogs.
    import xml.etree.ElementTree as ET
    tree = ET.fromstring(content)
    for node in tree.iter():
        if node.tag.rsplit("}", 1)[-1] == "INFO" and node.attrib.get("name", "").upper() == "QUERY_STATUS":
            if node.attrib.get("value", "").upper() in {"ERROR", "OVERFLOW"}:
                raise ValueError("Incomplete catalog: " + (node.text or node.attrib["value"]))
    table = parse_single_table(BytesIO(content)).to_table()
    if len(table) >= 20000:
        raise ValueError("Catalog row cap reached")
    rows = []
    for row in table:
        values = {}
        for key in table.colnames:
            value = row[key]
            if np.ma.is_masked(value):
                value = None
            elif key.lower() in {"source_id", "designation", "ph_qual", "cc_flags", "var_flg", "phot_variable_flag"}:
                value = str(value)
            elif isinstance(value, (np.integer, int)):
                value = int(value)
            elif isinstance(value, (np.floating, float)):
                value = float(value) if np.isfinite(value) else None
            else:
                value = str(value)
            values[key.lower()] = value
        rows.append(values)
    return rows


def queries(plan):
    ra, dec = plan["samples"][0]["ra"], plan["samples"][0]["dec"]
    cone = f"1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},0.18))"
    return {
        "gaia": ("https://gea.esac.esa.int/tap-server/tap/sync",
                 "SELECT TOP 20000 source_id,ra,dec,ref_epoch,pmra,pmdec,parallax,ruwe,phot_g_mean_mag,phot_variable_flag FROM gaiadr3.gaia_source WHERE " + cone + " AND phot_g_mean_mag<=20 ORDER BY source_id"),
        "allwise": ("https://irsa.ipac.caltech.edu/TAP/sync",
                    "SELECT TOP 20000 designation,ra,dec,w1mpro,w2mpro,w1snr,w2snr,ph_qual,cc_flags,var_flg,ext_flg FROM allwise_p3as_psd WHERE " + cone + " ORDER BY designation"),
    }


def download(plan):
    CACHE.mkdir(parents=True, exist_ok=True)
    previous = read_json(CACHE / "catalogs.json") if (CACHE / "catalogs.json").exists() else {}
    outcomes = {}
    for name, (url, query) in queries(plan).items():
        path = CACHE / (name + ".xml")
        try:
            if not path.exists():
                params = {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": query}
                if name == "allwise" and previous.get(name, {}).get("status") == "unavailable":
                    # Same official catalog, fields and cone through documented alternate transport.
                    sample = plan["samples"][0]
                    url = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
                    params = {"catalog": "allwise_p3as_psd", "spatial": "Cone", "objstr": f"{sample['ra']} {sample['dec']}",
                              "radius": "10.8", "radunits": "arcmin", "outfmt": "3",
                              "selcols": "designation,ra,dec,w1mpro,w2mpro,w1snr,w2snr,ph_qual,cc_flags,var_flg,ext_flg"}
                response = httpx.get(url, params=params, timeout=60, follow_redirects=True)
                response.raise_for_status()
                table_rows(response.content)
                path.write_bytes(response.content)
            content = path.read_bytes()
            outcomes[name] = {"status": "downloaded", "url": url, "query": query,
                              "path": path.relative_to(ROOT).as_posix(), "sha256": digest(content),
                              "bytes": len(content), "rows": len(table_rows(content)), "retrieved_at": timestamp()}
            if previous.get(name, {}).get("sha256") == digest(content):
                outcomes[name] = previous[name]
            elif previous.get(name, {}).get("status") == "unavailable":
                outcomes[name]["prior_attempt"] = previous[name]
                outcomes[name]["actual_parameters"] = params
        except Exception as exc:
            outcomes[name] = {"status": "unavailable", "url": url, "query": query, "error": str(exc)}
        print(json.dumps({name: outcomes[name]}), flush=True)
    write_json(CACHE / "catalogs.json", outcomes)


def position(row, epoch):
    coord = SkyCoord(ra=float(row["ra"])*u.deg, dec=float(row["dec"])*u.deg,
                     pm_ra_cosdec=float(row.get("pmra") or 0)*u.mas/u.yr,
                     pm_dec=float(row.get("pmdec") or 0)*u.mas/u.yr,
                     obstime=Time(float(row.get("ref_epoch") or 2016), format="jyear", scale="tcb"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        moved = coord.apply_space_motion(new_obstime=epoch)
    return SkyCoord(moved.ra, moved.dec)


def weights(shape, x, y, radius, method):
    if method == "center":
        yy, xx = np.indices(shape)
        return (np.hypot(xx-x, yy-y) <= radius).astype(float)
    if method != "fractional":
        raise ValueError("Unknown aperture method")
    aperture = CircularAperture((x, y), r=radius)
    return aperture.to_mask(method="subpixel", subpixels=5).to_image(shape)


def measure(parsed, method):
    """Independent comparison implementation, with weighted variance/background."""
    image, variance, flags = parsed.image_mjy_sr, parsed.variance_mjy_sr2, parsed.flags
    if min(parsed.target_x, parsed.target_y, image.shape[1]-1-parsed.target_x, image.shape[0]-1-parsed.target_y) < 5.5:
        return {"method": method, "flux_ujy": None, "error_ujy": None, "reason": "annulus_or_aperture_outside_image"}
    good = np.isfinite(image) & np.isfinite(variance) & (variance > 0) & ((flags & policy.PHOTOMETRY_EXCLUDE_MASK) == 0)
    yy, xx = np.indices(image.shape)
    radius = np.hypot(xx-parsed.target_x, yy-parsed.target_y)
    annulus = (radius >= 3) & (radius <= 5) & good & ((flags & policy.BIT_SOURCE) == 0)
    weight = weights(image.shape, parsed.target_x, parsed.target_y, 12.3/parsed.native_pixel_scale_arcsec, method)
    support = weight > 0
    result = {"method": method, "annulus_pixels": int(annulus.sum()), "weighted_area_pixels": float(weight.sum()),
              "clean_fraction": float(weight[good].sum()/weight.sum()), "background_supported": bool((parsed.background_metadata or {}).get("subtracted", False)),
              "flux_ujy": None, "error_ujy": None}
    if not result["background_supported"]:
        return dict(result, reason="unsupported_field_background")
    if not np.all(good[support]):
        return dict(result, reason="incomplete_aperture_support")
    if annulus.sum() < 10:
        return dict(result, reason="insufficient_clean_annulus")
    background = float(np.median(image[annulus]))
    scatter = 1.4826 * float(np.median(np.abs(image[annulus]-background)))
    bgvariance = max((math.pi/2)*float(np.mean(variance[annulus]))/int(annulus.sum()),
                     1.2533**2*scatter**2/int(annulus.sum()))
    conversion = 1e12*(parsed.native_pixel_scale_arcsec*np.pi/(180*3600))**2
    flux = float(np.sum(weight[support]*(image[support]-background))*conversion)
    var = float(np.sum(weight[support]**2*variance[support]) + weight.sum()**2*bgvariance)
    error = math.sqrt(var)*conversion
    return dict(result, flux_ujy=flux, error_ujy=error, snr=flux/error,
                annulus_background_mjy_sr=background, annulus_background_variance_mjy_sr2=bgvariance)


def stability(rows, method):
    z = [(row["measurements"][1][method]["flux_ujy"]-row["measurements"][0][method]["flux_ujy"])/
         math.hypot(row["measurements"][0][method]["error_ujy"], row["measurements"][1][method]["error_ujy"]) for row in rows]
    if len(z) < 3:
        return {"status": "insufficient", "controls": len(z), "z": z}
    median = float(np.median(z))
    scatter = float(1.4826*np.median(np.abs(np.asarray(z)-median)))
    maximum = max(abs(value) for value in z)
    return {"status": "pass" if abs(median) <= 1 and scatter <= 2 and maximum <= 5 else "failed",
            "controls": len(z), "median_z": median, "robust_scatter_z": scatter, "max_abs_z": maximum, "z": z}


def load_inputs(plan):
    contents, headers = [], []
    for sample in plan["samples"]:
        content = (ROOT / sample["path"]).read_bytes()
        if digest(content) != sample["sha256"]:
            raise ValueError("Real input hash mismatch")
        contents.append(content)
        with fits.open(BytesIO(content), memmap=False) as hdul:
            headers.append(dict(hdul["IMAGE"].header))
    return contents, headers


def select_controls(plan, gaia, allwise, headers):
    from services.spherex_pipeline import output_wcs
    center = plan["samples"][0]
    wcs = output_wcs(center["ra"], center["dec"])
    times = [Time(header["MJD-AVG"], format="mjd", scale=header.get("TIMESYS", "UTC").lower()) for header in headers]
    moved = [[position(row, epoch) for row in gaia] for epoch in times]
    arrays = [SkyCoord(ra=[p.ra.deg for p in positions]*u.deg, dec=[p.dec.deg for p in positions]*u.deg) for positions in moved]
    ircoords = SkyCoord(ra=[row["ra"] for row in allwise]*u.deg, dec=[row["dec"] for row in allwise]*u.deg)
    centercoord = SkyCoord(center["ra"], center["dec"], unit="deg")
    shortlist, rejected = [], Counter()
    for index in sorted(range(len(gaia)), key=lambda i: int(gaia[i]["source_id"])):
        row = gaia[index]
        if row["source_id"] in plan["excluded_phase3_source_ids"]:
            rejected["phase3_control"] += 1
            continue
        if any(row.get(key) is None for key in ("pmra", "pmdec", "ruwe", "parallax", "phot_g_mean_mag")):
            rejected["missing_gaia_quality"] += 1
            continue
        if not (10 <= row["phot_g_mean_mag"] <= 17 and row["ruwe"] <= 1.4 and math.hypot(row["pmra"],row["pmdec"]) <= 100 and abs(row["parallax"]) <= 10 and row.get("phot_variable_flag") != "VARIABLE"):
            rejected["gaia_quality"] += 1
            continue
        coords = [positions[index] for positions in moved]
        pixels = [wcs.world_to_pixel(coord) for coord in coords]
        # 31arcsec guard is fixed before flux; native annulus and neighbors stay inside the matched field.
        if any(max(abs(float(x)-119.5), abs(float(y)-119.5))*3.075+31 > 360 for x,y in pixels):
            rejected["outside_guarded_field"] += 1
            continue
        if any(coord.separation(centercoord).arcsec < 30 for coord in coords):
            rejected["target_proximity"] += 1
            continue
        distances = [coord.separation(array).arcsec for coord,array in zip(coords,arrays)]
        for values in distances:
            values[index] = np.inf
        nearest = min(float(np.min(values)) for values in distances)
        if nearest < 30.75:
            rejected["gaia_neighbor"] += 1
            continue
        irpos = position(row, Time(2010.5, format="decimalyear", scale="utc"))
        irsep = irpos.separation(ircoords).arcsec
        matches = np.where(irsep <= 3)[0]
        if len(matches) != 1:
            rejected["allwise_match_missing_or_ambiguous"] += 1
            continue
        matchindex = int(matches[0])
        ir = allwise[matchindex]
        othersep = ircoords[matchindex].separation(ircoords).arcsec
        othersep[matchindex] = np.inf
        if float(np.min(othersep)) < 30.75:
            rejected["allwise_neighbor"] += 1
            continue
        var = str(ir.get("var_flg") or "")
        ph = str(ir.get("ph_qual") or "")
        if not (len(var) >= 2 and all(c in "01" for c in var[:2]) and len(ph) >= 2 and all(c in "AB" for c in ph[:2])
                and str(ir.get("cc_flags") or "")[:2] == "00" and ir.get("ext_flg") == 0
                and (ir.get("w1snr") or 0) >= 10 and (ir.get("w2snr") or 0) >= 10):
            rejected["allwise_quality_or_unknown_variability"] += 1
            continue
        shortlist.append({"gaia": row, "allwise": ir, "positions": [{"ra": c.ra.deg, "dec": c.dec.deg, "mjd": float(t.mjd), "timescale": t.scale} for c,t in zip(coords,times)],
                          "nearest_gaia_arcsec": nearest, "allwise_match_arcsec": float(irsep[matchindex]), "nearest_allwise_arcsec": float(np.min(othersep))})
        if len(shortlist) == 20:
            break
    return shortlist, dict(rejected)


def analyze(plan):
    report = {"created_at": timestamp(), "preregistration_sha256": digest(PLAN.read_bytes()),
              "status": "insufficient", "production_method_changed": False, "golden_modified": False,
              "controls": [], "limitations": ["Catalog screening does not certify infrared constancy or exclude unresolved/faint blends.",
                                                "Disjoint sources share the earlier exposure pair; independent of prior control fluxes, not independent of detector systematics.",
                                                "WCS-WAVE matching is approximate; D3 CWAVE/CBAND calibration still required."]}
    try:
        provenance = read_json(CACHE / "catalogs.json")
        report["catalogs"] = provenance
        if any(provenance.get(name, {}).get("status") != "downloaded" for name in ("gaia", "allwise")):
            raise ValueError("Required fresh Gaia/AllWISE screening unavailable")
        catalogs = {}
        for name in ("gaia", "allwise"):
            content = (ROOT / provenance[name]["path"]).read_bytes()
            if digest(content) != provenance[name]["sha256"]:
                raise ValueError("Catalog hash mismatch")
            catalogs[name] = table_rows(content)
        contents, headers = load_inputs(plan)
        report["input_headers"] = [{key: header.get(key) for key in ("DATE-OBS", "MJD-AVG", "TIMESYS")} for header in headers]
        shortlist, rejection = select_controls(plan, catalogs["gaia"], catalogs["allwise"], headers)
        lock = {"preregistration_sha256": report["preregistration_sha256"],
                "catalog_hashes": {name: provenance[name]["sha256"] for name in provenance},
                "shortlist": shortlist, "catalog_rejections": rejection}
        if LOCK.exists():
            if read_json(LOCK) != lock:
                raise ValueError("Locked control selection changed; require a new preregistration")
        else:
            write_json(LOCK, lock)
        report["control_lock_sha256"] = digest(LOCK.read_bytes())
        report["catalog_rejections"] = rejection
        report["catalog_selected_count"] = len(shortlist)
        report["gaia_neighbors_without_proper_motion"] = sum(row.get("pmra") is None or row.get("pmdec") is None for row in catalogs["gaia"])
        from services.live_selection import dense_spectral_signature, compatible
        from services.spherex_pipeline import parse_cutout
        sample = plan["samples"][0]
        signatures = [dense_spectral_signature(content, sample["ra"], sample["dec"], .2) for content in contents]
        report["wcs_wave_dense_compatibility"] = {"passed": compatible(*signatures), "pixels": signatures[0].shape[1],
                                                 "calibration": "approximate WCS-WAVE; independent CWAVE pending"}
        if not report["wcs_wave_dense_compatibility"]["passed"]:
            raise ValueError("Holdout pair fails dense wavelength matching")
        for row in shortlist:
            record = {"gaia_source_id": row["gaia"]["source_id"], "measurements": []}
            for content, position_value in zip(contents, row["positions"]):
                parsed = parse_cutout(content, position_value["ra"], position_value["dec"])
                values = {method: measure(parsed, method) for method in ("center", "fractional")}
                record["measurements"].append(values)
            record["eligible"] = all(value.get("snr", 0) >= 5 for visit in record["measurements"] for value in visit.values())
            report["controls"].append(record)
        eligible = [row for row in report["controls"] if row["eligible"]]
        report["stability"] = {method: stability(eligible, method) for method in ("center", "fractional")}
        report["astrometry"] = {"status": "not_established", "reason": "D1 Phase3 validation cannot certify this D3 pair; independent D3 centroids required"}
        report["reason"] = "No promotion: require sufficient independent controls, D3 external astrometry, calibrated wavelength matching and reviewed method adoption"
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    preserve_result(RESULT, report)
    print(json.dumps({"status": report["status"], "selected": report.get("catalog_selected_count"), "stability": report.get("stability"), "error": report.get("error")}), flush=True)
    return report


def coordinate_profile():
    """Derive staged directions from complete primary catalog solutions."""
    import csv
    from phase3_calibration_audit import audit_wise_published_solution
    evidence = read_json(ROOT / "docs/evidence/phase3/phase3-calibration-audit.json")
    for entry in (evidence["gaia_targets"]["source"], evidence["wise_published_solution"]["source"]):
        if digest((ROOT / entry["path"]).read_bytes()) != entry["sha256"]:
            raise ValueError("Primary coordinate catalog hash mismatch")
    primary_wise = audit_wise_published_solution()
    values = primary_wise["published_values"]
    wise = {"target_id": "wise_0855", "reference_ra_deg": values["RA_ICRS"],
            "reference_dec_deg": values["DE_ICRS"],
            "reference_time": {"value": values["MJD"], "format": "mjd", "scale": "utc", "scale_caveat": "Publication epoch scale not explicit in table; UTC convention retained; negligible relative to positional uncertainty"},
            "pm_ra_cosdec_mas_yr": values["pmRA"], "pm_dec_mas_yr": values["pmDE"],
            "parallax_mas_metadata_only": values["plx"], "source": evidence["wise_published_solution"]["source"],
            "citation": primary_wise["citation"], "caveat": "Full fit covariance unavailable; no observer-parallax or perspective correction"}
    mapping = {row["source_id"]: row["target_id"] for row in evidence["gaia_targets"]["targets"]}
    source = evidence["gaia_targets"]["source"]
    rows = list(csv.DictReader((ROOT / source["path"]).read_text(encoding="utf-8").splitlines()))
    targets = [wise]
    for row in rows:
        targets.append({"target_id": mapping[row["source_id"]], "source_id": row["source_id"],
                        "reference_ra_deg": float(row["ra"]), "reference_dec_deg": float(row["dec"]),
                        "reference_time": {"value": float(row["ref_epoch"]), "format": "jyear", "scale": "tcb"},
                        "pm_ra_cosdec_mas_yr": float(row["pmra"]), "pm_dec_mas_yr": float(row["pmdec"]),
                        "parallax_mas_metadata_only": float(row["parallax"]), "ruwe": float(row["ruwe"]),
                        "source": source, "citation": "Gaia DR3 gaiadr3.gaia_source; exact source_id and query retained in Phase3 audit",
                        "caveat": "Unresolved infrared photocenter may differ; Epsilon Indi highRUWE4.30/binary and RW Aur binary/variable especially limit precision"})
    for target in targets:
        epoch = target["reference_time"]
        reference = Time(epoch["value"], format=epoch["format"], scale=epoch["scale"])
        coord = SkyCoord(ra=target["reference_ra_deg"]*u.deg, dec=target["reference_dec_deg"]*u.deg,
                         pm_ra_cosdec=target["pm_ra_cosdec_mas_yr"]*u.mas/u.yr,
                         pm_dec=target["pm_dec_mas_yr"]*u.mas/u.yr, obstime=reference, frame="icrs")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            moved = coord.apply_space_motion(new_obstime=Time(2025.8, format="decimalyear", scale="tt"))
        target["query_2025_8_tt"] = {"ra_deg": float(moved.ra.deg), "dec_deg": float(moved.dec.deg)}
        target["display_reference_epoch"] = str(reference.decimalyear) if epoch["format"] == "mjd" else "J2016.0"
    result = {"created_at": timestamp(), "status": "proposed_staged_profile_not_promoted", "frame": "ICRS",
              "propagation": "Astropy apply_space_motion; angular barycentric direction only. Parallax retained as source metadata, not applied; no radial velocity/perspective acceleration.",
              "time_warning": "Preserve format+scale internally. J2016.0 TCB is not decimalyear2016.0 TT; do not replace exactMJD with rounded label.",
              "targets": targets}
    write_json(ROOT / "docs/evidence/phase4/phase4-science-coordinate-profile.json", result)
    print(json.dumps({"coordinate_profile": [{"target_id": t["target_id"], **t["query_2025_8_tt"]} for t in targets]}), flush=True)
    return result


def independent_astrometry(content, rows, center_ra, center_dec):
    from astropy.wcs import WCS
    from astropy.wcs.utils import proj_plane_pixel_scales
    from phase3_astrometry import detect, propagate, summary
    with fits.open(BytesIO(content), memmap=False) as hdul:
        image = np.asarray(hdul["IMAGE"].data, float)-np.asarray(hdul["ZODI"].data, float)
        variance = np.asarray(hdul["VARIANCE"].data, float)
        flags = np.asarray(hdul["FLAGS"].data, np.uint32)
        header = hdul["IMAGE"].header.copy()
    spatial = WCS(header)
    output = WCS(naxis=2)
    output.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    output.wcs.crval = [center_ra, center_dec]
    output.wcs.crpix = [120.5, 120.5]
    output.wcs.cdelt = [-.0008541667, .0008541667]
    scale = float(np.mean(proj_plane_pixel_scales(spatial))*3600)
    peaks = detect(image, variance, (flags & policy.PHOTOMETRY_EXCLUDE_MASK) != 0, scale)
    moved, valid, missing = propagate(rows, header["MJD-AVG"], header.get("TIMESYS", "UTC").lower())
    matches, rejected = [], Counter()
    if peaks:
        sky = spatial.pixel_to_world([p["x"] for p in peaks], [p["y"] for p in peaks])
        indices, distance, _ = sky.match_to_catalog_sky(moved)
        multiplicities = Counter(int(index) for index, separation in zip(indices,distance) if separation.arcsec <= 12.3)
        for peak,index,separation,coord in zip(peaks,indices,distance,sky):
            if separation.arcsec > 12.3 or multiplicities[int(index)] != 1:
                rejected["unmatched_or_ambiguous"] += 1
                continue
            row = valid[int(index)]
            field_x, field_y = output.world_to_pixel(moved[int(index)])
            if max(abs(float(field_x)-119.5), abs(float(field_y)-119.5))*.0008541667 > .1:
                rejected["outside_requested_field"] += 1
                continue
            if (any(row.get(k) is None for k in ("ruwe", "parallax", "phot_g_mean_mag")) or row["ruwe"] > 1.4
                    or abs(row["parallax"]) > 10 or row["phot_g_mean_mag"] > 17):
                rejected["catalog_quality"] += 1
                continue
            neighbors = moved[int(index)].separation(moved).arcsec
            if np.count_nonzero(neighbors < 30.75) > 1:
                rejected["neighbor"] += 1
                continue
            dra, ddec = moved[int(index)].spherical_offsets_to(coord)
            matches.append({"gaia_source_id": row["source_id"], "native_dra_cosdec_arcsec": float(dra.arcsec),
                            "native_ddec_arcsec": float(ddec.arcsec), "centroid": peak})
    return {"summary": summary(matches,"native"), "matches": matches, "rejections": dict(rejected),
            "gaia_missing_pm": missing, "detected_peaks": len(peaks),
            "method": "Independent10sigma local maxima and ellipticalGaussian centroids; no fitting towardGaia; catalogG<=17,RUWE<=1.4,|parallax|<=10mas,neighbors>=30.75arcsec; associations12.3arcsec; no residual clipping",
            "scope": "Native D3 stars within requested .2degree TAN field, not padded perimeter or golden coadds; freshG<=20Gaia neighborhood; missingPM rows would leave isolation incomplete"}


def calibration_prerequisite(plan, contents):
    from astropy.wcs import WCS
    from scipy.ndimage import map_coordinates
    from services.live_selection import compatible
    url = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/dr1/spectral_wcs/cal-swcs-v5-2026-191/3/spectral_wcs_D3_spx_cal-swcs-v5-2026-191.fits"
    path = CACHE / "spectral_wcs_D3_spx_cal-swcs-v5-2026-191.fits"
    if not path.exists():
        import time
        started = time.monotonic()
        chunks = []
        count = 0
        with httpx.stream("GET", url, timeout=35, follow_redirects=True) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                count += len(chunk)
                if count > 40_000_000 or time.monotonic()-started > 60:
                    raise ValueError("Calibration exceeds bounded transfer")
                chunks.append(chunk)
        data = b"".join(chunks)
        with fits.open(BytesIO(data), memmap=False) as hdul:
            if not {"CWAVE", "CBAND", "WCS-WAVE"}.issubset({h.name for h in hdul}):
                raise ValueError("Required calibration extensions missing")
        path.write_bytes(data)
    source = {"url": url, "path": path.relative_to(ROOT).as_posix(), "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
    sample = plan["samples"][0]
    grid = WCS(naxis=2)
    grid.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    grid.wcs.crval = [sample["ra"], sample["dec"]]
    grid.wcs.crpix = [120.5, 120.5]
    grid.wcs.cdelt = [-.0008541667, .0008541667]
    yy, xx = np.mgrid[3:237,3:237]
    world = grid.pixel_to_world(xx.ravel(), yy.ravel())
    signatures, details = [], []
    with fits.open(path, memmap=False) as calibration:
        wave, band = np.asarray(calibration["CWAVE"].data,float), np.asarray(calibration["CBAND"].data,float)
        for sample,content in zip(plan["samples"], contents):
            with fits.open(BytesIO(content), memmap=False) as hdul:
                header = hdul["IMAGE"].header
                same_table = all(np.array_equal(hdul["WCS-WAVE"].data[name],calibration["WCS-WAVE"].data[name]) for name in ("X","Y","VALUES"))
                same_orientation = header.get("DETCOORD") == calibration["CWAVE"].header.get("DETCOORD") == "sky"
                if not same_table or not same_orientation or int(header["DETECTOR"]) != 3:
                    raise ValueError("Calibration pairing/orientation not verified")
                spatial = WCS(header)
                x,y = spatial.world_to_pixel(world)
                xo,yo = 1+x-header["CRPIX1A"], 1+y-header["CRPIX2A"]
                calibrated = np.array([map_coordinates(array,[yo,xo],order=1,mode="constant",cval=np.nan) for array in (wave,band)])
                lookup = WCS(header,fobj=hdul,key="W"); lookup.sip = None
                approximate = np.asarray(lookup.pixel_to_world_values(x,y))
                signatures.append(calibrated)
                details.append({"sample_id": sample["id"], "wcs_wave_arrays_identical": same_table,
                                "orientation": "sky", "max_lookup_wave_error_nm": float(np.max(np.abs(calibrated[0]-approximate[0]))*1000),
                                "max_lookup_bandwidth_error_nm": float(np.max(np.abs(calibrated[1]-approximate[1]))*1000)})
    return {"status": "pass" if compatible(*signatures) else "failed", "source": source, "samples": details,
            "retained_pixel_centers": int(xx.size), "method": "CWAVE/CBAND bilinear sampling at eachoutputcenter mappedthroughspatialWCS and originaldetector x=1+xcut-CRPIX1A; releaseD3/sky/exactX,Y,VALUES matching verified; same quarterwidth/.8bandwidthgate",
            "maximum_center_separation_fraction_narrower_bandwidth": float(np.max(np.abs(signatures[0][0]-signatures[1][0])/np.minimum(signatures[0][1],signatures[1][1]))),
            "minimum_bandwidth_ratio": float(np.min(np.minimum(signatures[0][1],signatures[1][1])/np.maximum(signatures[0][1],signatures[1][1]))),
            "limitation": "Perpixel calibration interpolation, not identicalfullfilterresponse or PSF matching; no universalallband validation"}


def prerequisites(plan):
    contents, _ = load_inputs(plan)
    rows = table_rows((CACHE / "gaia.xml").read_bytes())
    result = {"created_at": timestamp(), "input_sha256": [sample["sha256"] for sample in plan["samples"]],
              "gaia_sha256": digest((CACHE / "gaia.xml").read_bytes()), "astrometry": []}
    for sample,content in zip(plan["samples"],contents):
        try:
            measured = independent_astrometry(content,rows,sample["ra"],sample["dec"])
            result["astrometry"].append(dict(measured,sample_id=sample["id"]))
        except Exception as exc:
            result["astrometry"].append({"sample_id":sample["id"],"status":"unavailable","error":str(exc)})
    try:
        result["calibration"] = calibration_prerequisite(plan,contents)
    except Exception as exc:
        result["calibration"] = {"status": "unavailable", "error": str(exc)}
    write_json(ROOT / "docs/evidence/phase4/phase4-science-prerequisites.json",result)
    print(json.dumps({"astrometry": [row.get("summary",row.get("status")) for row in result["astrometry"]],"calibration": result["calibration"]}),flush=True)
    return result


SEARCH_PLAN = ROOT / "docs/evidence/phase4/phase4-science-search-preregistration.json"


def register_search():
    if SEARCH_PLAN.exists():
        return read_json(SEARCH_PLAN)
    astrometry = read_json(ROOT / "docs/evidence/phase3/phase3-astrometry-results.json")
    original = read_json(PLAN)
    candidates = []
    for target in ("wise_0855", "r_draconis", "barnards_star", "rw_aurigae"):
        exposures = next(row["exposures"] for row in astrometry["targets"] if row["target"] == target)
        manifest = read_json(ROOT / "golden_cache" / target / "manifest.json")
        samples = []
        for index, exposure in enumerate(exposures):
            samples.append({"id": f"{target}_D1_holdout_{index}", "uri": exposure["uri"],
                            "path": exposure["fits"]["cache"], "sha256": exposure["fits"]["sha256"],
                            "ra": manifest["query"]["ra"], "dec": manifest["query"]["dec"], "band": 1,
                            "release": "DR1" if "/dr1/" in exposure["uri"] else "QR3"})
        candidates.append({"target": target, "samples": samples})
    value = {"registered_at": timestamp(), "status": "frozen_before_new_candidate_control_flux_inspection",
             "previous_empty_result_sha256": digest(RESULT.read_bytes()), "inherited_protocol_sha256": digest(PLAN.read_bytes()),
             "protocol": original, "candidates_in_fixed_order": candidates,
             "selection": "Recorded first/lastD1 pair perfield, fixedorder WISE,RDraconis,Barnard,RWAur. Screen9points withincentral.12deg usingexistingrealcutouts; incompatiblepair rejected beforecatalog/flux. Ifcoarsepasses, obtainpadded.2degcutouts anddensevalidateactual.2deggrid, thenapplyUNCHANGEDGaia/AllWISEselection. Firstpairwith>=3catalogeligiblecontrols islocked beforeflux; no substitution afterflux failures. Stopafter4pairs.",
             "astrometry_independence": "Phase3D1astrometry may have inspectedthese images globally, but no Phase4heldout-source aperture fluxes wereused. AllPhase3controlIDs remainexcluded.",
             "thresholds": "All sourcequality/isolation/photometry/astrometry gates inherited unchanged; neverrelax toobtaincontrols"}
    write_json(SEARCH_PLAN, value)
    print(json.dumps({"search_registered": str(SEARCH_PLAN.relative_to(ROOT)), "sha256": digest(SEARCH_PLAN.read_bytes())}), flush=True)
    return value


def search_holdout():
    global CACHE, PLAN, RESULT, LOCK
    from services.live_selection import spectral_signature, compatible, dense_spectral_signature
    from services.irsa_client import ArtifactRecord, IrsaClient
    from core.config import Settings
    import time
    search = read_json(SEARCH_PLAN)
    original_paths = CACHE, PLAN, RESULT, LOCK
    outcomes = []
    for candidate in search["candidates_in_fixed_order"]:
        result = {"target": candidate["target"], "status": "not_selected"}
        outcomes.append(result)
        try:
            inherited = dict(search["protocol"], samples=candidate["samples"])
            content, headers = load_inputs(inherited)
            sample = candidate["samples"][0]
            signatures = [spectral_signature(item, sample["ra"], sample["dec"], .12) for item in content]
            result["coarse_compatibility"] = compatible(*signatures)
            result["center_wavelength_um"] = [float(s[0,4]) for s in signatures]
            result["center_bandwidth_um"] = [float(s[1,4]) for s in signatures]
            if not result["coarse_compatibility"]:
                result["reason"] = "Recorded pair fails wavelength screening; no control flux extracted"
                continue
            # Broader padded downloads are used only for geometry-qualified pairs.
            CACHE = ROOT / "backend/.cache/phase4/science" / candidate["target"]
            padded_samples, padded_content = [], []
            for sample, header in zip(candidate["samples"], headers):
                record = ArtifactRecord(sample["uri"], float(header["MJD-AVG"]), None, 1, "SPHEREx-D1", sample["id"], sample["release"], "spherex_"+sample["release"].lower())
                client = IrsaClient(replace(Settings(), cache_dir=CACHE, retries=1), deadline_at=time.monotonic()+55)
                size = math.sqrt(2)*.2 + 2*6.15/3600
                data = client.fetch_cutout(record, sample["ra"], sample["dec"], size)
                path = client._cutout_cache_path(record, sample["ra"], sample["dec"], size)
                padded_samples.append(dict(sample, path=path.relative_to(ROOT).as_posix(), sha256=digest(data)))
                padded_content.append(data)
            result["padded_samples"] = padded_samples
            dense = [dense_spectral_signature(data, sample["ra"], sample["dec"], .2) for data in padded_content]
            result["dense_compatibility"] = compatible(*dense)
            if not result["dense_compatibility"]:
                result["reason"] = "Densefield spectral gate failed; no control flux extracted"
                continue
            candidate_plan = dict(inherited, samples=padded_samples, parent_search_sha256=digest(SEARCH_PLAN.read_bytes()))
            PLAN = ROOT / f"docs/evidence/phase4/phase4-science-search-{candidate['target']}-protocol.json"
            RESULT = ROOT / f"docs/evidence/phase4/phase4-science-search-{candidate['target']}-results.json"
            LOCK = ROOT / f"docs/evidence/phase4/phase4-science-search-{candidate['target']}-control-lock.json"
            if PLAN.exists() and read_json(PLAN) != candidate_plan:
                raise ValueError("Frozen search candidate metadata changed")
            if not PLAN.exists():
                write_json(PLAN, candidate_plan)
            download(candidate_plan)
            metadata = read_json(CACHE / "catalogs.json")
            if metadata["allwise"]["status"] == "unavailable":
                download(candidate_plan)  # Same-data Gator fallback, bounded once.
            analysis = analyze(candidate_plan)
            result.update(status=analysis["status"], result_file=RESULT.relative_to(ROOT).as_posix(),
                          catalog_selected_count=analysis.get("catalog_selected_count"), stability=analysis.get("stability"))
            if analysis.get("catalog_selected_count", 0) >= 3:
                result["selection_locked"] = True
                break
        except Exception as exc:
            result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            CACHE, PLAN, RESULT, LOCK = original_paths
        print(json.dumps(result), flush=True)
    summary = {"created_at": timestamp(), "search_preregistration_sha256": digest(SEARCH_PLAN.read_bytes()),
               "status": "insufficient", "candidates": outcomes,
               "reason": "No production adoption without passing independent control and calibration/astrometry gates"}
    preserve_result(ROOT / "docs/evidence/phase4/phase4-science-search-results.json", summary)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--coordinates", action="store_true")
    parser.add_argument("--register-search", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--prerequisites", action="store_true")
    args = parser.parse_args()
    if args.register:
        register()
    if not PLAN.exists():
        parser.error("Run --register before data acquisition or analysis")
    plan = read_json(PLAN)
    if args.download:
        download(plan)
    if args.analyze:
        analyze(plan)
    if args.coordinates:
        coordinate_profile()
    if args.register_search:
        register_search()
    if args.search:
        search_holdout()
    if args.prerequisites:
        prerequisites(plan)


if __name__ == "__main__":
    main()
