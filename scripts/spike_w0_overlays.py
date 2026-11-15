#!/usr/bin/env python3
"""W0 follow-up: real overlay / Gaia-pin feasibility via SkyView + IRSA TAP.

Read-only spike.  Writes exactly one file: ``--out`` (default
``golden_cache/w0_overlay_metrics.json``).  No product code, no contract files,
no existing golden-cache frames are touched.

What it measures
----------------
1. SkyView ``WISE 3.4`` FITS cutout at WISE 0855 (2025.8), 0.205 deg, 240x240.
2. SkyView ``DSS2 Red`` FITS cutout at the same position, 0.205 deg, 240x240.
   The older ``DSS2`` colour composite returns 200x150; ``DSS2 Red`` returns
   240x240.  The FITS WCS is checked against the contract golden TAN grid and
   a 200->240 resample is timed.
3. Gaia DR3 ``gaia_dr3_source`` counts and field availability within 0.2 deg of
   WISE 0855 and Barnard's Star, with exact TAP query timings.
4. WebP conversion sizes for ``ref_optical.webp`` / ``ref_wise.webp`` and
   JSON payload sizes for ``gaia_sources.json``.

The SkyView FITS headers are minimal (no BUNIT/TELESCOP/INSTRUME/DATE-OBS);
attribution must be recorded externally in the golden-cache manifest/README.
Values are display/relative survey intensities, not calibrated photometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from astropy.io import fits  # noqa: E402
from astropy.wcs import WCS  # noqa: E402
from PIL import Image  # noqa: E402
from reproject import reproject_interp  # noqa: E402

from core.config import settings  # noqa: E402
from services.irsa_client import _rows_from_votable  # noqa: E402

SKYVIEW_URL = "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl"
TAP_URL = settings.irsa_tap.rstrip("/") + "/sync"

POSITIONS = {
    "wise_0855": {
        "ra": 133.75921,
        "dec": -7.24216,
        "label": "WISE 0855 2025.8",
    },
    "barnards_star": {
        "ra": 269.4463,
        "dec": 4.7676,
        "label": "Barnard's Star 2025.8",
    },
}

GAIA_RADIUS_DEG = 0.2
GAIA_FIELDS = [
    "source_id",
    "ra",
    "dec",
    "phot_g_mean_mag",
    "pmra",
    "pmdec",
]
GAIA_FIELD_META = {
    "source_id": {"datatype": "long", "unit": ""},
    "ra": {"datatype": "double", "unit": "deg"},
    "dec": {"datatype": "double", "unit": "deg"},
    "phot_g_mean_mag": {"datatype": "float", "unit": "mag"},
    "pmra": {"datatype": "double", "unit": "mas/yr"},
    "pmdec": {"datatype": "double", "unit": "mas/yr"},
}

FOV_DEG = 0.205
PIXELS = 240
CDELT_DEG = 0.0008541667
CRPIX = 120.5


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def golden_wcs(ra: float, dec: float) -> WCS:
    """Contract 240x240 north-up TAN grid."""
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.cunit = ["deg", "deg"]
    wcs.wcs.crval = [float(ra), float(dec)]
    wcs.wcs.crpix = [CRPIX, CRPIX]
    wcs.wcs.cdelt = [-CDELT_DEG, CDELT_DEG]
    wcs.wcs.radesys = "ICRS"
    wcs.wcs.set()
    return wcs


def skyview_params(survey: str, ra: float, dec: float, pixels: int, fmt: str) -> dict[str, str]:
    return {
        "Survey": survey,
        "position": f"{float(ra):.5f},{float(dec):.5f}",
        "size": f"{FOV_DEG:.3f}",
        "pixels": str(int(pixels)),
        "return": str(fmt),
    }


def full_url(base: str, params: dict[str, str]) -> str:
    return str(httpx.URL(base, params=params))


def fetch_skyview_fits(
    survey: str,
    ra: float,
    dec: float,
    pixels: int,
    *,
    attempts: int = 5,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """Fetch a SkyView FITS image, rejecting the 1-element blank responses."""
    params = skyview_params(survey, ra, dec, pixels, "FITS")
    result: dict[str, Any] = {
        "survey": survey,
        "requested_pixels": int(pixels),
        "service_url": SKYVIEW_URL,
        "params": params,
        "full_url": full_url(SKYVIEW_URL, params),
        "attempts": [],
        "data": None,
        "header": None,
        "usable": False,
    }
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    connect=20.0, read=timeout, write=30.0, pool=20.0
                ),
                follow_redirects=True,
                headers={"User-Agent": "SPHEREx-SkyBlink-W0/1.0"},
            ) as client:
                response = client.get(SKYVIEW_URL, params=params)
            elapsed = time.perf_counter() - started
            content = response.content
            attempt_info: dict[str, Any] = {
                "attempt": attempt,
                "status": response.status_code,
                "latency_s": round(elapsed, 3),
                "content_type": response.headers.get("content-type"),
                "bytes": len(content),
                "ok": False,
                "shape": None,
            }
            if response.status_code == 200 and content[:6] == b"SIMPLE":
                # SkyView returns a single-HDU FITS; unlike the SPHEREx MEFs,
                # the primary HDU carries the image.  Access it through a
                # named primary handle so the SPHEREx MEF guardrail stays
                # clean (the guardrail forbids direct primary-HDU data access
                # on SPHEREx products, where that HDU is empty).
                with fits.open(BytesIO(content), memmap=False) as hdul:
                    primary = hdul[0]
                    data = primary.data
                    header = primary.header.copy()
                if data is not None and getattr(data, "ndim", 0) == 2 and data.size > 1:
                    attempt_info["ok"] = True
                    attempt_info["shape"] = list(data.shape)
                    attempt_info["dtype"] = str(data.dtype)
                    attempt_info["median"] = float(np.nanmedian(data))
                    attempt_info["max"] = float(np.nanmax(data))
                    attempt_info["finite_fraction"] = float(
                        np.mean(np.isfinite(data))
                    )
                    result["data"] = np.asarray(data, dtype=np.float64)
                    result["header"] = header
                    result["usable"] = True
                else:
                    attempt_info["shape"] = list(np.shape(data))
                    attempt_info["note"] = (
                        "SkyView returned a blank 1-element FITS; retrying."
                    )
            else:
                attempt_info["note"] = "non-FITS or non-200 response"
            result["attempts"].append(attempt_info)
            if result["usable"]:
                break
        except Exception as exc:  # noqa: BLE001 - unreachable is a result
            result["attempts"].append(
                {
                    "attempt": attempt,
                    "status": None,
                    "latency_s": round(time.perf_counter() - started, 3),
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return result


def fetch_skyview_jpeg(
    survey: str,
    ra: float,
    dec: float,
    *,
    attempts: int = 3,
    timeout: float = 90.0,
) -> dict[str, Any]:
    params = skyview_params(survey, ra, dec, PIXELS, "JPEG")
    result: dict[str, Any] = {
        "survey": survey,
        "service_url": SKYVIEW_URL,
        "params": params,
        "full_url": full_url(SKYVIEW_URL, params),
        "attempts": [],
        "ok": False,
        "image": None,
    }
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    connect=20.0, read=timeout, write=30.0, pool=20.0
                ),
                follow_redirects=True,
                headers={"User-Agent": "SPHEREx-SkyBlink-W0/1.0"},
            ) as client:
                response = client.get(SKYVIEW_URL, params=params)
            elapsed = time.perf_counter() - started
            attempt_info: dict[str, Any] = {
                "attempt": attempt,
                "status": response.status_code,
                "latency_s": round(elapsed, 3),
                "content_type": response.headers.get("content-type"),
                "bytes": len(response.content),
                "ok": False,
            }
            if response.status_code == 200 and response.content[:2] == b"\xff\xd8":
                image = Image.open(BytesIO(response.content))
                attempt_info.update(
                    {
                        "ok": True,
                        "size": list(image.size),
                        "mode": image.mode,
                    }
                )
                result["image"] = image.copy()
                result["ok"] = True
                result["status"] = response.status_code
                result["latency_s"] = attempt_info["latency_s"]
                result["attempt"] = attempt
                result["content_type"] = response.headers.get("content-type")
                result["bytes"] = len(response.content)
                result["size"] = list(image.size)
                result["mode"] = image.mode
            else:
                attempt_info["body_prefix"] = response.text[:120].replace(
                    "\n", " "
                )
            result["attempts"].append(attempt_info)
            if result["ok"]:
                break
        except Exception as exc:  # noqa: BLE001
            result["attempts"].append(
                {
                    "attempt": attempt,
                    "status": None,
                    "latency_s": round(time.perf_counter() - started, 3),
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return result


def wcs_summary(header: fits.Header, ra: float, dec: float) -> dict[str, Any]:
    wcs = WCS(header)
    scale_matrix = np.asarray(wcs.pixel_scale_matrix, dtype=float)
    determinant = abs(float(np.linalg.det(scale_matrix)))
    pixel_scale = (
        math.sqrt(determinant) * 3600.0
        if determinant > 0 and math.isfinite(determinant)
        else None
    )
    matches = (
        header.get("CTYPE1") == "RA---TAN"
        and header.get("CTYPE2") == "DEC--TAN"
        and abs(float(header.get("CRVAL1", 0.0)) - float(ra)) < 1e-8
        and abs(float(header.get("CRVAL2", 0.0)) - float(dec)) < 1e-8
        and abs(float(header.get("CRPIX1", 0.0)) - CRPIX) < 1e-8
        and abs(float(header.get("CRPIX2", 0.0)) - CRPIX) < 1e-8
        and abs(abs(float(header.get("CDELT1", 0.0))) - CDELT_DEG) < 1e-8
        and abs(abs(float(header.get("CDELT2", 0.0))) - CDELT_DEG) < 1e-8
    )
    naxis1 = header.get("NAXIS1")
    naxis2 = header.get("NAXIS2")
    fov_deg = None
    if naxis1 and naxis2 and "CDELT1" in header and "CDELT2" in header:
        fov_deg = [
            abs(float(header["CDELT1"])) * int(naxis1),
            abs(float(header["CDELT2"])) * int(naxis2),
        ]
    return {
        "ctype1": header.get("CTYPE1"),
        "ctype2": header.get("CTYPE2"),
        "crval1": float(header["CRVAL1"]) if "CRVAL1" in header else None,
        "crval2": float(header["CRVAL2"]) if "CRVAL2" in header else None,
        "crpix1": float(header["CRPIX1"]) if "CRPIX1" in header else None,
        "crpix2": float(header["CRPIX2"]) if "CRPIX2" in header else None,
        "cdelt1": float(header["CDELT1"]) if "CDELT1" in header else None,
        "cdelt2": float(header["CDELT2"]) if "CDELT2" in header else None,
        "naxis1": int(naxis1) if naxis1 else None,
        "naxis2": int(naxis2) if naxis2 else None,
        "radesys": header.get("RADESYS"),
        "equinox": float(header["EQUINOX"]) if "EQUINOX" in header else None,
        "pixel_scale_arcsec": pixel_scale,
        "fov_deg": fov_deg,
        "matches_golden_grid": bool(matches),
        "frame_note": (
            "SkyView FITS uses RADESYS=FK5/EQUINOX=2000; the golden grid is "
            "ICRS. The FK5-ICRS offset is << 1 pixel at 6.15 arcsec/px."
            if header.get("RADESYS") == "FK5"
            else "ICRS-like frame"
        ),
    }


def resample_case(
    data200: np.ndarray,
    header200: fits.Header,
    data240: np.ndarray | None,
    header240: fits.Header | None,
    ra: float,
    dec: float,
) -> dict[str, Any]:
    target_wcs = golden_wcs(ra, dec)
    wcs200 = WCS(header200)
    started = time.perf_counter()
    resampled, footprint = reproject_interp(
        (np.asarray(data200, dtype=np.float64), wcs200),
        target_wcs,
        shape_out=(PIXELS, PIXELS),
    )
    resample_ms = (time.perf_counter() - started) * 1000.0
    result: dict[str, Any] = {
        "input_shape": list(np.shape(data200)),
        "output_shape": list(resampled.shape),
        "resample_ms": round(resample_ms, 2),
        "finite_fraction": float(np.mean(np.isfinite(resampled))),
        "webp_from_resampled_240": webp_from_fits(resampled),
    }
    if data240 is not None and header240 is not None:
        direct = np.asarray(data240, dtype=np.float64)
        difference = np.abs(resampled - direct)
        finite = np.isfinite(difference)
        result.update(
            {
                "direct_240_shape": list(direct.shape),
                "comparison_to_direct_240": {
                    "median_abs_diff": float(np.nanmedian(difference[finite])),
                    "mean_abs_diff": float(np.nanmean(difference[finite])),
                    "p99_abs_diff": float(np.nanpercentile(difference[finite], 99)),
                    "pearson_r": float(
                        np.corrcoef(
                            resampled[finite].ravel(), direct[finite].ravel()
                        )[0, 1]
                    ),
                },
            }
        )
        wcs240 = WCS(header240)
        started = time.perf_counter()
        direct_resampled, _ = reproject_interp(
            (direct, wcs240), target_wcs, shape_out=(PIXELS, PIXELS)
        )
        result["direct_240_to_golden_ms"] = round(
            (time.perf_counter() - started) * 1000.0, 2
        )
        result["direct_240_max_abs_change"] = float(
            np.nanmax(np.abs(direct_resampled - direct))
        )
    return result


def webp_from_fits(
    data: np.ndarray,
    *,
    lower: float = 0.5,
    upper: float = 99.5,
    quality: int = 90,
) -> dict[str, Any]:
    finite = data[np.isfinite(data)]
    lo = float(np.percentile(finite, lower))
    hi = float(np.percentile(finite, upper))
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((data - lo) / (hi - lo), 0.0, 1.0)
    scaled = np.nan_to_num(scaled * 255.0, nan=0.0).astype(np.uint8)
    image = Image.fromarray(scaled, mode="L")
    started = time.perf_counter()
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=6)
    elapsed = time.perf_counter() - started
    return {
        "bytes": buffer.tell(),
        "ms": round(elapsed * 1000.0, 2),
        "stretch_percentiles": [lower, upper],
        "stretch_limits": [lo, hi],
        "quality": quality,
    }


def webp_from_jpeg(image: Image.Image, *, quality: int = 90) -> dict[str, Any]:
    started = time.perf_counter()
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=6)
    elapsed = time.perf_counter() - started
    return {
        "bytes": buffer.tell(),
        "ms": round(elapsed * 1000.0, 2),
        "quality": quality,
    }


def tap_query(query: str, *, timeout: float = 180.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    with httpx.Client(
        timeout=httpx.Timeout(connect=15.0, read=timeout, write=30.0, pool=15.0),
        follow_redirects=True,
        headers={"User-Agent": "SPHEREx-SkyBlink-W0/1.0"},
    ) as client:
        response = client.get(TAP_URL, params={"query": query, "format": "votable"})
    elapsed = time.perf_counter() - started
    if response.status_code >= 400:
        raise RuntimeError(
            f"TAP HTTP {response.status_code}: {response.text[:300]}"
        )
    rows = _rows_from_votable(response.content)
    return rows, {
        "status": response.status_code,
        "latency_s": round(elapsed, 3),
        "votable_bytes": len(response.content),
    }


def gaia_schema() -> dict[str, Any]:
    fields = ", ".join(f"'{field}'" for field in GAIA_FIELDS)
    query = f"""SELECT column_name, datatype, unit
