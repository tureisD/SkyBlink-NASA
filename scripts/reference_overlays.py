#!/usr/bin/env python3
"""Real reference overlays and Gaia DR3 pins for the golden cache.

The W0 feasibility report (``docs/research/w0-feasibility-report.md`` §5) replaced the
synthetic cross-mission references with real, display-only survey cutouts:

* **DSS2 Red** (Digitized Sky Survey, STScI) via NASA/GSFC SkyView;
* **WISE 3.4 um** (AllWISE) via NASA/GSFC SkyView and NASA/JPL/Caltech WISE;
* **WISE 4.6 um** for the WISE 0855 field only, because the Y dwarf is fainter
  than the 3.4 um confusion limit but emerges at 4.6 um;
* **Gaia DR3** sources (``gaia_dr3_source``) via NASA/IPAC IRSA TAP, capped to
  ``phot_g_mean_mag <= 16`` and the brightest 200 pins.

Everything here is a **reference/display** product: it is never used for
SPHEREx photometry, never substituted for a SPHEREx frame, and is explicitly
marked ``is_simulated_fallback: false`` because the images and catalog rows are
real survey data. The cutouts are resampled onto the exact contract 240 x 240
TAN golden grid so they line up with the blink canvas and the proper-motion
reticle.

SkyView is known to occasionally answer a ``240``-pixel FITS request with a
blank one-element FITS (HTTP 200); :func:`fetch_skyview` retries and, if the
blank response persists, falls back to a 200 x 200 FITS that is reprojected to
240 x 240. The retry history is recorded in the golden manifest so the
provenance is auditable.

Attribution is mandatory and is shipped twice: as a structured
``ref_attribution.json`` asset (served through ``/api/v1/assets/...``) and in
the target's manifest under ``reference_overlay_provenance``.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
for _candidate in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from astropy.io import fits  # noqa: E402
from astropy.wcs import WCS  # noqa: E402
from PIL import Image  # noqa: E402
from reproject import reproject_interp  # noqa: E402

from core.config import settings  # noqa: E402
from services.irsa_client import _rows_from_votable  # noqa: E402
from services.spherex_pipeline import GRID_HEIGHT, GRID_WIDTH, output_wcs  # noqa: E402

logger = logging.getLogger("skyblink.reference_overlays")

SKYVIEW_URL = "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl"
TAP_URL = settings.irsa_tap.rstrip("/") + "/sync"

DSS2_SURVEY = "DSS2 Red"
WISE_W1_SURVEY = "WISE 3.4"
WISE_W2_SURVEY = "WISE 4.6"
FOV_DEG = 0.205
PIXELS = GRID_WIDTH

STRETCH_PERCENTILES = (0.5, 99.5)
WEBP_QUALITY = 90

GAIA_RADIUS_DEG = 0.2
GAIA_G_LIMIT = 16.0
GAIA_CAP = 200

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")

OPTICAL_FILE = "ref_optical.webp"
WISE_W1_FILE = "ref_wise.webp"
WISE_W2_FILE = "ref_wise_w2.webp"
GAIA_FILE = "gaia_dr3.json"
ATTRIBUTION_FILE = "ref_attribution.json"

#: Targets that also get the WISE 4.6 um reference field.
WISE_W2_TARGETS = frozenset({"wise_0855"})

ATTRIBUTION_TEXT = (
    "DSS2 Red via NASA/GSFC SkyView; Digitized Sky Survey (STScI). "
    "WISE 3.4/4.6 um (AllWISE) via NASA/GSFC SkyView and NASA/JPL/Caltech "
    "WISE. Gaia DR3 via ESA/Gaia/DPAC through NASA/IPAC IRSA TAP. These are "
    "display-only reference fields, not calibrated photometry and not "
    "SPHEREx data."
)

CREDITS = (
    {
        "asset": OPTICAL_FILE,
        "survey": DSS2_SURVEY,
        "provider": "NASA/GSFC SkyView",
        "credit": "Digitized Sky Survey (STScI), DSS2 Red",
    },
    {
        "asset": WISE_W1_FILE,
        "survey": WISE_W1_SURVEY,
        "provider": "NASA/GSFC SkyView",
        "credit": "NASA/JPL/Caltech WISE (AllWISE), 3.4 um",
    },
    {
        "asset": WISE_W2_FILE,
        "survey": WISE_W2_SURVEY,
        "provider": "NASA/GSFC SkyView",
        "credit": "NASA/JPL/Caltech WISE (AllWISE), 4.6 um",
    },
    {
        "asset": GAIA_FILE,
        "survey": "Gaia DR3",
        "provider": "NASA/IPAC IRSA TAP",
        "credit": "ESA/Gaia/DPAC, Gaia DR3",
    },
)

ASSET_TYPES = {
    OPTICAL_FILE: {"kind": "optical", "survey": DSS2_SURVEY, "wavelength_um": None},
    WISE_W1_FILE: {"kind": "mid_ir", "survey": WISE_W1_SURVEY, "wavelength_um": 3.4},
    WISE_W2_FILE: {"kind": "mid_ir", "survey": WISE_W2_SURVEY, "wavelength_um": 4.6},
}


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(content: bytes) -> str:
    import hashlib  # noqa: PLC0415 - tiny, keep module import light

    return hashlib.sha256(content).hexdigest()


def sha256_text_bytes(content: bytes) -> str:
    """SHA-256 of text content with CRLF/CR normalized to LF.

    Reference JSON assets are committed as text.  A Windows checkout with
    ``core.autocrlf=true`` can materialize them with CRLF while the recorded
    hash is computed on LF; normalizing keeps the provenance stable.  Never
    use this for binary WebP/gzip assets.
    """
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_bytes(normalized)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)
    _atomic_write(path, (text + "\n").encode("utf-8"))


def asset_url(target_id: str, filename: str) -> str:
    """Contract asset URL for a golden-cache file."""
    return f"/api/v1/assets/{target_id}/{filename}"


def local_reference_filenames(
    manifest: dict[str, Any], target_id: str
) -> list[str]:
    """Local files referenced by ``reference_overlays``.

    The manifest stores contract asset URLs.  This helper maps
    ``/api/v1/assets/{target_id}/<file>`` back to ``<file>`` so the build and
    verification code can hash/prune the actual golden-cache files.  External
    URLs and non-file values are ignored.
    """
    names: list[str] = []
    prefix = f"/api/v1/assets/{target_id}/"
    for value in (manifest.get("reference_overlays") or {}).values():
        if not isinstance(value, str) or not value:
            continue
        name = value
        if name.startswith(prefix):
            name = name[len(prefix) :]
        elif name.startswith(("http://", "https://", "/")):
            continue
        if not _SAFE_FILENAME.fullmatch(name):
            continue
        if name not in names:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# SkyView FITS retrieval
# ---------------------------------------------------------------------------
def _skyview_params(survey: str, ra: float, dec: float, pixels: int) -> dict[str, str]:
    return {
        "Survey": survey,
        "position": f"{float(ra):.5f},{float(dec):.5f}",
        "size": f"{FOV_DEG:.3f}",
        "pixels": str(int(pixels)),
        "return": "FITS",
    }


def fetch_skyview(
    survey: str,
    ra: float,
    dec: float,
    *,
    pixels: int = PIXELS,
    attempts: int = 4,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Fetch a SkyView FITS cutout, rejecting blank one-element responses.

    Returns a dict with ``ok``, ``data`` (float64), ``header``, ``request_url``
    and a compact ``attempts`` history.  Never raises for network/service
    failures; callers decide whether to retry at a smaller pixel count.
    """
    params = _skyview_params(survey, ra, dec, pixels)
    request_url = str(httpx.URL(SKYVIEW_URL, params=params))
    result: dict[str, Any] = {
        "ok": False,
        "survey": survey,
        "requested_pixels": int(pixels),
        "request_url": request_url,
        "params": params,
        "attempts": [],
        "data": None,
        "header": None,
    }
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    connect=20.0, read=timeout, write=30.0, pool=20.0
                ),
                follow_redirects=True,
                headers={"User-Agent": "SPHEREx-SkyBlink-S4/1.0"},
            ) as client:
                response = client.get(SKYVIEW_URL, params=params)
            elapsed = time.perf_counter() - started
            content = response.content
            log: dict[str, Any] = {
                "attempt": attempt,
                "status": response.status_code,
                "latency_s": round(elapsed, 3),
                "content_type": response.headers.get("content-type"),
                "bytes": len(content),
                "ok": False,
            }
            if response.status_code == 200 and content[:6] == b"SIMPLE":
                # SkyView returns a single-HDU FITS whose image lives in the
                # primary HDU.  This is *not* a SPHEREx MEF: the SPHEREx
                # guardrail forbids relying on an empty primary HDU, so the
                # primary is accessed through an explicit handle here.
                with fits.open(BytesIO(content), memmap=False) as hdul:
                    primary = hdul[0]
                    data = primary.data
                    header = primary.header.copy()
                if data is not None and getattr(data, "ndim", 0) == 2 and data.size > 1:
                    array = np.asarray(data, dtype=np.float64)
                    log["ok"] = True
                    log["shape"] = list(array.shape)
                    log["finite_fraction"] = float(np.mean(np.isfinite(array)))
                    result.update(
                        {
                            "ok": True,
                            "status": response.status_code,
                            "content_type": response.headers.get("content-type"),
                            "data": array,
                            "header": header,
                            "bytes": len(content),
                            "latency_s": round(elapsed, 3),
                        }
                    )
                else:
                    log["shape"] = list(np.shape(data))
                    log["note"] = (
                        "SkyView returned a blank 1-element FITS; retrying."
                    )
            else:
                log["note"] = "non-FITS or non-200 response"
                log["body_prefix"] = content[:120].decode(
                    "utf-8", errors="replace"
                ).replace("\n", " ")
            result["attempts"].append(log)
            if result["ok"]:
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


