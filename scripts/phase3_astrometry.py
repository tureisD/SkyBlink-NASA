"""Independent Gaia-versus-image centroid audit; never modifies golden data.

Raw FITS downloads and fresh Gaia catalog responses live only in the ignored
backend/.cache/phase3/astrometry directory. Generated Gaussian arrays exist
only in isolated algorithm tests, never in this audit's measurements.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
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
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from reproject import reproject_interp
from scipy.ndimage import maximum_filter
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from core.flags import FLAG_VALUES, PHOTOMETRY_EXCLUDE_MASK  # noqa: E402

TARGETS = ["wise_0855", "barnards_star", "eps_indi_b", "rw_aurigae", "r_draconis"]
CACHE = ROOT / "backend/.cache/phase3/astrometry"
THRESHOLD_ARCSEC = 1.5375


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch(url: str, *, params: dict | None = None, suffix: str) -> tuple[bytes, dict]:
    identity = url + json.dumps(params or {}, sort_keys=True)
    cached = CACHE / (digest(identity.encode()) + suffix)
    CACHE.mkdir(parents=True, exist_ok=True)
    if cached.exists():
        content = cached.read_bytes()
        return content, {"url": url, "params": params, "sha256": digest(content), "cache": str(cached.relative_to(ROOT))}
    response = httpx.get(url, params=params, timeout=60, follow_redirects=True)
    response.raise_for_status()
    content = response.content
    if suffix == ".fits" and not content.startswith(b"SIMPLE"):
        raise ValueError("Upstream response is not FITS")
    if suffix == ".xml":
        parse_single_table(BytesIO(content))
    cached.write_bytes(content)
    return content, {"url": str(response.url), "params": params, "sha256": digest(content), "cache": str(cached.relative_to(ROOT))}


def gaia_catalog(ra: float, dec: float) -> tuple[list[dict], dict]:
    query = f"""SELECT TOP 5000 source_id, ra, dec, phot_g_mean_mag, pmra, pmdec, parallax, ruwe