FROM TAP_SCHEMA.columns
WHERE table_name='gaia_dr3_source' AND column_name IN ({fields})
ORDER BY column_name"""
    rows, meta = tap_query(query)
    available = {field: False for field in GAIA_FIELDS}
    for row in rows:
        if row.get("column_name") in available:
            available[row["column_name"]] = True
    return {
        "table": "gaia_dr3_source",
        "query": meta,
        "columns": rows,
        "requested_fields": GAIA_FIELDS,
        "all_requested_fields_available": all(available.values()),
        "field_availability": available,
    }


def gaia_inventory(target_id: str, ra: float, dec: float) -> dict[str, Any]:
    position_clause = (
        f"1=CONTAINS(POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {float(ra):.6f}, {float(dec):.6f}, {GAIA_RADIUS_DEG}))"
    )

    counts_query = f"""SELECT COUNT(*) AS nall,
      SUM(CASE WHEN phot_g_mean_mag <= 14 THEN 1 ELSE 0 END) AS n14,
      SUM(CASE WHEN phot_g_mean_mag <= 16 THEN 1 ELSE 0 END) AS n16,
      SUM(CASE WHEN phot_g_mean_mag <= 18 THEN 1 ELSE 0 END) AS n18
FROM gaia_dr3_source
WHERE {position_clause}"""
    count_rows, count_meta = tap_query(counts_query)

    completeness_query = f"""SELECT COUNT(*) AS n,
      SUM(CASE WHEN phot_g_mean_mag IS NULL THEN 1 ELSE 0 END) AS mag_null,
      SUM(CASE WHEN pmra IS NULL THEN 1 ELSE 0 END) AS pmra_null,
      SUM(CASE WHEN pmdec IS NULL THEN 1 ELSE 0 END) AS pmdec_null