def _wcs_matches_golden(header: fits.Header, ra: float, dec: float) -> bool:
    """True when a 240 x 240 FITS header is already the contract grid."""
    try:
        incoming = WCS(header)
    except Exception:  # noqa: BLE001 - a bad header is simply "no match"
        return False
    if int(header.get("NAXIS1", 0)) != GRID_WIDTH or int(
        header.get("NAXIS2", 0)
    ) != GRID_HEIGHT:
        return False
    golden = output_wcs(ra, dec)
    xs = np.array([0.0, GRID_WIDTH - 1.0, 0.0, GRID_WIDTH - 1.0, 119.5])
    ys = np.array([0.0, 0.0, GRID_HEIGHT - 1.0, GRID_HEIGHT - 1.0, 119.5])
    with np.errstate(all="ignore"):
        try:
            expected = golden.pixel_to_world(xs, ys)
            actual = incoming.pixel_to_world(xs, ys)
            separation_arcsec = np.asarray(
                expected.separation(actual).to_value("arcsec"), dtype=float
            )
        except Exception:  # noqa: BLE001
            return False
    return bool(np.all(np.isfinite(separation_arcsec))) and float(
        np.max(separation_arcsec)
    ) < 0.05


def to_golden_grid(
    data: np.ndarray, header: fits.Header, ra: float, dec: float
) -> tuple[np.ndarray, bool]:
    """Reproject a survey cutout onto the contract 240 x 240 TAN grid.

    Returns ``(array, resampled)``.  A cutout that already matches the golden
    grid is used directly; anything else (a 200 x 200 fallback, a padded or
    rotated SkyView grid) is reprojected with bilinear interpolation.
    """
    if data.shape == (GRID_HEIGHT, GRID_WIDTH) and _wcs_matches_golden(
        header, ra, dec
    ):
        return np.asarray(data, dtype=np.float64), False
    incoming = WCS(header)
    golden = output_wcs(ra, dec)
    resampled, _footprint = reproject_interp(
        (np.asarray(data, dtype=np.float64), incoming),
        golden,
        shape_out=(GRID_HEIGHT, GRID_WIDTH),
        order="bilinear",
    )
    return np.asarray(resampled, dtype=np.float64), True