FROM gaia_dr3_source
WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra:.8f},{dec:.8f},0.18))
AND phot_g_mean_mag <= 18
ORDER BY phot_g_mean_mag ASC"""
    try:
        content, provenance = fetch("https://gea.esac.esa.int/tap-server/tap/sync", params={
            "REQUEST":"doQuery","LANG":"ADQL","FORMAT":"votable",
            "QUERY":query.replace("gaia_dr3_source","gaiadr3.gaia_source")}, suffix=".xml")
    except Exception as esa_error:
        content, provenance = fetch("https://irsa.ipac.caltech.edu/TAP/sync", params={"query": query, "format": "votable"}, suffix=".xml")
        provenance["esa_error"] = str(esa_error)
    table = parse_single_table(BytesIO(content)).to_table()
    rows = []
    for row in table:
        values = {}
        for key in table.colnames:
            item = row[key]
            name = key.lower()
            values[name] = None if np.ma.is_masked(item) else str(item) if name == "source_id" else float(item)
        rows.append(values)
    if len(rows) >= 5000:
        raise ValueError("Gaia query reached 5000-row limit; blending screen incomplete")
    provenance.update({"catalog": "Gaia DR3", "reference_epoch": "J2016.0 TCB", "g_limit": 18, "rows": len(rows), "is_simulated_fallback": False})
    return rows, provenance


def propagate(rows: list[dict], mjd: float, scale: str) -> tuple[SkyCoord, list[dict], int]:
    valid = [r for r in rows if all(r.get(k) is not None and np.isfinite(r[k]) for k in ("ra", "dec", "pmra", "pmdec"))]
    coord = SkyCoord(ra=[r["ra"] for r in valid] * u.deg, dec=[r["dec"] for r in valid] * u.deg,
                     pm_ra_cosdec=[r["pmra"] for r in valid] * u.mas/u.yr,
                     pm_dec=[r["pmdec"] for r in valid] * u.mas/u.yr,
                     obstime=Time(2016.0, format="jyear", scale="tcb"), frame="icrs")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # No distance/radial velocity; documented angular PM propagation.
        moved = coord.apply_space_motion(new_obstime=Time(mjd, format="mjd", scale=scale))
    # Strip propagation metadata/differentials before comparing static ICRS
    # positions from the FITS WCS; the coordinates remain at exposure time.
    return SkyCoord(ra=moved.ra, dec=moved.dec, frame="icrs"), valid, len(rows) - len(valid)


def fit_centroid(image: np.ndarray, variance: np.ndarray, bad: np.ndarray, x: float, y: float, scale: float) -> dict | None:
    """Unconstrained-by-Gaia elliptical Gaussian fit around an image peak.

    Centroid bounds are +/-2 native pixels about the independently detected
    peak, not about the expected catalog position. No acceptance cut uses the
    final astrometric residual, preventing artificially good residuals.
    """
    half = int(np.ceil(4 * 6.15 / scale))
    cx, cy = int(round(x)), int(round(y))
    if cx-half < 0 or cy-half < 0 or cx+half >= image.shape[1] or cy+half >= image.shape[0]:
        return None
    sl = np.s_[cy-half:cy+half+1, cx-half:cx+half+1]
    patch, var, mask = image[sl], variance[sl], bad[sl]
    yy, xx = np.indices(patch.shape, dtype=float)
    xx += cx-half
    yy += cy-half
    radius = np.hypot(xx-x, yy-y)
    core = radius <= 2 * 6.15 / scale
    if np.any(mask[core]) or np.any(~np.isfinite(patch[core])):
        return None
    clean = ~mask & np.isfinite(patch) & np.isfinite(var) & (var > 0)
    if clean.sum() < 25:
        return None
    sky = float(np.median(patch[clean & (radius > 2.5*6.15/scale)])) if np.any(clean & (radius > 2.5*6.15/scale)) else float(np.median(patch[clean]))
    amplitude = float(np.max(patch[clean]) - sky)
    noise = float(np.sqrt(np.median(var[clean])))
    if amplitude <= 10*noise:
        return None
    coords_x, coords_y, values = xx[clean], yy[clean], patch[clean]
    errors = np.sqrt(var[clean])
    def residual(p):
        amp, x0, y0, sx, sy, bg = p
        model = bg + amp*np.exp(-0.5*(((coords_x-x0)/sx)**2 + ((coords_y-y0)/sy)**2))
        return (model-values)/errors
    factor = 6.15 / scale
    guess = [amplitude,x,y,0.9*factor,0.9*factor,sky]
    lower = [0,x-2*factor,y-2*factor,0.3*factor,0.3*factor,-np.inf]
    upper = [np.inf,x+2*factor,y+2*factor,2.5*factor,2.5*factor,np.inf]
    fit = least_squares(residual, guess, bounds=(lower,upper), max_nfev=250)
    amp,x0,y0,sx,sy,bg = fit.x
    if not fit.success or max(sx,sy)/min(sx,sy) > 2 or min(sx,sy) < .35*factor or max(sx,sy) > 2*factor:
        return None
    return {"x":float(x0),"y":float(y0),"peak_snr_approx":float(amp/noise),"sigma_x_px":float(sx),"sigma_y_px":float(sy),"reduced_chi2_approx":float(np.sum(fit.fun**2)/max(1,len(fit.fun)-6))}


def detect(image: np.ndarray, variance: np.ndarray, bad: np.ndarray, scale: float, rejected: list[dict] | None = None) -> list[dict]:
    clean = ~bad & np.isfinite(image) & np.isfinite(variance) & (variance > 0)
    if not np.any(clean):
        return []
    sky = float(np.median(image[clean]))
    candidate = clean & (image == maximum_filter(np.where(clean,image,-np.inf), size=5)) & ((image-sky) > 10*np.sqrt(np.where(clean,variance,np.inf)))
    ys,xs = np.where(candidate)
    peaks = []
    for x,y in zip(xs,ys):
        neighbors = ((xs-x)**2+(ys-y)**2 < (3*6.15/scale)**2) & ((xs!=x)|(ys!=y))
        if np.any(neighbors):
            if rejected is not None:
                rejected.append({"x":int(x),"y":int(y),"reason":"image_neighbor_within_3_native_pixels"})
            continue
        fitted = fit_centroid(image,variance,bad,float(x),float(y),scale)
        if fitted is not None:
            peaks.append(fitted)
        elif rejected is not None:
            rejected.append({"x":int(x),"y":int(y),"reason":"flagged_core_edge_low_signal_or_poor_fit"})
    return peaks


def summary(rows: list[dict], prefix: str) -> dict:
    if len(rows) < 3:
        return {"status":"insufficient_stars","count":len(rows),"threshold_arcsec":THRESHOLD_ARCSEC}
    offsets = np.array([[r[f"{prefix}_dra_cosdec_arcsec"],r[f"{prefix}_ddec_arcsec"]] for r in rows])
    bias = np.median(offsets,axis=0)
    sigma = 1.4826*np.median(np.abs(offsets-bias),axis=0)
    robust_rms = float(np.sqrt(np.sum(bias**2+sigma**2)))
    radial = np.linalg.norm(offsets,axis=1)
    return {"status":"pass" if robust_rms <= THRESHOLD_ARCSEC else "fail","count":len(rows),
            "median_offset_arcsec":bias.tolist(),"robust_sigma_axes_arcsec":sigma.tolist(),
            "robust_rms_including_bias_arcsec":robust_rms,"raw_radial_rms_arcsec":float(np.sqrt(np.mean(radial**2))),
            "maximum_residual_arcsec":float(radial.max()),"above_threshold":int(np.sum(radial>THRESHOLD_ARCSEC)),"threshold_arcsec":THRESHOLD_ARCSEC}


def audit_exposure(target: str, manifest: dict, uri: str, rows: list[dict]) -> dict:
    ra,dec = manifest["query"]["ra"],manifest["query"]["dec"]
    url = "https://irsa.ipac.caltech.edu/" + uri.lstrip("/")
    content, provenance = fetch(url,params={"center":f"{ra:.8f},{dec:.8f}","size":"0.2"},suffix=".fits")
    with fits.open(BytesIO(content),memmap=False) as hdul:
        image = hdul["IMAGE"].data.astype(float)-hdul["ZODI"].data.astype(float)
        variance = hdul["VARIANCE"].data.astype(float)
        flags = hdul["FLAGS"].data.astype(np.uint32)
        header = hdul["IMAGE"].header.copy()
        primary = hdul[0].header
        combined = dict(primary);combined.update(dict(header))
        time_key = next((k for k in ["MJD-AVG","MJD-MID","MJD_OBS","MJD-OBS","MJD"] if k in combined),None)
        if time_key is None:
            raise ValueError("No verified observation MJD in FITS headers")
        mjd = float(combined[time_key]);time_scale = str(combined.get("TIMESYS","UTC")).lower()
        if time_scale not in {"utc","tt","tai","tcb","tdb"}:
            raise ValueError(f"Unsupported FITS time scale {time_scale}")
    spatial = WCS(header)
    scale = float(np.mean(proj_plane_pixel_scales(spatial))*3600)
    bad = (flags & PHOTOMETRY_EXCLUDE_MASK) != 0
    rejected_peaks = []
    measured = detect(image,variance,bad,scale,rejected_peaks)
    moved, valid_rows, missing_pm = propagate(rows,mjd,time_scale)
    out = WCS(naxis=2);out.wcs.ctype=["RA---TAN","DEC--TAN"];out.wcs.crval=[ra,dec];out.wcs.crpix=[120.5,120.5];out.wcs.cdelt=[-3.075/3600,3.075/3600]
    projected, footprint = reproject_interp((np.where(bad,np.nan,image),spatial),out,shape_out=(240,240))
    projected_var,_ = reproject_interp((variance,spatial),out,shape_out=(240,240))
    projected_bad,_ = reproject_interp((bad.astype(float),spatial),out,shape_out=(240,240),order="nearest-neighbor")
    projected_bad = (projected_bad > 0) | (footprint == 0) | ~np.isfinite(projected)
    rejected = Counter({"gaia_missing_pm":missing_pm})
    rejected_gaia = []
    def reject_gaia(reason: str, row: dict, peak: dict) -> None:
        rejected[reason] += 1
        rejected_gaia.append({"source_id":row["source_id"],"reason":reason,"native_x":peak["x"],"native_y":peak["y"]})
    matches = []
    if len(measured) and len(valid_rows):
        positions = spatial.pixel_to_world([p["x"] for p in measured],[p["y"] for p in measured])
        nearest, distances, _ = positions.match_to_catalog_sky(moved)
        associations = Counter(int(idx) for idx,distance in zip(nearest,distances) if distance.arcsec <= 12.3)
        for peak,idx,separation,position in zip(measured,nearest,distances,positions):
            if separation.arcsec > 12.3:
                rejected["no_gaia_within_12_3_arcsec"] += 1;continue
            if associations[int(idx)] > 1:
                rejected["ambiguous_multiple_peaks_for_gaia_source"] += 1;continue
            row = valid_rows[int(idx)]
            if any(row.get(k) is None or not np.isfinite(row[k]) for k in ("phot_g_mean_mag","ruwe","parallax")) or row["phot_g_mean_mag"] > 16 or row["ruwe"] > 1.4 or abs(row["parallax"]) > 10:
                reject_gaia("gaia_magnitude_astrometric_quality_or_parallax",row,peak);continue
            neighbors = moved[int(idx)].separation(moved).arcsec
            if np.sum(neighbors < 18.45) > 1:
                reject_gaia("gaia_neighbor_within_18_45_arcsec",row,peak);continue
            # Missing-PM catalog rows still veto potential blends at J2016.0.
            missing_rows = [r for r in rows if r.get("pmra") is None or r.get("pmdec") is None]
            if missing_rows:
                unknown = SkyCoord([r["ra"] for r in missing_rows]*u.deg,[r["dec"] for r in missing_rows]*u.deg)
                if np.any(moved[int(idx)].separation(unknown).arcsec < 18.45):
                    reject_gaia("neighbor_missing_pm",row,peak);continue
            xout,yout = out.world_to_pixel(position)
            fitted = fit_centroid(projected,projected_var,projected_bad,float(xout),float(yout),3.075)
            if fitted is None:
                reject_gaia("reprojected_fit_invalid_or_flagged",row,peak);continue
            shifted = out.pixel_to_world(fitted["x"],fitted["y"])
            dra,ddec = moved[int(idx)].spherical_offsets_to(position)
            out_dra,out_ddec = moved[int(idx)].spherical_offsets_to(shifted)
            matches.append({"source_id":row["source_id"],"g_mag":row["phot_g_mean_mag"],"ruwe":row["ruwe"],"parallax_mas":row["parallax"],
                            "gaia_ra_at_exposure":float(moved[int(idx)].ra.deg),"gaia_dec_at_exposure":float(moved[int(idx)].dec.deg),
                            "pmra_mas_yr":row["pmra"],"pmdec_mas_yr":row["pmdec"],"native_fit":peak,"output_fit":fitted,
                            "native_dra_cosdec_arcsec":float(dra.arcsec),"native_ddec_arcsec":float(ddec.arcsec),
                            "output_dra_cosdec_arcsec":float(out_dra.arcsec),"output_ddec_arcsec":float(out_ddec.arcsec)})
    return {"target":target,"uri":uri,"fits":provenance,"mjd":mjd,"mjd_keyword":time_key,"time_scale":time_scale,
            "native_pixel_scale_arcsec":scale,"measurement_exclude_mask":PHOTOMETRY_EXCLUDE_MASK,
            "excluded_pixel_flag_counts":{name:int(np.count_nonzero(flags & value)) for name,value in FLAG_VALUES.items() if value & PHOTOMETRY_EXCLUDE_MASK and np.any(flags & value)},
            "rejected_image_peaks":rejected_peaks,"rejected_gaia_matches":rejected_gaia,
            "detected_clean_peaks":len(measured),"rejected":dict(rejected),
            "native":summary(matches,"native"),"output":summary(matches,"output"),"matches":matches}


def audit_target(target: str) -> dict:
    manifest = json.loads((ROOT/"golden_cache"/target/"manifest.json").read_text(encoding="utf-8"))
    result = {"target":target,"exposures":[]}
    try:
        rows,provenance = gaia_catalog(manifest["query"]["ra"],manifest["query"]["dec"])
        result["gaia"] = provenance
    except Exception as exc:
        result.update(status="unverified",error=f"Independent Gaia catalog unavailable: {exc}")
        return result
    epochs = [e for e in manifest["epochs"] if "1" in e["band_stats"]]
    uris = list(dict.fromkeys(e["band_stats"]["1"]["artifact_uris"][0] for e in [epochs[0],epochs[-1]]))
    for uri in uris:
        try:
            result["exposures"].append(audit_exposure(target,manifest,uri,rows))
        except Exception as exc:
            result["exposures"].append({"uri":uri,"status":"unverified","error":str(exc)})
    statuses = [e.get("output",{}).get("status",e.get("status")) for e in result["exposures"]]
    result["status"] = "pass" if statuses and all(s=="pass" for s in statuses) else "fail" if "fail" in statuses else "insufficient_or_unverified"
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets",nargs="+",choices=TARGETS,default=TARGETS)
    args=parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(audit_target,args.targets))
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"is_simulated_fallback":False,"scope":"First and last available recorded D1 exposures per target; independent peak centroids vs fresh Gaia DR3, native and reprojected. Not validation of golden coadds.",
            "criteria":{"minimum_stars":3,"threshold_arcsec":THRESHOLD_ARCSEC,"gaia_candidate_g_max":16,"gaia_neighbor_g_max":18,"ruwe_max":1.4,"absolute_parallax_max_mas":10,"gaia_isolation_arcsec":18.45,"association_radius_arcsec":12.3,"peak_snr_min_approx":10,"robust_rms_definition":"sqrt(sum(median_offset_axis**2 + (1.4826*MAD_axis)**2)); bias retained; no residual clipping"},
            "limitations":["Gaussian centroid model is approximate for undersampled asymmetric SPHEREx PSFs.","No distance/radial velocity or observer parallax correction; candidates with absolute parallax >10 mas excluded.","Gaia G<=18 neighbors do not rule out all infrared blends.","No passing-star selection uses the 1.5375 arcsec acceptance threshold.","Representative individual exposures cannot certify all golden coadds."],"targets":results}
    out=ROOT/"docs/evidence/phase3/phase3-astrometry-results.json";out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    lines=["# Phase 3 independent astrometry measurements","",f"Generated: {report['generated_at']}","",report["scope"],"","Threshold: robust RMS including bias <= 1.5375 arcsec, with at least three suitable stars per exposure. No residual clipping or target-driven threshold tuning.","","| Target | Exposure | Stars | Native robust RMS (arcsec) | Output robust RMS (arcsec) | Status |","|---|---|---:|---:|---:|---|"]
    for result in results:
        print(result["target"],result["status"],flush=True)
        if not result["exposures"]:
            lines.append(f"| {result['target']} | unavailable | 0 | — | — | {result.get('error','unverified')} |")
        for exposure in result["exposures"]:
            native=exposure.get("native",{});output=exposure.get("output",{})
            native_rms = f"{native['robust_rms_including_bias_arcsec']:.3f}" if 'robust_rms_including_bias_arcsec' in native else 'n/a'
            output_rms = f"{output['robust_rms_including_bias_arcsec']:.3f}" if 'robust_rms_including_bias_arcsec' in output else 'n/a'
            status = output.get('status',exposure.get('error','unverified')).replace('\n',' ').replace('|','/')
            lines.append(f"| {result['target']} | {exposure['uri'].split('/')[-1]} | {output.get('count',0)} | {native_rms} | {output_rms} | {status} |")
    lines.extend(["","## Method and limits","","Detection uses image local maxima without Gaia coordinates. Elliptical Gaussian fits use IMAGE minus ZODI, native variance weights, and the conservative hard-plus-warning mask. SOURCE remains usable. Fits with flagged cores, close image peaks, poor shapes, close Gaia neighbors, missing proper motions, or poor Gaia astrometric quality are excluded. Gaia ICRS positions are propagated from J2016.0 TCB to the FITS observation MJD/time scale with SkyCoord.apply_space_motion. Every accepted star's source ID, proper motion, fit, and native/output residual vector appears in the JSON report. Native and output coordinates are measured independently; the output fit is on the reprojected real exposure, not on a rendered WebP.",""]+[f"- {v}" for v in report["limitations"]]+["","The JSON records source URLs, exact query, local download SHA-256, exclusions, bias, robust scatter, raw radial RMS, maximum residual, and above-threshold count. FITS and query responses remain in ignored local cache; saved observations are unchanged.","","References: [Gaia DR3 reference epoch](https://www.cosmos.esa.int/web/gaia/dr3), [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf).",""])
    (ROOT/"docs/verification/phase3-astrometry-results.md").write_text("\n".join(lines),encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