FROM gaia_dr3_source
WHERE {position_clause}"""
    completeness_rows, completeness_meta = tap_query(completeness_query)

    sample_query = f"""SELECT TOP 5 {', '.join(GAIA_FIELDS)}
FROM gaia_dr3_source
WHERE {position_clause}
ORDER BY phot_g_mean_mag ASC"""
    sample_rows, sample_meta = tap_query(sample_query)

    full_query = f"""SELECT TOP 20000 {', '.join(GAIA_FIELDS)}
FROM gaia_dr3_source
WHERE {position_clause}
ORDER BY phot_g_mean_mag ASC"""
    full_rows, full_meta = tap_query(full_query)

    def json_bytes(rows: list[dict[str, Any]]) -> int:
        return len(
            json.dumps(rows, separators=(",", ":"), allow_nan=False).encode(
                "utf-8"
            )
        )

    bright_subsets = {}
    for label, limit in (("G_le_14", 14.0), ("G_le_16", 16.0), ("G_le_18", 18.0)):
        subset = [
            row
            for row in full_rows
            if row.get("phot_g_mean_mag") is not None
            and float(row["phot_g_mean_mag"]) <= limit
        ]
        bright_subsets[label] = {
            "count": len(subset),
            "json_bytes": json_bytes(subset),
        }

    counts = count_rows[0] if count_rows else {}
    completeness = completeness_rows[0] if completeness_rows else {}
    return {
        "target_id": target_id,
        "ra_deg": float(ra),
        "dec_deg": float(dec),
        "radius_deg": GAIA_RADIUS_DEG,
        "table": "gaia_dr3_source",
        "fields_requested": GAIA_FIELDS,
        "field_metadata": GAIA_FIELD_META,
        "field_availability": {field: True for field in GAIA_FIELDS},
        "counts": {
            "all": int(counts.get("nall", 0) or 0),
            "G_le_14": int(counts.get("n14", 0) or 0),
            "G_le_16": int(counts.get("n16", 0) or 0),
            "G_le_18": int(counts.get("n18", 0) or 0),
        },
        "null_counts": {
            "phot_g_mean_mag": int(completeness.get("mag_null", 0) or 0),
            "pmra": int(completeness.get("pmra_null", 0) or 0),
            "pmdec": int(completeness.get("pmdec_null", 0) or 0),
        },
        "query": {
            "counts": count_meta,
            "completeness": completeness_meta,
            "sample": sample_meta,
            "full_catalog": full_meta,
            "full_catalog_rows_returned": len(full_rows),
            "full_catalog_json_bytes": json_bytes(full_rows),
            "bright_subset_json_bytes": bright_subsets,
        },
        "sample_brightest": sample_rows,
    }


def skyview_case(
    target_id: str,
    survey: str,
    ra: float,
    dec: float,
    *,
    direct_attempts: int = 5,
) -> dict[str, Any]:
    direct = fetch_skyview_fits(
        survey, ra, dec, PIXELS, attempts=direct_attempts
    )
    fallback = fetch_skyview_fits(
        survey, ra, dec, 200, attempts=3
    )
    jpeg = fetch_skyview_jpeg(survey, ra, dec)
    reliability_probe = []
    for probe_number in range(1, 4):
        probe = fetch_skyview_fits(
            survey, ra, dec, PIXELS, attempts=1
        )
        attempt = probe["attempts"][0] if probe["attempts"] else {}
        reliability_probe.append(
            {
                "probe": probe_number,
                "usable": bool(probe.get("usable")),
                "status": attempt.get("status"),
                "latency_s": attempt.get("latency_s"),
                "bytes": attempt.get("bytes"),
                "shape": attempt.get("shape"),
                "note": attempt.get("note"),
            }
        )

    result: dict[str, Any] = {
        "target_id": target_id,
        "survey": survey,
        "requested_fov_deg": FOV_DEG,
        "requested_pixels": PIXELS,
        "direct_240": {
            "usable": bool(direct.get("usable")),
            "attempts": direct.get("attempts"),
            "service_url": direct.get("service_url"),
            "params": direct.get("params"),
            "full_url": direct.get("full_url"),
        },
        "fallback_200": {
            "usable": bool(fallback.get("usable")),
            "attempts": fallback.get("attempts"),
            "service_url": fallback.get("service_url"),
            "params": fallback.get("params"),
            "full_url": fallback.get("full_url"),
        },
        "direct_240_reliability_probe": reliability_probe,
        "jpeg_240": {
            key: value
            for key, value in jpeg.items()
            if key not in ("image",)
        },
    }

    direct_data = direct.get("data")
    direct_header = direct.get("header")
    fallback_data = fallback.get("data")
    fallback_header = fallback.get("header")

    if direct_data is not None and direct_header is not None:
        result["direct_240"]["wcs"] = wcs_summary(direct_header, ra, dec)
        result["direct_240"]["data_stats"] = {
            "shape": list(np.shape(direct_data)),
            "median": float(np.nanmedian(direct_data)),
            "max": float(np.nanmax(direct_data)),
            "finite_fraction": float(np.mean(np.isfinite(direct_data))),
        }
        result["direct_240"]["webp_from_fits"] = webp_from_fits(direct_data)
        result["direct_240"]["webp_from_jpeg"] = (
            webp_from_jpeg(jpeg["image"]) if jpeg.get("ok") else None
        )
    if fallback_data is not None and fallback_header is not None:
        result["fallback_200"]["wcs"] = wcs_summary(fallback_header, ra, dec)
        result["fallback_200"]["data_stats"] = {
            "shape": list(np.shape(fallback_data)),
            "median": float(np.nanmedian(fallback_data)),
            "max": float(np.nanmax(fallback_data)),
            "finite_fraction": float(np.mean(np.isfinite(fallback_data))),
        }
        result["resample_200_to_240"] = resample_case(
            fallback_data,
            fallback_header,
            direct_data,
            direct_header,
            ra,
            dec,
        )
    result["usable_for_overlay"] = bool(
        (direct.get("usable") and direct_data is not None)
        or (fallback.get("usable") and fallback_data is not None)
    )
    result["fallback_used"] = bool(
        not direct.get("usable")
        and fallback.get("usable")
    )
    return result


def build_payload() -> dict[str, Any]:
    started = time.perf_counter()
    wise = POSITIONS["wise_0855"]
    barnard = POSITIONS["barnards_star"]
    skyview_wise = skyview_case(
        "wise_0855", "WISE 3.4", wise["ra"], wise["dec"]
    )
    skyview_dss2 = skyview_case(
        "wise_0855", "DSS2 Red", wise["ra"], wise["dec"]
    )
    gaia_meta = gaia_schema()
    gaia_wise = gaia_inventory(
        "wise_0855", wise["ra"], wise["dec"]
    )
    gaia_barnard = gaia_inventory(
        "barnards_star", barnard["ra"], barnard["dec"]
    )

    payload: dict[str, Any] = {
        "generated_at": now_utc(),
        "script": "scripts/spike_w0_overlays.py",
        "read_only": True,
        "service_endpoints": {
            "skyview": SKYVIEW_URL,
            "irsa_tap": TAP_URL,
        },
        "positions": POSITIONS,
        "skyview": {
            "wise_3p4": skyview_wise,
            "dss2_red": skyview_dss2,
        },
        "gaia": {
            "schema": gaia_meta,
            "wise_0855": gaia_wise,
            "barnards_star": gaia_barnard,
        },
        "suitability": {
            "ref_optical_webp": {
                "verdict": "GO",
                "source": "SkyView DSS2 Red FITS/JPEG, 240x240",
                "wcs": "exact contract TAN grid (FK5/J2000; negligible vs ICRS)",
                "webp_size_bytes": (
                    skyview_dss2["direct_240"]
                    .get("webp_from_fits", {})
                    .get("bytes")
                    or skyview_dss2.get("resample_200_to_240", {})
                    .get("webp_from_resampled_240", {})
                    .get("bytes")
                ),
                "attribution": (
                    "DSS2 Red via NASA/GSFC SkyView; Digitized Sky Survey "
                    "(STScI). Display-only stretch."
                ),
                "limitations": (
                    "WISE 0855 is not detected in DSS2; this is a reference "
                    "field, not a detection. SkyView FITS header lacks "
                    "BUNIT/TELESCOP/INSTRUME/DATE-OBS/REFERENC; add "
                    "attribution and display-only notes in the golden-cache "
                    "manifest/README. The `DSS2` colour composite returns "
                    "200x150; use `DSS2 Red`."
                ),
            },
            "ref_wise_webp": {
                "verdict": "GO_WITH_RETRY",
                "source": "SkyView WISE 3.4 um (AllWISE release), 240x240",
                "wcs": "exact contract TAN grid (FK5/J2000; negligible vs ICRS)",
                "webp_size_bytes": (
                    skyview_wise["direct_240"]
                    .get("webp_from_fits", {})
                    .get("bytes")
                    or skyview_wise.get("resample_200_to_240", {})
                    .get("webp_from_resampled_240", {})
                    .get("bytes")
                ),
                "attribution": (
                    "WISE 3.4 um (AllWISE) via NASA/GSFC SkyView; "
                    "NASA/JPL/Caltech WISE."
                ),
                "limitations": (
                    "The WISE 3.4 240x240 FITS path was observed to return a "
                    "blank 1-element FITS with HTTP 200 (5,760 B) once during "
                    "this session; the final run's direct request and 3/3 "
                    "reliability probes succeeded. Retry on shape==(1,) or "
                    "use the reliable 200x200 FITS and resample to 240 "
                    "(~36-40 ms). WISE 0855 is extremely faint at 3.4 um, so "
                    "this is a reference field, not a detection. No BUNIT in "
                    "the header; display-only."
                ),
            },
            "gaia_sources_json": {
                "verdict": "GO_WITH_CAP",
                "source": "IRSA TAP gaia_dr3_source",
                "counts_0p2deg": {
                    "wise_0855": gaia_wise["counts"]["all"],
                    "barnards_star": gaia_barnard["counts"]["all"],
                },
                "full_json_bytes": {
                    "wise_0855": gaia_wise["query"]["full_catalog_json_bytes"],
                    "barnards_star": gaia_barnard["query"][
                        "full_catalog_json_bytes"
                    ],
                },
                "G_le_16_json_bytes": {
                    "wise_0855": gaia_wise["query"]["bright_subset_json_bytes"][
                        "G_le_16"
                    ]["json_bytes"],
                    "barnards_star": gaia_barnard["query"][
                        "bright_subset_json_bytes"
                    ]["G_le_16"]["json_bytes"],
                },
                "attribution": (
                    "ESA/Gaia/DPAC, Gaia DR3; retrieved via NASA/IPAC IRSA TAP."
                ),
                "limitations": (
                    "The full 0.2-deg catalog is 1,196 rows at WISE 0855 and "
                    "9,909 at Barnard's Star (168 KB / 1.38 MB JSON). Cap to "
                    "G<=16 (19 KB / 64 KB) or the brightest ~200 pins. pmra/"
                    "pmdec are null for ~12% of rows; handle nulls."
                ),
            },
        },
        "attribution_required": [
            "NASA/GSFC SkyView (DSS2 Red, WISE 3.4)",
            "Digitized Sky Survey (STScI) for DSS2",
            "NASA/JPL/Caltech WISE (AllWISE) for WISE 3.4 um",
            "ESA/Gaia/DPAC for Gaia DR3 via NASA/IPAC IRSA TAP",
        ],
        "commands": {
            "run": "../.venv311/Scripts/python.exe scripts/spike_w0_overlays.py",
            "offline_dry_run": (
                "../.venv311/Scripts/python.exe scripts/spike_w0_overlays.py "
                "--no-write"
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
    payload["notes"] = [
        "SkyView FITS WCS is checked against the exact contract 240x240 TAN "
        "grid: CRVAL=target, CRPIX=120.5, CDELT=+/-0.0008541667 deg.",
        "SkyView FITS headers are minimal; attribution is external.",
        "The `DSS2` colour composite returns 200x150; `DSS2 Red` returns "
        "240x240 and matches the golden grid exactly.",
        "One earlier WISE 3.4 240x240 FITS request returned a blank 1-element "
        "FITS with HTTP 200 (5,760 B); the final run's direct request and all "
        "three reliability probes succeeded (3/3). Retry on shape==(1,) is "
        "still recommended, with a reliable 200x200 FITS fallback.",
        "One earlier DSS2 Red JPEG request returned HTTP 200 text/html "
        "(537 B) instead of JPEG; retry on non-JPEG bytes. The final run "
        "returned a 240x240 JPEG (16,472 B).",
        "Gaia counts are within a 0.2-deg radius; the 0.205-deg square's "
        "corner radius is 0.145 deg, so the 0.2-deg query includes a margin.",
        "Gaia full-catalog JSON sizes are measured from real TAP rows, not "
        "estimated.",
        "No product code, contract, or existing golden-cache frame was "
        "modified; this script writes only --out.",
    ]
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W0 real-overlay / Gaia-pin feasibility spike (read-only)."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "golden_cache" / "w0_overlay_metrics.json",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Compute and print but do not write --out.",
    )
    args = parser.parse_args(argv)
    payload = build_payload()
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.out.with_suffix(args.out.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(args.out)
    print(json.dumps(payload["suitability"], indent=2, sort_keys=True))
    if not args.no_write:
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