def write_display_webp(
    data: np.ndarray,
    path: Path,
    *,
    lower: float = STRETCH_PERCENTILES[0],
    upper: float = STRETCH_PERCENTILES[1],
    quality: int = WEBP_QUALITY,
) -> dict[str, Any]:
    """Write an 8-bit display WebP with a percentile linear stretch."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError(f"{path.name}: no finite pixels to render")
    lo = float(np.percentile(finite, lower))
    hi = float(np.percentile(finite, upper))
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((np.nan_to_num(data, nan=lo) - lo) / (hi - lo), 0.0, 1.0)
    pixels = np.round(scaled * 255.0).astype(np.uint8)
    image = Image.fromarray(pixels, mode="L")
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=int(quality), method=6)
    content = buffer.getvalue()
    _atomic_write(path, content)
    return {
        "bytes": len(content),
        "sha256": sha256_bytes(content),
        "stretch_percentiles": [float(lower), float(upper)],
        "stretch_limits": [lo, hi],
        "quality": int(quality),
        "mode": "L",
        "shape": [int(data.shape[0]), int(data.shape[1])],
    }


# ---------------------------------------------------------------------------
# Gaia DR3 pins via IRSA TAP
# ---------------------------------------------------------------------------
def _tap_query(query: str, *, timeout: float = 180.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    with httpx.Client(
        timeout=httpx.Timeout(connect=15.0, read=timeout, write=30.0, pool=15.0),
        follow_redirects=True,
        headers={"User-Agent": "SPHEREx-SkyBlink-S4/1.0"},
    ) as client:
        response = client.get(TAP_URL, params={"query": query, "format": "votable"})
    elapsed = time.perf_counter() - started
    if response.status_code >= 400:
        raise RuntimeError(f"TAP HTTP {response.status_code}: {response.text[:300]}")
    rows = _rows_from_votable(response.content)
    return rows, {
        "status": response.status_code,
        "latency_s": round(elapsed, 3),
        "votable_bytes": len(response.content),
    }


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fetch_gaia(
    ra: float,
    dec: float,
    *,
    radius_deg: float = GAIA_RADIUS_DEG,
    g_limit: float = GAIA_G_LIMIT,
    cap: int = GAIA_CAP,
) -> dict[str, Any]:
    """Query ``gaia_dr3_source`` for display pins around (ra, dec).

    Applies ``phot_g_mean_mag <= g_limit`` and a hard ``TOP cap`` so the JSON
    stays a display asset (Barnard's Star has 455 sources at G <= 16 within
    0.2 deg).  Null proper motions are preserved as JSON ``null``; rows are
    sorted brightest-first.  ``source_id`` is serialized as a string because
    Gaia identifiers exceed the JavaScript safe-integer range.
    """
    position = (
        "1=CONTAINS(POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {float(ra):.6f}, {float(dec):.6f}, {float(radius_deg):.4f}))"
    )
    counts_query = f"""SELECT COUNT(*) AS n_all,
      SUM(CASE WHEN phot_g_mean_mag <= {float(g_limit):.1f} THEN 1 ELSE 0 END) AS n_g_limit
FROM gaia_dr3_source
WHERE {position}"""
    count_rows, count_meta = _tap_query(counts_query)
    counts = count_rows[0] if count_rows else {}

    rows_query = f"""SELECT TOP {int(cap)} source_id, ra, dec, phot_g_mean_mag, pmra, pmdec
FROM gaia_dr3_source
WHERE {position} AND phot_g_mean_mag <= {float(g_limit):.1f}
ORDER BY phot_g_mean_mag ASC"""
    rows, rows_meta = _tap_query(rows_query)

    sources: list[dict[str, Any]] = []
    null_pm = 0
    for row in rows:
        g_mag = _finite_or_none(row.get("phot_g_mean_mag"))
        ra_value = _finite_or_none(row.get("ra"))
        dec_value = _finite_or_none(row.get("dec"))
        if ra_value is None or dec_value is None:
            continue
        pmra = _finite_or_none(row.get("pmra"))
        pmdec = _finite_or_none(row.get("pmdec"))
        if pmra is None or pmdec is None:
            null_pm += 1
        source_id = row.get("source_id")
        sources.append(
            {
                "source_id": str(int(source_id)) if source_id is not None else "",
                "ra": ra_value,
                "dec": dec_value,
                "g_mag": g_mag,
                "pmra": pmra,
                "pmdec": pmdec,
                "label": f"G={g_mag:.2f}" if g_mag is not None else "Gaia DR3",
            }
        )

    return {
        "endpoint": TAP_URL,
        "table": "gaia_dr3_source",
        "query": {
            "ra": float(ra),
            "dec": float(dec),
            "radius_deg": float(radius_deg),
            "g_limit": float(g_limit),
            "cap": int(cap),
            "total_all": int(counts.get("n_all") or 0),
            "total_g_le_limit": int(counts.get("n_g_limit") or 0),
            "returned": len(sources),
            "truncated": int(counts.get("n_g_limit") or 0) > len(sources),
            "null_pm_count": null_pm,
        },
        "count_meta": count_meta,
        "rows_meta": rows_meta,
        "sources": sources,
    }


def write_gaia_json(
    path: Path, target_id: str, ra: float, dec: float, gaia: dict[str, Any]
) -> dict[str, Any]:
    payload = {
        "target_id": target_id,
        "generated_at": now_utc(),
        "is_simulated_fallback": False,
        "source": "NASA/IPAC IRSA TAP gaia_dr3_source (Gaia DR3)",
        "attribution": "ESA/Gaia/DPAC, Gaia DR3; retrieved via NASA/IPAC IRSA TAP.",
        "frame": "ICRS",
        "reference_epoch": "J2016.0 (Gaia DR3 reference epoch)",
        "note": (
            "Display pins only, not calibrated photometry. Positions are at "
            "the Gaia DR3 reference epoch J2016.0; pmra/pmdec (mas/yr, "
            "mu_alpha* cos delta for pmra) are included so the frontend can "
            "propagate pins to another epoch. Null proper motions are kept "
            "as null; source_id is a string because it exceeds the "
            "JavaScript safe-integer range."
        ),
        **gaia,
    }
    _atomic_write_json(path, payload)
    content = path.read_bytes()
    return {
        "bytes": len(content),
        "sha256": sha256_text_bytes(content),
        "is_simulated_fallback": False,
        "query": payload["query"],
        "source": payload["source"],
        "attribution": payload["attribution"],
    }


def write_attribution_json(path: Path, target_id: str) -> dict[str, Any]:
    payload = {
        "target_id": target_id,
        "generated_at": now_utc(),
        "is_simulated_fallback": False,
        "note": (
            "Reference/display fields only. These surveys are not SPHEREx "
            "data and are not calibrated photometry; the stretch is chosen "
            "for display."
        ),
        "attribution_text": ATTRIBUTION_TEXT,
        "credits": list(CREDITS),
    }
    _atomic_write_json(path, payload)
    content = path.read_bytes()
    return {
        "bytes": len(content),
        "sha256": sha256_text_bytes(content),
        "is_simulated_fallback": False,
        "attribution_text": ATTRIBUTION_TEXT,
    }


# ---------------------------------------------------------------------------
# Per-target orchestration
# ---------------------------------------------------------------------------
def _expected_image_assets(target_id: str) -> list[str]:
    files = [OPTICAL_FILE, WISE_W1_FILE]
    if target_id in WISE_W2_TARGETS:
        files.append(WISE_W2_FILE)
    return files


def _survey_for(filename: str) -> str:
    return {
        OPTICAL_FILE: DSS2_SURVEY,
        WISE_W1_FILE: WISE_W1_SURVEY,
        WISE_W2_FILE: WISE_W2_SURVEY,
    }[filename]


def _build_image_asset(
    target_id: str,
    target_dir: Path,
    filename: str,
    ra: float,
    dec: float,
) -> dict[str, Any]:
    """Fetch one survey cutout, resample to the golden grid, and write WebP."""
    survey = _survey_for(filename)
    primary = fetch_skyview(survey, ra, dec, pixels=PIXELS, attempts=4)
    fetch = primary
    fallback = None
    if not fetch["ok"]:
        logger.warning(
            "%s: %s 240x240 FITS unusable after retries; trying 200x200",
            target_id,
            survey,
        )
        fallback = fetch_skyview(survey, ra, dec, pixels=200, attempts=3)
        if fallback["ok"]:
            fetch = fallback
    if not fetch["ok"]:
        raise RuntimeError(
            f"{target_id}: SkyView {survey} failed; attempts="
            f"{fetch['attempts'][-1] if fetch['attempts'] else 'none'}"
        )

    golden_data, resampled = to_golden_grid(
        fetch["data"], fetch["header"], ra, dec
    )
    finite_fraction = float(np.mean(np.isfinite(golden_data)))
    if finite_fraction < 0.5:
        raise RuntimeError(
            f"{target_id}: {survey} reprojected coverage is only "
            f"{finite_fraction:.2%}; refusing a mostly-empty overlay"
        )
    display = write_display_webp(golden_data, target_dir / filename)
    asset = {
        **ASSET_TYPES[filename],
        "file": filename,
        "service_url": SKYVIEW_URL,
        "request_url": fetch["request_url"],
        "request_params": fetch["params"],
        "requested_pixels": int(fetch["requested_pixels"]),
        "fallback_200_used": bool(fallback is not None),
        "primary_request_url": primary["request_url"],
        "primary_requested_pixels": int(primary["requested_pixels"]),
        "primary_attempts": primary["attempts"],
        "http_status": fetch.get("status"),
        "content_type": fetch.get("content_type"),
        "attempts": fetch["attempts"],
        "fetched_at": now_utc(),
        "input_shape": list(np.shape(fetch["data"])),
        "output_shape": [GRID_HEIGHT, GRID_WIDTH],
        "resampled_to_golden_grid": bool(resampled),
        "golden_grid": (
            f"{GRID_WIDTH}x{GRID_HEIGHT} TAN, north-up, "
            "3.075 arcsec/pixel, CRPIX=(120.5, 120.5)"
        ),
        "finite_fraction": finite_fraction,
        "display": {
            "stretch_percentiles": display["stretch_percentiles"],
            "stretch_limits": display["stretch_limits"],
            "quality": display["quality"],
            "mode": display["mode"],
        },
        "bytes": display["bytes"],
        "sha256": display["sha256"],
        "is_simulated_fallback": False,
        "limitations": (
            "Display-only reference field, not calibrated photometry and not "
            "SPHEREx data. The target may not be detected at this wavelength."
        ),
    }
    logger.info(
        "%s: %s -> %s (%d bytes, resampled=%s, fallback_200=%s)",
        target_id,
        survey,
        filename,
        display["bytes"],
        resampled,
        fallback is not None,
    )
    return asset


def ensure_reference_overlays(
    target_id: str,
    target_dir: Path,
    ra: float,
    dec: float,
    *,
    fetch_missing: bool = True,
    force: bool = False,
    reuse: dict[str, Any] | None = None,
    gaia_cap: int = GAIA_CAP,
    gaia_g_limit: float = GAIA_G_LIMIT,
) -> dict[str, Any]:
    """Materialize the real overlay/Gaia assets for one target.

    Existing assets are reused when their recorded SHA-256 still matches and
    ``force`` is not set, so an S4 rebuild does not re-download ~30 MB of
    survey cutouts.  Missing assets require ``fetch_missing``.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    reuse_assets: dict[str, Any] = {}
    if isinstance(reuse, dict) and reuse.get("target_id") in {None, target_id}:
        reuse_assets = reuse.get("assets") or {}
    assets: dict[str, Any] = {}

    for filename in _expected_image_assets(target_id):
        path = target_dir / filename
        recorded = reuse_assets.get(filename) if isinstance(reuse_assets, dict) else None
        if (
            not force
            and path.is_file()
            and isinstance(recorded, dict)
            and recorded.get("sha256") == sha256_bytes(path.read_bytes())
        ):
            assets[filename] = dict(recorded)
            logger.info("%s: reusing %s (sha256 verified)", target_id, filename)
            continue
        if not fetch_missing:
            raise FileNotFoundError(
                f"{target_id}: {filename} missing and fetch_missing=False"
            )
        assets[filename] = _build_image_asset(
            target_id, target_dir, filename, ra, dec
        )

    gaia_path = target_dir / GAIA_FILE
    recorded_gaia = reuse_assets.get(GAIA_FILE) if isinstance(reuse_assets, dict) else None
    if (
        not force
        and gaia_path.is_file()
        and isinstance(recorded_gaia, dict)
        and recorded_gaia.get("sha256") == sha256_text_bytes(gaia_path.read_bytes())
    ):
        assets[GAIA_FILE] = dict(recorded_gaia)
        logger.info("%s: reusing %s (sha256 verified)", target_id, GAIA_FILE)
    else:
        if not fetch_missing:
            raise FileNotFoundError(
                f"{target_id}: {GAIA_FILE} missing and fetch_missing=False"
            )
        gaia = fetch_gaia(
            ra, dec, radius_deg=GAIA_RADIUS_DEG, g_limit=gaia_g_limit, cap=gaia_cap
        )
        assets[GAIA_FILE] = write_gaia_json(gaia_path, target_id, ra, dec, gaia)
        logger.info(
            "%s: Gaia DR3 %d/%d pins (G<=%.1f, cap %d, null_pm=%d)",
            target_id,
            gaia["query"]["returned"],
            gaia["query"]["total_g_le_limit"],
            gaia_g_limit,
            gaia_cap,
            gaia["query"]["null_pm_count"],
        )

    # The credit bundle is tiny and deterministic apart from generated_at;
    # always refresh so the attribution cannot drift from the assets.
    assets[ATTRIBUTION_FILE] = {
        "file": ATTRIBUTION_FILE,
        **write_attribution_json(target_dir / ATTRIBUTION_FILE, target_id),
    }

    return {
        "is_simulated_fallback": False,
        "generated_at": now_utc(),
        "generated_by": "scripts/reference_overlays.py",
        "target_id": target_id,
        "query_center": {"ra": float(ra), "dec": float(dec)},
        "display_only": True,
        "display_note": (
            "Reference/display products only. They never replace SPHEREx "
            "frames, never feed photometry, and are not calibrated "
            "photometry."
        ),
        "attribution_text": ATTRIBUTION_TEXT,
        "credits": list(CREDITS),
        "assets": assets,
    }


def reference_overlay_url_map(target_id: str) -> dict[str, str]:
    """Contract ``reference_overlays`` map.

    ``optical_dss2_red``/``mid_ir_wise*``/``gaia_sources_url`` are asset URLs.
    ``attribution`` is human-readable prose metadata (the backend preserves it
    verbatim and never treats it as an asset filename).  The structured credit
    bundle is exposed separately as ``attribution_json``.
    """
    overlays = {
        # 1.0.0 keys (kept; now backed by real survey cutouts).
        "optical_dss_gaia": asset_url(target_id, OPTICAL_FILE),
        "mid_ir_wise": asset_url(target_id, WISE_W1_FILE),
        # 1.1.0 keys.
        "optical_dss2_red": asset_url(target_id, OPTICAL_FILE),
        "mid_ir_wise_w1": asset_url(target_id, WISE_W1_FILE),
        "gaia_sources_url": asset_url(target_id, GAIA_FILE),
        "attribution": ATTRIBUTION_TEXT,
        "attribution_json": asset_url(target_id, ATTRIBUTION_FILE),
    }
    if target_id in WISE_W2_TARGETS:
        overlays["mid_ir_wise_w2"] = asset_url(target_id, WISE_W2_FILE)
    return overlays


NOTE_LINE = (
    "Real reference overlays: DSS2 Red (NASA/GSFC SkyView; STScI), WISE "
    "3.4 um and WISE 4.6 um for WISE 0855 (NASA/GSFC SkyView; "
    "NASA/JPL/Caltech), and Gaia DR3 pins via IRSA TAP. Display-only, not "
    "calibrated photometry, is_simulated_fallback=false."
)


def apply_reference_overlays(
    manifest: dict[str, Any],
    target_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Merge the overlay map/provenance into a golden manifest."""
    manifest["reference_overlays"] = reference_overlay_url_map(target_id)
    metadata = dict(metadata)
    metadata["reference_overlay_urls"] = dict(manifest["reference_overlays"])
    manifest["reference_overlay_provenance"] = metadata
    notes = manifest.setdefault("notes", [])
    if NOTE_LINE not in notes:
        notes.append(NOTE_LINE)
    return manifest


def reference_asset_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    """Compact integrity/status summary for logs, validation and tests."""
    target_id = str(manifest.get("target_id", ""))
    files = local_reference_filenames(manifest, target_id)
    provenance = manifest.get("reference_overlay_provenance") or {}
    assets = provenance.get("assets") or {}
    total_bytes = int(sum(int((assets.get(name) or {}).get("bytes", 0)) for name in files))
    gaia = assets.get(GAIA_FILE) or {}
    return {
        "keys": sorted((manifest.get("reference_overlays") or {}).keys()),
        "files": files,
        "count": len(files),
        "total_bytes": total_bytes,
        "is_simulated_fallback": bool(provenance.get("is_simulated_fallback")),
        "gaia_returned": int((gaia.get("query") or {}).get("returned", 0) or 0),
        "gaia_total_g_le_limit": int(
            (gaia.get("query") or {}).get("total_g_le_limit", 0) or 0
        ),
    }
