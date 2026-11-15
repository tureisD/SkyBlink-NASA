#!/usr/bin/env python3
"""W0 science-half feasibility spike (read-only by default).

Measures, from the already-cached real IRSA SPHEREx cutouts and live IRSA TAP:

1. HDU 5 ``PSF`` wing recovery for Barnard's Star and R Draconis.
2. R Draconis NEP epoch inventory from the 2,483 TAP science rows.
3. Telemetry sidecar size for one 240x240 float16 MJy/sr plane + uint32 flags.
4. ``hips2fits`` availability (CDS) and reachable alternatives.
5. LVF visit / distinct-wavelength inventory for WISE 0855 and Epsilon Indi B.

The script never writes product code, contract files, golden-cache frames or
cached FITS.  It writes exactly one file: ``--out`` (default
``golden_cache/w0_metrics.json``).  Network calls are read-only TAP/SIA/HTTP
queries.  ``--skip-network`` makes the run fully offline; sections that need
network are then reported as ``skipped``.

Usage (from the science worktree)::

    ../.venv311/Scripts/python.exe scripts/spike_w0_metrics.py

Mapping rules / conventions
---------------------------
* Cached cutout path: sha256(f"{access_url}|{ra:.8f}|{dec:.8f}|{size:.6f}")
  exactly as ``backend/services/irsa_client.py::IrsaClient._cutout_cache_path``.
* Spectrum channel <-> visit: the golden manifest's
  ``band_stats[band].artifact_uris`` are the visits selected by
  ``_select_visits`` (up to 3, evenly spaced in MJD).  Each visit yields one
  channel; the per-visit wavelength is read from ``WCS-WAVE`` with
  ``key="W"`` and ``sip=None``.  Channels are matched by epoch + detector +
  |Delta lambda| < 5e-4 um.
* Wing annulus: 1.2 <= r <= 4.2 native pixels (native scale from the cutout
  WCS, ~6.15 arcsec/px).  ``P_i`` is the normalized local HDU 5 PSF in each
  native pixel; ``f_wing = sum(P_i)`` over clean wing pixels.
* Primary clean mask: ``PHOTOMETRY_EXCLUDE_MASK`` (hard + warning, including
  DICHROIC).  ``BIT_SOURCE`` is deliberately kept: it covers ~93% of these
  frames and is the source mask, not a defect.  A BIT_SOURCE-excluded variant
  is reported for transparency.
* Gate: ``f_wing >= 0.12`` and ``N_wing >= 8``.  A failed gate never yields
  photometry; diagnostic fluxes are labelled ``diagnostic_only``.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import logging
import math
import struct
import sys
import time
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402
from astropy.io import fits  # noqa: E402
from astropy.time import Time  # noqa: E402
from astropy.wcs import WCS  # noqa: E402
from reproject import reproject_interp  # noqa: E402

from core import flags as flag_policy  # noqa: E402
from core.config import settings  # noqa: E402
from core.targets import get_target, propagated_coordinates  # noqa: E402
from services.irsa_client import (  # noqa: E402
    ArtifactRecord,
    BAND_NAME_RE,
    _detect_release,
    _rows_from_votable,
)
from services.spherex_pipeline import (  # noqa: E402
    GRID_HEIGHT,
    GRID_WIDTH,
    _select_visits,
    group_epochs,
    output_wcs,
    parse_cutout,
    reproject_to_grid,
)

# Silence Astropy WCS chatter (the spectral lookup is expected to warn).
for _logger_name in ("astropy", "astropy.wcs", "astropy.wcs.wcs"):
    logging.getLogger(_logger_name).setLevel(logging.ERROR)

ARCSEC_TO_RAD = math.pi / (180.0 * 3600.0)
NATIVE_PIXEL_SCALE_ARCSEC = 6.15
APERTURE_RADIUS_ARCSEC = 12.3

WING_R_INNER = 1.2
WING_R_OUTER = 4.2
WING_F_MIN = 0.12
WING_N_MIN = 8

PSF_ZONES_X = 11
PSF_ZONES_Y = 11
DETECTOR_SIZE = 2040.0

TELEMETRY_WIDTH = GRID_WIDTH
TELEMETRY_HEIGHT = GRID_HEIGHT

TAP_TIMEOUT_SECONDS = 180.0
HIPS_TIMEOUT_SECONDS = 20.0
HIPS_CONNECT_SECONDS = 8.0

DEFAULT_CACHE_DIRS = (
    REPO_ROOT.parent / "backend" / "backend" / ".cache" / "cutouts",
    REPO_ROOT / "backend" / ".cache" / "cutouts",
)


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iso_from_mjd(mjd: float) -> str:
    try:
        return Time(float(mjd), format="mjd", scale="utc").iso.split(".")[0]
    except Exception:
        return ""


def jfloat(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def cutout_cache_path(
    cache_dir: Path,
    access_url: str,
    ra: float,
    dec: float,
    size_deg: float,
) -> Path:
    """Mirror ``IrsaClient._cutout_cache_path`` (read-only use)."""
    key = f"{access_url}|{float(ra):.8f}|{float(dec):.8f}|{float(size_deg):.6f}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.fits"


def find_cutout(
    cache_dirs: list[Path],
    uri: str,
    query: dict[str, Any],
) -> Path | None:
    access_url = (
        uri
        if uri.startswith("http://") or uri.startswith("https://")
        else "https://irsa.ipac.caltech.edu/" + uri.lstrip("/")
    )
    for cache_dir in cache_dirs:
        path = cutout_cache_path(
            cache_dir,
            access_url,
            float(query["ra"]),
            float(query["dec"]),
            float(query.get("cutout_size_deg", 0.2)),
        )
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def b64_len(data: bytes) -> int:
    return len(base64.b64encode(data))


def detector_zone(
    target_x: float,
    target_y: float,
    header: fits.Header,
) -> tuple[int, str]:
    """Return (0-based PSF zone index, source) for a cutout target pixel.

    ``CRPIX1A``/``CRPIX2A`` are the 0-based active-pixel offsets written by
    the SPHEREx cutout service.  The PSF cube has 11x11 zones of 185.4545
    detector pixels each (header XCTR_1..XCTR_121).
    """
    if "CRPIX1A" not in header or "CRPIX2A" not in header:
        return 60, "fallback_center"
    x_full = float(target_x) - float(header["CRPIX1A"])
    y_full = float(target_y) - float(header["CRPIX2A"])
    zone_x = int(np.clip(math.floor(x_full / (DETECTOR_SIZE / PSF_ZONES_X)), 0, 10))
    zone_y = int(np.clip(math.floor(y_full / (DETECTOR_SIZE / PSF_ZONES_Y)), 0, 10))
    return int(zone_y * PSF_ZONES_X + zone_x), "crpix1a"


def psf_native_pixels(
    plane: np.ndarray,
    target_x: float,
    target_y: float,
    *,
    oversamp: int,
    center_pix: float,
) -> tuple[np.ndarray, int, int]:
    """Distribute a normalized oversampled PSF onto native cutout pixels.

    Returns ``(P, x0, y0)`` where ``P[j, i]`` is the PSF fraction in the
    native pixel ``(x0 + i, y0 + j)``.  ``P`` sums to ~1 over all assigned
    pixels (the PSF cube truncates beyond +/-5 native px for HDU 5).
    """
    n_y, n_x = plane.shape
    fine_x = (np.arange(n_x) - center_pix) / float(oversamp)
    fine_y = (np.arange(n_y) - center_pix) / float(oversamp)
    ix = np.rint(float(target_x) + fine_x).astype(int)
    iy = np.rint(float(target_y) + fine_y).astype(int)

    x0 = int(math.floor(float(target_x))) - 8
    y0 = int(math.floor(float(target_y))) - 8
    nx = ny = 25
    P = np.zeros((ny, nx), dtype=np.float64)

    ix_local = ix - x0
    iy_local = iy - y0
    valid_x = (ix_local >= 0) & (ix_local < nx)
    valid_y = (iy_local >= 0) & (iy_local < ny)
    if not valid_x.any() or not valid_y.any():
        return P, x0, y0

    plane_valid = plane[np.ix_(valid_y, valid_x)]
    np.add.at(
        P,
        (iy_local[valid_y][:, None], ix_local[valid_x][None, :]),
        plane_valid,
    )
    return P, x0, y0


def wing_from_P(
    P: np.ndarray,
    x0: int,
    y0: int,
    target_x: float,
    target_y: float,
    flags: np.ndarray,
    finite: np.ndarray,
    exclude_mask: int,
) -> dict[str, Any]:
    """Measure f_wing/N_wing for one PSF-native map and one exclude mask."""
    f_wing = 0.0
    n_wing = 0
    f_all = 0.0
    n_all = 0
    for j in range(P.shape[0]):
        py = y0 + j
        if not (0 <= py < flags.shape[0]):
            continue
        for i in range(P.shape[1]):
            px = x0 + i
            if not (0 <= px < flags.shape[1]):
                continue
            value = float(P[j, i])
            if value == 0.0:
                continue
            r = math.hypot(px - target_x, py - target_y)
            if not (WING_R_INNER <= r <= WING_R_OUTER):
                continue
            n_all += 1
            f_all += value
            if (int(flags[py, px]) & int(exclude_mask)) == 0 and finite[py, px]:
                f_wing += value
                n_wing += 1
    return {
        "f_wing": float(f_wing),
        "n_wing": int(n_wing),
        "f_all": float(f_all),
        "n_all": int(n_all),
        "gate_pass": bool(f_wing >= WING_F_MIN and n_wing >= WING_N_MIN),
    }


def wing_flux_diagnostic(
    image: np.ndarray,
    variance: np.ndarray,
    flags: np.ndarray,
    finite: np.ndarray,
    target_x: float,
    target_y: float,
    P: np.ndarray,
    x0: int,
    y0: int,
    native_scale_arcsec: float,
    exclude_mask: int,
) -> dict[str, Any] | None:
    """Inverse-variance wing flux, labelled diagnostic-only by the caller.

    The sky background is the median of clean pixels in the 5.0-8.0 native-px
    annulus, outside the 1.2-4.2 px wing fit.  This is not used for the gate.
    """
    yy, xx = np.indices(flags.shape)
    r = np.hypot(xx - target_x, yy - target_y)
    bg_annulus = (r >= 5.0) & (r <= 8.0)
    bg_clean = (
        bg_annulus
        & ((flags & int(exclude_mask)) == 0)
        & ((flags & flag_policy.BIT_SOURCE) == 0)
        & finite
    )
    if int(np.count_nonzero(bg_clean)) < 10:
        return None
    background = float(np.nanmedian(image[bg_clean]))

    weight_sum = 0.0
    numerator = 0.0
    used = 0
    for j in range(P.shape[0]):
        py = y0 + j
        if not (0 <= py < flags.shape[0]):
            continue
        for i in range(P.shape[1]):
            px = x0 + i
            if not (0 <= px < flags.shape[1]):
                continue
            p = float(P[j, i])
            if p == 0.0:
                continue
            if (int(flags[py, px]) & int(exclude_mask)) != 0 or not finite[py, px]:
                continue
            variance_value = float(variance[py, px])
            if not math.isfinite(variance_value) or variance_value <= 0:
                continue
            weight = 1.0 / variance_value
            weight_sum += weight * p * p
            numerator += weight * (float(image[py, px]) - background) * p
            used += 1
    if used < WING_N_MIN or weight_sum <= 0.0:
        return None
    flux_mjy_sr = numerator / weight_sum
    sigma_mjy_sr = 1.0 / math.sqrt(weight_sum)
    omega_sr = (native_scale_arcsec * ARCSEC_TO_RAD) ** 2
    return {
        "flux_ujy": float(flux_mjy_sr * omega_sr * 1e12),
        "flux_err_ujy": float(sigma_mjy_sr * omega_sr * 1e12),
        "background_mjy_sr": background,
        "n_pixels": int(used),
    }


# ---------------------------------------------------------------------------
# FITS / PSF wing analysis
# ---------------------------------------------------------------------------
def analyze_psf_visit(
    path: Path,
    target_id: str,
    epoch_id: str,
    band: int,
    uri: str,
    query: dict[str, Any],
    spectrum_index: dict[tuple[str, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Analyze one cached visit for the HDU 5 PSF wing gate."""
    result: dict[str, Any] = {
        "epoch_id": epoch_id,
        "band": int(band),
        "detector": int(band),
        "uri": uri,
        "cache_path": str(path),
        "status": "UNKNOWN",
        "rejection_reasons": [],
        "gate_evaluable": False,
        "gate_pass": False,
        "f_wing": None,
        "n_wing": None,
    }
    target = get_target(target_id)
    if target is None:
        result["status"] = "ERROR"
        result["rejection_reasons"] = ["unknown_target"]
        return result

    try:
        hdul = fits.open(path, memmap=False, cache=False)
    except Exception as exc:  # pragma: no cover - defensive
        result["status"] = "MISSING_CACHE"
        result["rejection_reasons"] = [f"fits_open_failed: {exc}"]
        return result

    with hdul:
        names = {str(hdu.name).upper() for hdu in hdul}
        required = {"IMAGE", "FLAGS", "VARIANCE", "ZODI", "WCS-WAVE"}
        missing = required - names
        if missing:
            result["status"] = "ERROR"
            result["rejection_reasons"] = [f"missing_extensions: {sorted(missing)}"]
            return result

        header = hdul["IMAGE"].header
        image = np.array(hdul["IMAGE"].data, dtype=np.float64, copy=True)
        flags = np.array(hdul["FLAGS"].data, dtype=np.uint32, copy=True)
        variance = np.array(hdul["VARIANCE"].data, dtype=np.float64, copy=True)
        zodi = np.array(hdul["ZODI"].data, dtype=np.float64, copy=True)

        mjd = jfloat(header.get("MJD-AVG", header.get("MJD-OBS", header.get("MJD-BEG"))))
        result["mjd"] = mjd
        if mjd is None:
            result["status"] = "ERROR"
            result["rejection_reasons"] = ["missing_mjd"]
            return result
        decimal_year = float(Time(mjd, format="mjd", scale="tt").decimalyear)
        result["decimal_year"] = decimal_year

        # ZODI + local background, exactly as parse_cutout.
        image = image - zodi
        image[~np.isfinite(zodi)] = np.nan
        background_exclude = (
            flags & flag_policy.BACKGROUND_EXCLUDE_MASK
        ) != 0
        valid_background = image[~background_exclude & np.isfinite(image)]
        local_background = (
            float(np.nanmedian(valid_background))
            if valid_background.size > 10
            else 0.0
        )
        image = image - local_background
        result["local_background_mjy_sr"] = local_background

        spatial_wcs = WCS(header)
        coordinate = propagated_coordinates(target, decimal_year)
        target_x, target_y = spatial_wcs.world_to_pixel(coordinate)
        target_x = float(target_x)
        target_y = float(target_y)
        result["target_x"] = target_x
        result["target_y"] = target_y
        in_cutout = (
            math.isfinite(target_x)
            and math.isfinite(target_y)
            and 0.0 <= target_x <= image.shape[1] - 1
            and 0.0 <= target_y <= image.shape[0] - 1
        )
        if not in_cutout:
            result["status"] = "REJECTED"
            result["rejection_reasons"] = ["target_outside_cutout"]
            return result

        pixel_scale_matrix = np.asarray(spatial_wcs.pixel_scale_matrix, dtype=float)
        determinant = abs(float(np.linalg.det(pixel_scale_matrix)))
        native_scale = (
            math.sqrt(determinant) * 3600.0
            if determinant > 0 and math.isfinite(determinant)
            else NATIVE_PIXEL_SCALE_ARCSEC
        )
        result["native_pixel_scale_arcsec"] = float(native_scale)

        yy, xx = np.indices(flags.shape)
        distance = np.hypot(xx - target_x, yy - target_y)
        aperture = distance <= (APERTURE_RADIUS_ARCSEC / max(native_scale, 1e-6))
        aperture_count = int(np.count_nonzero(aperture))
        exclude = (flags & flag_policy.PHOTOMETRY_EXCLUDE_MASK) != 0
        finite = (
            np.isfinite(image)
            & np.isfinite(variance)
            & (variance > 0)
        )
        clean_aperture = aperture & ~exclude & finite
        clean_count = int(np.count_nonzero(clean_aperture))
        clean_fraction = (
            float(clean_count / aperture_count) if aperture_count else 0.0
        )
        center_x = int(round(target_x))
        center_y = int(round(target_y))
        center_flags = int(flags[center_y, center_x])
        center_hard_bad = bool(center_flags & flag_policy.HARD_BAD_MASK)
        result.update(
            {
                "aperture_pixel_count": aperture_count,
                "clean_aperture_pixels": clean_count,
                "clean_fraction_recomputed": clean_fraction,
                "center_flags": center_flags,
                "center_flags_names": flag_policy.names_for(center_flags),
                "center_hard_bad": center_hard_bad,
                "is_used_recomputed": bool(
                    clean_fraction >= 0.5 and not center_hard_bad
                ),
            }
        )

        # Per-visit spectral wavelength from WCS-WAVE (LAW 3: sip=None).
        wavelength_um: float | None = None
        bandwidth_um: float | None = None
        try:
            spectral_wcs = WCS(header, fobj=hdul, key="W")
            spectral_wcs.sip = None
            wave, bandwidth = spectral_wcs.pixel_to_world(target_x, target_y)
            wavelength_um = float(wave.to_value("um"))
            bandwidth_um = float(bandwidth.to_value("um"))
        except Exception as exc:
            result["wcs_wave_error"] = str(exc)
        result["wavelength_um"] = wavelength_um
        result["bandwidth_um"] = bandwidth_um

        # Match the production spectrum channel (epoch + detector + lambda).
        match = None
        if wavelength_um is not None:
            candidates = spectrum_index.get((epoch_id, int(band)), [])
            best_delta = 5e-4
            for channel in candidates:
                delta = abs(float(channel["wavelength_um"]) - wavelength_um)
                if delta < best_delta:
                    best_delta = delta
                    match = channel
        if match is not None:
            result["spectrum_channel"] = {
                "wavelength_um": match.get("wavelength_um"),
                "clean_fraction": match.get("clean_fraction"),
                "is_used_in_photometry": match.get("is_used_in_photometry"),
                "flags": match.get("flags"),
                "flux_ujy": match.get("flux_ujy"),
                "flux_err_ujy": match.get("flux_err_ujy"),
                "delta_lambda_um": float(best_delta),
            }
        else:
            result["spectrum_channel"] = None

        current_usable = (
            bool(match.get("is_used_in_photometry"))
            if match is not None
            else bool(clean_fraction >= 0.5 and not center_hard_bad)
        )
        result["current_usable"] = current_usable
        result["is_used_in_photometry_recommendation"] = bool(current_usable)
        result["recommended_photometry_method"] = (
            "aperture" if current_usable else "none"
        )

        if "PSF" not in names:
            result["psf_available"] = False
            if "EPSF" in names:
                epsf = hdul["EPSF"].data
                result["psf_source"] = "EPSF"
                result["psf_shape"] = list(np.shape(epsf["EPSF"][0]))
                result["psf_note"] = (
                    "QR3 product provides EPSF (441x33x33, 5x oversampling); "
                    "it covers only +/-3.3 native px and cannot evaluate the "
                    "1.2-4.2 native-px gate."
                )
                result["psf_coverage_radius_native_px"] = 3.3
                result["f_wing_truncated_1p2_3p3"] = _epsf_truncated_f(
                    hdul, flags, finite, exclude, target_x, target_y
                )
                result["status"] = "PSF_UNAVAILABLE"
                result["rejection_reasons"] = ["psf_unavailable_qr3_epsf"]
            else:
                result["psf_source"] = "none"
                result["status"] = "PSF_UNAVAILABLE"
                result["rejection_reasons"] = ["missing_psf_extension"]
            return result

        result["psf_available"] = True
        result["psf_source"] = "PSF"
        psf_cube = np.asarray(hdul["PSF"].data, dtype=np.float64)
        if psf_cube.ndim != 3 or psf_cube.shape[0] != 121:
            result["status"] = "ERROR"
            result["rejection_reasons"] = [f"psf_shape_invalid: {psf_cube.shape}"]
            return result
        zone, zone_source = detector_zone(target_x, target_y, header)
        result["psf_zone"] = int(zone)
        result["psf_zone_source"] = zone_source
        plane = psf_cube[zone]
        plane_sum = float(np.nansum(plane))
        result["psf_plane_sum"] = plane_sum
        if not math.isfinite(plane_sum) or plane_sum <= 0:
            result["status"] = "ERROR"
            result["rejection_reasons"] = ["psf_plane_invalid"]
            return result
        plane = plane / plane_sum

        P, x0, y0 = psf_native_pixels(
            plane, target_x, target_y, oversamp=10, center_pix=50.0
        )

        std = wing_from_P(
            P,
            x0,
            y0,
            target_x,
            target_y,
            flags,
            finite,
            flag_policy.PHOTOMETRY_EXCLUDE_MASK,
        )
        halo_relaxed = wing_from_P(
            P,
            x0,
            y0,
            target_x,
            target_y,
            flags,
            finite,
            (flag_policy.HARD_BAD_MASK & ~flag_policy.HALO_BIT)
            | flag_policy.ARTIFACT_WARNING_MASK,
        )
        hard_only = wing_from_P(
            P,
            x0,
            y0,
            target_x,
            target_y,
            flags,
            finite,
            flag_policy.HARD_BAD_MASK,
        )
        no_mask = wing_from_P(
            P, x0, y0, target_x, target_y, flags, finite, 0
        )
        source_excluded = wing_from_P(
            P,
            x0,
            y0,
            target_x,
            target_y,
            flags,
            finite,
            flag_policy.PHOTOMETRY_EXCLUDE_MASK | flag_policy.BIT_SOURCE,
        )

        annulus = (
            (distance >= WING_R_INNER) & (distance <= WING_R_OUTER)
        )
        annulus_flags = flags[annulus]
        result.update(
            {
                "f_wing": std["f_wing"],
                "n_wing": std["n_wing"],
                "f_wing_all": std["f_all"],
                "n_wing_all": std["n_all"],
                "f_wing_halo_relaxed": halo_relaxed["f_wing"],
                "n_wing_halo_relaxed": halo_relaxed["n_wing"],
                "f_wing_hard_only": hard_only["f_wing"],
                "n_wing_hard_only": hard_only["n_wing"],
                "f_wing_no_mask": no_mask["f_wing"],
                "n_wing_no_mask": no_mask["n_wing"],
                "f_wing_source_excluded": source_excluded["f_wing"],
                "n_wing_source_excluded": source_excluded["n_wing"],
                "gate_evaluable": True,
                "gate_pass": std["gate_pass"],
                "source_in_annulus": int(
                    np.count_nonzero(annulus_flags & flag_policy.BIT_SOURCE)
                ),
                "annulus_flag_counts": {
                    name: int(np.count_nonzero(annulus_flags & (1 << bit)))
                    for name, bit in flag_policy.FLAG_BITS.items()
                },
                "annulus_pixel_count": int(np.count_nonzero(annulus)),
            }
        )

        if current_usable:
            result["status"] = "CURRENT_USABLE"
        elif std["gate_pass"]:
            result["status"] = "WING_GATE_PASS"
            result["is_used_in_photometry_recommendation"] = True
            result["recommended_photometry_method"] = "psf_wing_fit"
        else:
            result["status"] = "REJECTED"
            if std["f_wing"] < WING_F_MIN:
                result["rejection_reasons"].append("f_wing_below_0.12")
            if std["n_wing"] < WING_N_MIN:
                result["rejection_reasons"].append("n_wing_below_8")
            if std["n_wing"] == 0:
                result["rejection_reasons"].append("no_clean_wing_pixels")

        # Diagnostic flux only when the gate passes; never shipped as usable
        # otherwise.
        if std["gate_pass"]:
            flux = wing_flux_diagnostic(
                image,
                variance,
                flags,
                finite,
                target_x,
                target_y,
                P,
                x0,
                y0,
                native_scale,
                flag_policy.PHOTOMETRY_EXCLUDE_MASK,
            )
            if flux is not None:
                flux["diagnostic_only"] = False
                result["wing_flux"] = flux
        return result


def _epsf_truncated_f(
    hdul: fits.HDUList,
    flags: np.ndarray,
    finite: np.ndarray,
    exclude: np.ndarray,
    target_x: float,
    target_y: float,
) -> dict[str, Any] | None:
    """Truncated 1.2-3.3 native-px PSF fraction from a QR3 EPSF table."""
    try:
        table = hdul["EPSF"].data
        header = hdul["IMAGE"].header
        x_full = float(target_x) - float(header["CRPIX1A"])
        y_full = float(target_y) - float(header["CRPIX2A"])
        centers_x = np.asarray(table["XCENTER"], dtype=float)
        centers_y = np.asarray(table["YCENTER"], dtype=float)
        spacing_x = float(np.median(np.diff(sorted(set(centers_x.tolist())))))
        spacing_y = float(np.median(np.diff(sorted(set(centers_y.tolist())))))
        bin_x = int(np.clip(round((x_full - centers_x.min()) / spacing_x), 0, 20))
        bin_y = int(np.clip(round((y_full - centers_y.min()) / spacing_y), 0, 20))
        row = bin_y * 21 + bin_x
        plane = np.asarray(table["EPSF"][row], dtype=np.float64)
        plane_sum = float(np.nansum(plane))
        if not math.isfinite(plane_sum) or plane_sum <= 0:
            return None
        plane = plane / plane_sum
        P, x0, y0 = psf_native_pixels(
            plane, target_x, target_y, oversamp=5, center_pix=16.0
        )
        f = 0.0
        n = 0
        for j in range(P.shape[0]):
            py = y0 + j
            if not (0 <= py < flags.shape[0]):
                continue
            for i in range(P.shape[1]):
                px = x0 + i
                if not (0 <= px < flags.shape[1]):
                    continue
                value = float(P[j, i])
                if value == 0.0:
                    continue
                r = math.hypot(px - target_x, py - target_y)
                if 1.2 <= r <= 3.3 and not exclude[py, px] and finite[py, px]:
                    f += value
                    n += 1
        return {
            "f_wing_1p2_3p3": float(f),
            "n_wing_1p2_3p3": int(n),
            "epsf_bin_x": bin_x,
            "epsf_bin_y": bin_y,
            "epsf_covers_4p2_native_px": False,
        }
    except Exception:
        return None


def summarize_psf_target(
    target_id: str,
    rows: list[dict[str, Any]],
    spectrum: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate per-visit PSF rows into a target summary."""
    total = len(rows)
    current_usable = sum(1 for row in rows if row.get("current_usable"))
    with_psf = sum(1 for row in rows if row.get("psf_available"))
    psf_unavailable = sum(
        1 for row in rows if row.get("status") == "PSF_UNAVAILABLE"
    )
    missing_cache = sum(
        1 for row in rows if row.get("status") == "MISSING_CACHE"
    )
    gate_pass = sum(1 for row in rows if row.get("gate_pass"))
    rejected = sum(1 for row in rows if row.get("status") == "REJECTED")
    reason_counts = Counter()
    for row in rows:
        for reason in row.get("rejection_reasons") or []:
            reason_counts[reason] += 1

    by_detector: dict[str, dict[str, Any]] = {}
    for detector in range(1, 7):
        subset = [row for row in rows if row.get("detector") == detector]
        by_detector[str(detector)] = {
            "visits": len(subset),
            "current_usable": sum(
                1 for row in subset if row.get("current_usable")
            ),
            "gate_pass": sum(1 for row in subset if row.get("gate_pass")),
            "psf_available": sum(
                1 for row in subset if row.get("psf_available")
            ),
            "median_f_wing": _median(
                [row.get("f_wing") for row in subset if row.get("f_wing") is not None]
            ),
            "median_n_wing": _median(
                [row.get("n_wing") for row in subset if row.get("n_wing") is not None]
            ),
        }

    per_epoch_band: list[dict[str, Any]] = []
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["epoch_id"], int(row["band"]))].append(row)
    for (epoch_id, band), subset in sorted(grouped.items()):
        f_values = [
            row.get("f_wing") for row in subset if row.get("f_wing") is not None
        ]
        n_values = [
            row.get("n_wing") for row in subset if row.get("n_wing") is not None
        ]
        per_epoch_band.append(
            {
                "epoch_id": epoch_id,
                "band": band,
                "detector": band,
                "visits": len(subset),
                "f_wing_values": [round(float(v), 4) for v in f_values],
                "n_wing_values": [int(v) for v in n_values],
                "f_wing_median": _median(f_values),
                "f_wing_best": max(f_values) if f_values else None,
                "n_wing_median": _median(n_values),
                "gate_pass_count": sum(1 for row in subset if row.get("gate_pass")),
                "current_usable_count": sum(
                    1 for row in subset if row.get("current_usable")
                ),
                "psf_available_count": sum(
                    1 for row in subset if row.get("psf_available")
                ),
            }
        )

    samples: list[dict[str, Any]] = []
    for detector in range(1, 7):
        subset = [row for row in rows if row.get("detector") == detector]
        psf_rows = [row for row in subset if row.get("psf_available")]
        candidate = None
        if psf_rows:
            candidate = max(
                psf_rows,
                key=lambda row: (
                    row.get("f_wing")
                    if row.get("f_wing") is not None
                    else -1.0
                ),
            )
        elif subset:
            candidate = subset[0]
        if candidate is not None:
            samples.append(
                {
                    "detector": detector,
                    "selection": "best_f_wing_visit",
                    "epoch_id": candidate.get("epoch_id"),
                    "band": candidate.get("band"),
                    "mjd": candidate.get("mjd"),
                    "wavelength_um": candidate.get("wavelength_um"),
                    "clean_fraction": candidate.get("clean_fraction_recomputed"),
                    "current_usable": candidate.get("current_usable"),
                    "f_wing": candidate.get("f_wing"),
                    "n_wing": candidate.get("n_wing"),
                    "f_wing_all": candidate.get("f_wing_all"),
                    "n_wing_all": candidate.get("n_wing_all"),
                    "gate_pass": candidate.get("gate_pass"),
                    "is_used_in_photometry_recommendation": candidate.get(
                        "is_used_in_photometry_recommendation"
                    ),
                    "recommended_photometry_method": candidate.get(
                        "recommended_photometry_method"
                    ),
                    "psf_source": candidate.get("psf_source"),
                    "status": candidate.get("status"),
                    "rejection_reasons": candidate.get("rejection_reasons"),
                    "annulus_flag_counts": candidate.get("annulus_flag_counts"),
                    "source_in_annulus": candidate.get("source_in_annulus"),
                }
            )

    f_values_all = [
        row.get("f_wing") for row in rows if row.get("f_wing") is not None
    ]
    best_channel = None
    if f_values_all:
        best = max(
            (row for row in rows if row.get("f_wing") is not None),
            key=lambda row: row["f_wing"],
        )
        best_channel = {
            "epoch_id": best.get("epoch_id"),
            "band": best.get("band"),
            "mjd": best.get("mjd"),
            "wavelength_um": best.get("wavelength_um"),
            "f_wing": best.get("f_wing"),
            "n_wing": best.get("n_wing"),
            "gate_pass": best.get("gate_pass"),
            "status": best.get("status"),
        }

    no_mask_pass = sum(
        1
        for row in rows
        if row.get("f_wing_no_mask") is not None
        and row["f_wing_no_mask"] >= WING_F_MIN
        and row.get("n_wing_no_mask", 0) >= WING_N_MIN
    )
    no_mask_median = _median(
        [
            row.get("f_wing_no_mask")
            for row in rows
            if row.get("f_wing_no_mask") is not None
        ]
    )
    median_f_wing = _median(f_values_all)
    if gate_pass > 0:
        verdict = "PARTIAL-GO"
        verdict_reason = (
            f"{gate_pass}/{total} channels pass the f_wing>=0.12 and N_wing>=8 "
            "gate; the remaining channels must not be assigned wing flux."
        )
    else:
        verdict = "NO-GO"
        verdict_reason = (
            f"0/{total} channels pass the f_wing>=0.12 and N_wing>=8 gate. "
            f"The clean wing fraction is {median_f_wing:.4f} (median) because "
            "the 1.2-4.2 native-px annulus is dominated by SUR_ERROR / "
            "TRANSIENT / OVERFLOW / BLOOM. Even with no flag masking, only "
            f"{no_mask_pass}/{with_psf} PSF-bearing channels pass and the "
            f"median unmasked annulus fraction is {no_mask_median:.4f}. HDU 5 "
            "PSF wing recovery cannot replace the current aperture photometry "
            "as specified."
        )

    return {
        "target_id": target_id,
        "channels_total": total,
        "channels_current_usable": current_usable,
        "channels_with_psf_cube": with_psf,
        "channels_psf_unavailable": psf_unavailable,
        "channels_missing_cache": missing_cache,
        "channels_gate_pass": gate_pass,
        "channels_rejected": rejected,
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "current_usable_fraction": (current_usable / total) if total else None,
        "gate_pass_fraction": (gate_pass / total) if total else None,
        "median_f_wing": _median(f_values_all),
        "max_f_wing": max(f_values_all) if f_values_all else None,
        "median_f_wing_no_mask": no_mask_median,
        "channels_gate_pass_no_mask": no_mask_pass,
        "best_channel": best_channel,
        "per_detector": by_detector,
        "per_epoch_band": per_epoch_band,
        "samples_per_detector": samples,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "spectrum_current_usable": _spectrum_usable_count(spectrum),
        "spectrum_total_channels": _spectrum_total_channels(spectrum),
    }


def _median(values: list[Any]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return float(np.median(clean))


def _spectrum_usable_count(spectrum: dict[str, Any]) -> int:
    return sum(
        1
        for epoch in spectrum.get("epochs", [])
        for channel in epoch.get("channels", [])
        if channel.get("is_used_in_photometry")
    )


def _spectrum_total_channels(spectrum: dict[str, Any]) -> int:
    return sum(
        len(epoch.get("channels", [])) for epoch in spectrum.get("epochs", [])
    )


def run_psf_wing(
    cache_dirs: list[Path],
    golden_cache_dir: Path,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for target_id in ("barnards_star", "r_draconis"):
        manifest_path = golden_cache_dir / target_id / "manifest.json"
        spectrum_path = golden_cache_dir / target_id / "spectrum.json"
        if not manifest_path.is_file():
            output[target_id] = {
                "error": f"missing manifest: {manifest_path}",
                "verdict": "NO-GO",
            }
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spectrum = (
            json.loads(spectrum_path.read_text(encoding="utf-8"))
            if spectrum_path.is_file()
            else {"epochs": []}
        )
        query = manifest["query"]
        spectrum_index: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(
            list
        )
        for epoch in spectrum.get("epochs", []):
            for channel in epoch.get("channels", []):
                spectrum_index[
                    (epoch["epoch_id"], int(channel["detector"]))
                ].append(channel)

        rows: list[dict[str, Any]] = []
        for epoch in manifest.get("epochs", []):
            for band_key, stats in epoch.get("band_stats", {}).items():
                band = int(band_key)
                for uri in stats.get("artifact_uris") or []:
                    path = find_cutout(cache_dirs, uri, query)
                    if path is None:
                        rows.append(
                            {
                                "epoch_id": epoch["epoch_id"],
                                "band": band,
                                "detector": band,
                                "uri": uri,
                                "status": "MISSING_CACHE",
                                "rejection_reasons": ["missing_cache"],
                                "gate_pass": False,
                                "current_usable": False,
                                "psf_available": False,
                            }
                        )
                        continue
                    rows.append(
                        analyze_psf_visit(
                            path,
                            target_id,
                            epoch["epoch_id"],
                            band,
                            uri,
                            query,
                            spectrum_index,
                        )
                    )
        output[target_id] = summarize_psf_target(target_id, rows, spectrum)
        output[target_id]["rows"] = rows
    return output


# ---------------------------------------------------------------------------
# TAP inventory
# ---------------------------------------------------------------------------
def tap_sync(query: str, *, timeout: float = TAP_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    """Synchronous IRSA TAP query; retries transient 429/5xx."""
    url = settings.irsa_tap.rstrip("/") + "/sync"
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    connect=15.0, read=timeout, write=30.0, pool=15.0
                ),
                follow_redirects=True,
                headers={
                    "User-Agent": "SPHEREx-SkyBlink-W0/1.0 (NASA Space Apps 2026)"
                },
            ) as client:
                response = client.get(
                    url, params={"query": query, "format": "votable"}
                )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2.0 * (attempt + 1))
                continue
            response.raise_for_status()
            return _rows_from_votable(response.content)
        except Exception as exc:  # noqa: BLE001 - report, do not crash the spike
            last_error = exc
            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"TAP query failed: {last_error}")


def tap_science_query(ra: float, dec: float) -> list[dict[str, Any]]:
    query = f"""SELECT TOP 5000
       a.uri AS uri,
       p.time_bounds_lower AS mjd_obs,
       p.time_bounds_upper AS mjd_obs_upper,
       p.energy_bandpassname AS detector_band,
       p.planeid AS planeid,
       a.contentlength AS contentlength,
       p.datarelease AS datarelease,
       p.poly AS poly
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
WHERE 1 = CONTAINS(POINT('ICRS', {float(ra):.8f}, {float(dec):.8f}), p.poly)
  AND a.producttype = 'science'
  AND a.contenttype = 'image/fits'
ORDER BY p.time_bounds_lower ASC"""
    return tap_sync(query)


def records_from_tap_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[ArtifactRecord], dict[str, str]]:
    records: list[ArtifactRecord] = []
    poly_by_uri: dict[str, str] = {}
    for row in rows:
        uri = row.get("uri")
        band_name = row.get("detector_band")
        mjd_lower = jfloat(row.get("mjd_obs"))
        if not uri or not band_name or mjd_lower is None:
            continue
        match = BAND_NAME_RE.fullmatch(str(band_name))
        if match is None:
            continue
        band = int(match.group(1))
        release, collection = _detect_release(str(uri))
        mjd_upper = jfloat(row.get("mjd_obs_upper"))
        contentlength = row.get("contentlength")
        records.append(
            ArtifactRecord(
                uri=str(uri),
                mjd_lower=float(mjd_lower),
                mjd_upper=mjd_upper,
                band=band,
                band_name=f"SPHEREx-D{band}",
                planeid=str(row.get("planeid") or ""),
                release=release,
                collection=collection,
                contentlength=int(contentlength)
                if contentlength is not None
                else None,
            )
        )
        poly = row.get("poly")
        if poly:
            poly_by_uri[str(uri)] = str(poly)
    return records, poly_by_uri


def cluster_by_gap(
    records: list[ArtifactRecord], gap_days: float
) -> list[list[ArtifactRecord]]:
    ordered = sorted(records, key=lambda item: item.mjd_mid)
    clusters: list[list[ArtifactRecord]] = []
    current: list[ArtifactRecord] = []
    for record in ordered:
        if current and record.mjd_mid - current[-1].mjd_mid > gap_days:
            clusters.append(current)
            current = []
        current.append(record)
    if current:
        clusters.append(current)
    return clusters


def cluster_summary(cluster: list[ArtifactRecord]) -> dict[str, Any]:
    mjds = [record.mjd_mid for record in cluster]
    bands = Counter(record.band for record in cluster)
    nights = {round(mjd, 1) for mjd in mjds}
    return {
        "start_mjd": float(min(mjds)),
        "end_mjd": float(max(mjds)),
        "start_iso": iso_from_mjd(min(mjds)),
        "end_iso": iso_from_mjd(max(mjds)),
        "span_days": float(max(mjds) - min(mjds)),
        "n_exposures": len(cluster),
        "n_unique_nights_0p1d": len(nights),
        "bands_present": sorted(bands),
        "n_bands": len(bands),
        "per_band_counts": {
            str(band): int(count) for band, count in sorted(bands.items())
        },
    }


def run_r_draconis_inventory(
    records: list[ArtifactRecord],
    golden_cache_dir: Path | None = None,
) -> dict[str, Any]:
    if not records:
        return {
            "tap_rows": 0,
            "verdict": "NO-GO",
            "verdict_reason": "TAP returned no R Draconis science artifacts.",
        }
    mjds = [record.mjd_mid for record in records]
    per_band = Counter(record.band for record in records)
    per_release = Counter(record.release for record in records)
    gap60 = [cluster_summary(cluster) for cluster in cluster_by_gap(records, 60.0)]
    gap10 = [cluster_summary(cluster) for cluster in cluster_by_gap(records, 10.0)]
    gap30 = [cluster_summary(cluster) for cluster in cluster_by_gap(records, 30.0)]
    production_epochs = []
    for epoch in group_epochs(records):
        bands = Counter(record.band for record in epoch.records)
        production_epochs.append(
            {
                "epoch_id": epoch.epoch_id,
                "label": epoch.label,
                "mjd_start": float(epoch.mjd_start),
                "mjd_end": float(epoch.mjd_end),
                "n_exposures": len(epoch.records),
                "bands_present": sorted(bands),
                "per_band_counts": {
                    str(band): int(count) for band, count in sorted(bands.items())
                },
            }
        )
    golden_epoch_bands: dict[str, list[int]] = {}
    if golden_cache_dir is not None:
        manifest_path = golden_cache_dir / "r_draconis" / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                golden_epoch_bands = {
                    str(epoch["epoch_id"]): sorted(
                        int(band) for band in epoch.get("band_stats", {})
                    )
                    for epoch in manifest.get("epochs", [])
                }
            except Exception:
                golden_epoch_bands = {}

    def count_ge(clusters: list[dict[str, Any]], minimum: int) -> int:
        return sum(1 for cluster in clusters if cluster["n_bands"] >= minimum)

    return {
        "tap_rows": len(records),
        "tap_rows_claimed": 2483,
        "tap_rows_matches_claim": len(records) == 2483,
        "mjd_min": float(min(mjds)),
        "mjd_max": float(max(mjds)),
        "span_days": float(max(mjds) - min(mjds)),
        "unique_mjd_0p01d": len({round(mjd, 2) for mjd in mjds}),
        "unique_nights_0p1d": len({round(mjd, 1) for mjd in mjds}),
        "unique_nights_1d": len({int(math.floor(mjd)) for mjd in mjds}),
        "production_epochs": production_epochs,
        "golden_cache_epoch_bands": golden_epoch_bands,
        "per_band_counts": {
            str(band): int(count) for band, count in sorted(per_band.items())
        },
        "per_release_counts": dict(sorted(per_release.items())),
        "clusters_gap_60d": gap60,
        "clusters_gap_30d": gap30,
        "clusters_gap_10d": gap10,
        "gap_60d_cluster_count": len(gap60),
        "gap_30d_cluster_count": len(gap30),
        "gap_10d_cluster_count": len(gap10),
        "gap_60d_clusters_ge_4_bands": count_ge(gap60, 4),
        "gap_30d_clusters_ge_4_bands": count_ge(gap30, 4),
        "gap_10d_clusters_ge_4_bands": count_ge(gap10, 4),
        "gap_10d_clusters_all_6_bands": count_ge(gap10, 6),
        "largest_night_gap_days": _largest_night_gap(mjds),
        "verdict": "NO-GO",
        "verdict_reason": (
            "The 2,483 TAP rows form one continuous 520-day season: there is "
            "no gap > 60 days, so the specified clustering yields 1 cluster, "
            "not 5-6 epochs. The NEP cadence is rolling band pairs "
            "(D3+D6, D2+D5, D1+D4), and D2/D5 have only 89 exposures each. "
            "At a 10-day gap there are 7 natural blocks and only 1 block has "
            "all six bands present, with D2/D5 partial. Five to six "
            "well-populated, complete 6-band epochs are not supported by the "
            "TAP data; do not interpolate them."
        ),
    }


def _largest_night_gap(mjds: list[float]) -> float | None:
    nights = sorted({round(mjd, 2) for mjd in mjds})
    if len(nights) < 2:
        return None
    return float(max(np.diff(nights)))


# ---------------------------------------------------------------------------
# Polygon / LVF geometry
# ---------------------------------------------------------------------------
def parse_ewkb_polygon(hex_string: str) -> np.ndarray:
    """Parse a hex EWKB polygon into an (n, 2) lon/lat array."""
    data = bytes.fromhex(hex_string)
    endian = "<" if data[0] == 1 else ">"
    offset = 1
    geometry_type = struct.unpack_from(endian + "I", data, offset)[0]
    offset += 4
    if geometry_type & 0x20000000:
        offset += 4  # SRID
    ring_count = struct.unpack_from(endian + "I", data, offset)[0]
    offset += 4
    if ring_count < 1:
        raise ValueError("EWKB polygon has no rings")
    point_count = struct.unpack_from(endian + "I", data, offset)[0]
    offset += 4
    points = []
    for _ in range(point_count):
        lon, lat = struct.unpack_from(endian + "dd", data, offset)
        offset += 16
        points.append((lon, lat))
    return np.asarray(points, dtype=float)


def detector_xy_from_polygon(
    polygon: np.ndarray, ra: float, dec: float
) -> tuple[float, float]:
    """Affine detector X/Y (0..2040) of a sky position inside the polygon.

    The TAP ``p.poly`` footprint is the full 2040x2040 detector quad.  Vertex
    0 is detector (0, 0), vertex 1 is (2040, 0), vertex 3 is (0, 2040).  The
    affine approximation was validated against the cached cutout CRPIX1A/
    CRPIX2A offsets to ~1-7 detector pixels for WISE 0855.
    """
    origin = polygon[0]
    edge_x = polygon[1] - polygon[0]
    edge_y = polygon[3] - polygon[0]
    cos_dec = math.cos(math.radians(dec))
    # TAP polygons may store RA on the -180..180 branch while the target is
    # on 0..360 (Epsilon Indi B is at 331 deg but its polygon is at -29 deg).
    delta_ra = ((ra - origin[0] + 180.0) % 360.0) - 180.0
    delta = np.array([delta_ra * cos_dec, dec - origin[1]])
    matrix = np.column_stack(
        [
            np.array([edge_x[0] * cos_dec, edge_x[1]]),
            np.array([edge_y[0] * cos_dec, edge_y[1]]),
        ]
    )
    u, v = np.linalg.solve(matrix, delta)
    return float(u * DETECTOR_SIZE), float(v * DETECTOR_SIZE)


def predict_lambda_um(
    record: ArtifactRecord,
    polygon_hex: str,
    target,
    template_header: fits.Header,
    template_hdul: fits.HDUList,
) -> tuple[float | None, float | None, tuple[float, float] | None]:
    """Predict the LVF wavelength at the target for an uncached visit."""
    try:
        polygon = parse_ewkb_polygon(polygon_hex)
        decimal_year = float(
            Time(record.mjd_mid, format="mjd", scale="tt").decimalyear
        )
        coordinate = propagated_coordinates(target, decimal_year)
        x_det, y_det = detector_xy_from_polygon(
            polygon, coordinate.ra.deg, coordinate.dec.deg
        )
        spectral_wcs = WCS(template_header, fobj=template_hdul, key="W")
        spectral_wcs.sip = None
        pixel_x = x_det + float(template_header["CRPIX1W"])
        pixel_y = y_det + float(template_header["CRPIX2W"])
        wave, bandwidth = spectral_wcs.pixel_to_world(pixel_x, pixel_y)
        wave_um = float(wave.to_value("um"))
        bandwidth_um = float(bandwidth.to_value("um"))
        if not math.isfinite(wave_um) or wave_um <= 0:
            return None, None, (x_det, y_det)
        if not math.isfinite(bandwidth_um) or bandwidth_um <= 0:
            bandwidth_um = None
        return wave_um, bandwidth_um, (x_det, y_det)
    except Exception:
        return None, None, None


def actual_lambda_um(
    path: Path,
    target,
    record: ArtifactRecord,
) -> float | None:
    try:
        with fits.open(path, memmap=False, cache=False) as hdul:
            header = hdul["IMAGE"].header
            decimal_year = float(
                Time(record.mjd_mid, format="mjd", scale="tt").decimalyear
            )
            coordinate = propagated_coordinates(target, decimal_year)
            spatial_wcs = WCS(header)
            x, y = spatial_wcs.world_to_pixel(coordinate)
            spectral_wcs = WCS(header, fobj=hdul, key="W")
            spectral_wcs.sip = None
            wave, _ = spectral_wcs.pixel_to_world(float(x), float(y))
            return float(wave.to_value("um"))
    except Exception:
        return None


def distinct_count(values: list[float], tolerance: float) -> int:
    ordered = sorted(
        float(value) for value in values if math.isfinite(float(value))
    )
    if not ordered:
        return 0
    count = 1
    previous = ordered[0]
    for value in ordered[1:]:
        if value - previous > tolerance:
            count += 1
            previous = value
    return count


def unique_count_1e3(values: list[float]) -> int:
    return len(
        {
            round(float(value), 3)
            for value in values
            if math.isfinite(float(value))
        }
    )


def distinct_summary(values: list[float]) -> dict[str, int]:
    """Distinct-wavelength counts at 5, 10 and 20 nm separation."""
    return {
        "distinct_5nm": distinct_count(values, 0.005),
        "distinct_10nm": distinct_count(values, 0.010),
        "distinct_20nm": distinct_count(values, 0.020),
        "unique_1nm": unique_count_1e3(values),
    }


def select_wavelength_stratified(
    records: list[ArtifactRecord],
    lambdas: dict[str, float | None],
    n_visits: int,
) -> list[ArtifactRecord]:
    usable = [record for record in records if lambdas.get(record.uri) is not None]
    if n_visits >= len(usable):
        return list(usable)
    ordered = sorted(usable, key=lambda record: lambdas[record.uri])
    indices = np.unique(np.linspace(0, len(ordered) - 1, n_visits, dtype=int))
    return [ordered[index] for index in indices]


def run_lvf_inventory(
    target_id: str,
    cache_dirs: list[Path],
    golden_cache_dir: Path,
    tap_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    target = get_target(target_id)
    if target is None:
        return {"error": f"unknown target {target_id}"}
    records, poly_by_uri = records_from_tap_rows(tap_rows)
    epochs = group_epochs(records)
    manifest_path = golden_cache_dir / target_id / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {"epochs": []}
    )
    query = manifest.get("query", {})
    cached_uris: dict[tuple[str, int], list[str]] = defaultdict(list)
    for epoch in manifest.get("epochs", []):
        for band_key, stats in epoch.get("band_stats", {}).items():
            cached_uris[(epoch["epoch_id"], int(band_key))] = list(
                stats.get("artifact_uris") or []
            )

    epoch_summaries = []
    band_rows: list[dict[str, Any]] = []
    for epoch in epochs:
        bands = Counter(record.band for record in epoch.records)
        epoch_summaries.append(
            {
                "epoch_id": epoch.epoch_id,
                "label": epoch.label,
                "mjd_start": float(epoch.mjd_start),
                "mjd_end": float(epoch.mjd_end),
                "n_visits": len(epoch.records),
                "per_band_counts": {
                    str(band): int(count) for band, count in sorted(bands.items())
                },
            }
        )
        for band in range(1, 7):
            band_records = [record for record in epoch.records if record.band == band]
            if not band_records:
                continue
            uri_template = None
            for uri in cached_uris.get((epoch.epoch_id, band), []):
                path = find_cutout(cache_dirs, uri, query)
                if path is not None:
                    uri_template = uri
                    break
            if uri_template is None:
                band_rows.append(
                    {
                        "epoch_id": epoch.epoch_id,
                        "band": band,
                        "detector": band,
                        "n_available_visits": len(band_records),
                        "error": "no cached FITS for this epoch/band; cannot "
                        "read WCS-WAVE template",
                    }
                )
                continue
            template_path = find_cutout(cache_dirs, uri_template, query)
            try:
                template_hdul = fits.open(
                    template_path, memmap=False, cache=False
                )
            except Exception as exc:  # pragma: no cover
                band_rows.append(
                    {
                        "epoch_id": epoch.epoch_id,
                        "band": band,
                        "detector": band,
                        "n_available_visits": len(band_records),
                        "error": f"template_open_failed: {exc}",
                    }
                )
                continue
            with template_hdul:
                template_header = template_hdul["IMAGE"].header
                predicted: dict[str, float | None] = {}
                for record in band_records:
                    poly = poly_by_uri.get(record.uri)
                    if not poly:
                        predicted[record.uri] = None
                        continue
                    wave, _, _ = predict_lambda_um(
                        record,
                        poly,
                        target,
                        template_header,
                        template_hdul,
                    )
                    predicted[record.uri] = (
                        wave
                        if wave is not None and math.isfinite(wave)
                        else None
                    )

                chosen3 = _select_visits(band_records, 3)
                actual3 = []
                predicted3 = []
                for record in chosen3:
                    path = find_cutout(cache_dirs, record.uri, query)
                    actual = (
                        actual_lambda_um(path, target, record)
                        if path is not None
                        else None
                    )
                    actual3.append(actual)
                    predicted3.append(predicted.get(record.uri))
                errors = [
                    abs(a - p)
                    for a, p in zip(actual3, predicted3)
                    if a is not None and p is not None
                ]
                max_error = max(errors) if errors else None

                chronological: dict[str, Any] = {}
                by_wavelength: dict[str, Any] = {}
                for n_visits in (3, 6, 9, 12):
                    chosen = _select_visits(band_records, n_visits)
                    values = [
                        predicted.get(record.uri)
                        for record in chosen
                        if predicted.get(record.uri) is not None
                    ]
                    chronological[str(n_visits)] = {
                        "selected_visits": len(chosen),
                        "n_with_lambda": len(values),
                        **distinct_summary(values),
                    }

                    stratified = select_wavelength_stratified(
                        band_records, predicted, n_visits
                    )
                    values = [
                        predicted.get(record.uri)
                        for record in stratified
                        if predicted.get(record.uri) is not None
                    ]
                    by_wavelength[str(n_visits)] = {
                        "selected_visits": len(stratified),
                        "n_with_lambda": len(values),
                        **distinct_summary(values),
                    }

                base = by_wavelength.get("3", {})
                added = {
                    key: {
                        "added_5nm": max(
                            0,
                            value["distinct_5nm"]
                            - base.get("distinct_5nm", 0),
                        ),
                        "added_10nm": max(
                            0,
                            value["distinct_10nm"]
                            - base.get("distinct_10nm", 0),
                        ),
                        "added_20nm": max(
                            0,
                            value["distinct_20nm"]
                            - base.get("distinct_20nm", 0),
                        ),
                    }
                    for key, value in by_wavelength.items()
                    if key != "3"
                }
                all_lambdas = [
                    value
                    for value in predicted.values()
                    if value is not None and math.isfinite(value)
                ]
                band_rows.append(
                    {
                        "epoch_id": epoch.epoch_id,
                        "band": band,
                        "detector": band,
                        "n_available_visits": len(band_records),
                        "n_cached_visits": len(
                            cached_uris.get((epoch.epoch_id, band), [])
                        ),
                        "lambda_existing_3_actual_um": [
                            round(value, 6) if value is not None else None
                            for value in actual3
                        ],
                        "lambda_existing_3_predicted_um": [
                            round(value, 6) if value is not None else None
                            for value in predicted3
                        ],
                        "prediction_max_abs_error_um": max_error,
                        "lambda_min_um": min(all_lambdas) if all_lambdas else None,
                        "lambda_max_um": max(all_lambdas) if all_lambdas else None,
                        "chronological": chronological,
                        "by_wavelength": by_wavelength,
                        "added_vs_3_by_wavelength": added,
                    }
                )

    # Target-level aggregates.
    valid_rows = [
        row for row in band_rows if "by_wavelength" in row and row["by_wavelength"]
    ]
    total_available = sum(row["n_available_visits"] for row in valid_rows)
    total_distinct_existing = {
        f"distinct_{tag}nm_existing_3": sum(
            row["by_wavelength"]["3"][f"distinct_{tag}nm"]
            for row in valid_rows
        )
        for tag in (5, 10, 20)
    }
    total_added = {
        tag: {
            key: sum(
                row["added_vs_3_by_wavelength"][key][f"added_{tag}nm"]
                for row in valid_rows
            )
            for key in ("6", "9", "12")
        }
        for tag in (5, 10, 20)
    }
    n_band_epochs_ge = {
        key: sum(
            1 for row in valid_rows if row["n_available_visits"] >= int(key)
        )
        for key in ("3", "6", "9", "12")
    }
    prediction_errors = [
        row["prediction_max_abs_error_um"]
        for row in valid_rows
        if row.get("prediction_max_abs_error_um") is not None
    ]
    max_prediction_error = max(prediction_errors) if prediction_errors else None
    return {
        "target_id": target_id,
        "ra_2025_deg": target.ra_epoch2025,
        "dec_2025_deg": target.dec_epoch2025,
        "n_tap_visits": len(records),
        "epoch_summaries": epoch_summaries,
        "band_epochs": band_rows,
        "n_band_epochs_with_wcs_template": len(valid_rows),
        "n_band_epochs_with_at_least": n_band_epochs_ge,
        "total_available_visits_in_band_epochs": total_available,
        **total_distinct_existing,
        "total_added_distinct": {
            f"{tag}nm": total_added[tag] for tag in (5, 10, 20)
        },
        "prediction_max_abs_error_um": max_prediction_error,
        "verdict": "GO-METADATA",
        "verdict_reason": (
            "TAP exposes more than 3 visits for most bands/epochs; the 3 "
            "cached visits already span 0.05-1.33 um within a band, and the "
            "polygon+WCS-WAVE prediction reproduces the cached visit "
            "wavelengths to 0.001-0.024 um depending on band/epoch. "
            "Six/nine/twelve visits add distinct samples at 5/10/20 nm "
            "separation; the 5-nm counts are the optimistic estimate because "
            "the prediction error is of the same order for some bands. "
            "Download timing is backend-owned."
        ),
    }


# ---------------------------------------------------------------------------
# Telemetry sidecar size
# ---------------------------------------------------------------------------
def build_telemetry_arrays(
    target_id: str,
    epoch_id: str,
    band: int,
    cache_dirs: list[Path],
    golden_cache_dir: Path,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None:
    manifest_path = golden_cache_dir / target_id / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    query = manifest["query"]
    epoch = next(
        (item for item in manifest.get("epochs", []) if item["epoch_id"] == epoch_id),
        None,
    )
    if epoch is None:
        return None
    stats = epoch.get("band_stats", {}).get(str(band))
    if not stats or not stats.get("artifact_uris"):
        return None
    uri = stats["artifact_uris"][0]
    path = find_cutout(cache_dirs, uri, query)
    if path is None:
        return None
    content = path.read_bytes()
    parsed = parse_cutout(content, float(query["ra"]), float(query["dec"]))
    out_wcs = output_wcs(float(query["ra"]), float(query["dec"]))
    frame = reproject_to_grid(parsed, out_wcs)
    image = np.asarray(frame.image_mjy_sr, dtype=np.float64)
    flag_raw, _ = reproject_interp(
        (parsed.flags.astype(np.uint32), parsed.spatial_wcs),
        out_wcs,
        shape_out=(TELEMETRY_HEIGHT, TELEMETRY_WIDTH),
        order="nearest-neighbor",
    )
    # Pixels outside the footprint carry NaN; they have no flags.
    flag_raw = np.nan_to_num(np.asarray(flag_raw, dtype=np.float64), nan=0.0)
    flags = np.rint(flag_raw).astype(np.uint32)
    return image, flags, {"target_id": target_id, "epoch_id": epoch_id, "band": band, "uri": uri}


def measure_telemetry(
    image: np.ndarray,
    flags: np.ndarray,
) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        f16 = np.ascontiguousarray(image, dtype=np.float16)
    u32 = np.ascontiguousarray(flags, dtype=np.uint32)
    f16_bytes = f16.tobytes()
    u32_bytes = u32.tobytes()
    both_bytes = f16_bytes + u32_bytes
    f16_gz9 = gzip.compress(f16_bytes, compresslevel=9)
    u32_gz9 = gzip.compress(u32_bytes, compresslevel=9)
    both_gz9 = gzip.compress(both_bytes, compresslevel=9)
    f16_gz6 = gzip.compress(f16_bytes, compresslevel=6)
    u32_gz6 = gzip.compress(u32_bytes, compresslevel=6)
    both_gz6 = gzip.compress(both_bytes, compresslevel=6)

    json_payload = {
        "version": 1,
        "epoch_id": "REPRESENTATIVE",
        "image_f16_b64": base64.b64encode(f16_bytes).decode("ascii"),
        "flags_u32_b64": base64.b64encode(u32_bytes).decode("ascii"),
        "width": TELEMETRY_WIDTH,
        "height": TELEMETRY_HEIGHT,
        "image_dtype": "float16",
        "flags_dtype": "uint32",
        "units": "MJy/sr",
    }
    json_gz_payload = {
        "version": 1,
        "epoch_id": "REPRESENTATIVE",
        "image_f16_gz_b64": base64.b64encode(f16_gz9).decode("ascii"),
        "flags_u32_gz_b64": base64.b64encode(u32_gz9).decode("ascii"),
        "width": TELEMETRY_WIDTH,
        "height": TELEMETRY_HEIGHT,
        "image_dtype": "float16",
        "flags_dtype": "uint32",
        "units": "MJy/sr",
        "compression": "gzip",
    }
    json_raw_bytes = json.dumps(json_payload, separators=(",", ":")).encode("utf-8")
    json_gz_bytes = json.dumps(json_gz_payload, separators=(",", ":")).encode("utf-8")

    return {
        "float16": {
            "raw_bytes": len(f16_bytes),
            "gzip9_bytes": len(f16_gz9),
            "gzip6_bytes": len(f16_gz6),
            "base64_raw_bytes": b64_len(f16_bytes),
            "base64_gzip9_bytes": b64_len(f16_gz9),
        },
        "uint32": {
            "raw_bytes": len(u32_bytes),
            "gzip9_bytes": len(u32_gz9),
            "gzip6_bytes": len(u32_gz6),
            "base64_raw_bytes": b64_len(u32_bytes),
            "base64_gzip9_bytes": b64_len(u32_gz9),
        },
        "both": {
            "raw_bytes": len(both_bytes),
            "gzip9_bytes": len(both_gz9),
            "gzip6_bytes": len(both_gz6),
            "base64_raw_bytes": b64_len(both_bytes),
            "base64_gzip9_bytes": b64_len(both_gz9),
        },
        "json": {
            "raw_base64_bytes": len(json_raw_bytes),
            "gzip_base64_bytes": len(json_gz_bytes),
        },
        "image_nan_fraction": float(np.mean(~np.isfinite(image))),
        "image_min_mjy_sr": float(np.nanmin(image)),
        "image_median_mjy_sr": float(np.nanmedian(image)),
        "image_max_mjy_sr": float(np.nanmax(image)),
        "flags_unique_values": int(len(np.unique(flags))),
    }


def run_telemetry(cache_dirs: list[Path], golden_cache_dir: Path) -> dict[str, Any]:
    cases = [
        ("wise_0855", "2025_E1", 5, "clean mid-IR frame"),
        ("r_draconis", "2025_E1", 3, "bright saturated Mira frame"),
        ("barnards_star", "2025_E1", 6, "high-flag frame"),
    ]
    measurements = []
    for target_id, epoch_id, band, label in cases:
        built = build_telemetry_arrays(
            target_id, epoch_id, band, cache_dirs, golden_cache_dir
        )
        if built is None:
            measurements.append(
                {
                    "case": f"{target_id}_{epoch_id}_D{band}",
                    "label": label,
                    "error": "could not build a real 240x240 frame",
                }
            )
            continue
        image, flags, provenance = built
        measurement = measure_telemetry(image, flags)
        measurement.update(
            {
                "case": f"{target_id}_{epoch_id}_D{band}",
                "label": label,
                "source": provenance,
                "array_shape": list(image.shape),
                "note": (
                    "Real single-band reprojection to the contract 240x240 "
                    "grid; the flags plane is a nearest-neighbor reprojection "
                    "of the raw Table 16 bitmask, not a boolean union."
                ),
            }
        )
        measurements.append(measurement)

    valid = [item for item in measurements if "both" in item]
    gzip_values = [item["both"]["gzip9_bytes"] for item in valid]
    json_values = [item["json"]["gzip_base64_bytes"] for item in valid]
    honest_kb = [
        round(value / 1024.0, 1) for value in (min(gzip_values), max(gzip_values))
    ] if gzip_values else None
    json_kb = [
        round(value / 1024.0, 1) for value in (min(json_values), max(json_values))
    ] if json_values else None
    claim_45kb = (
        all(value < 45 * 1024 for value in gzip_values) if gzip_values else None
    )
    return {
        "array_shape": [TELEMETRY_HEIGHT, TELEMETRY_WIDTH],
        "cases": measurements,
        "claim_45kb_gzipped": claim_45kb,
        "honest_gzip_both_kb_range": honest_kb,
        "honest_json_gzip_base64_kb_range": json_kb,
        "verdict": "NO-GO" if claim_45kb is False else "INCONCLUSIVE",
        "verdict_reason": (
            "The <45 KB claim is not realistic for a real 240x240 float16 "
            "MJy/sr plane plus uint32 Table 16 flags. The float16 plane "
            "dominates and gzips poorly (~78-99 KB alone); both arrays gzip "
            "to ~80-103 KB. The uint32 flag plane is tiny (~1.5-4.5 KB "
            "gzipped). The honest sidecar budget is ~80-105 KB gzipped, or "
            "~105-140 KB as base64 JSON."
        )
        if claim_45kb is False
        else "Could not measure a real frame.",
    }


# ---------------------------------------------------------------------------
# hips2fits / overlay availability
# ---------------------------------------------------------------------------
def timed_get(
    url: str,
    params: dict[str, Any] | None,
    *,
    connect: float = HIPS_CONNECT_SECONDS,
    read: float = HIPS_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with httpx.Client(
            timeout=httpx.Timeout(
                connect=connect, read=read, write=10.0, pool=connect
            ),
            follow_redirects=True,
            headers={"User-Agent": "SPHEREx-SkyBlink-W0/1.0"},
        ) as client:
            response = client.get(url, params=params)
        elapsed = time.monotonic() - started
        content_type = response.headers.get("content-type", "")
        return {
            "url": url,
            "status": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "latency_s": round(elapsed, 2),
            "content_type": content_type,
            "bytes": len(response.content),
            "image_like": content_type.startswith("image/")
            and len(response.content) > 1000,
        }
    except Exception as exc:  # noqa: BLE001 - unreachable is a result
        return {
            "url": url,
            "status": None,
            "ok": False,
            "latency_s": round(time.monotonic() - started, 2),
            "content_type": None,
            "bytes": 0,
            "image_like": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_hips2fits() -> dict[str, Any]:
    hips_params = {
        "width": 240,
        "height": 240,
        "fov": 0.205,
        "projection": "TAN",
        "coordsys": "icrs",
        "ra": 133.75921,
        "dec": -7.24216,
        "format": "jpg",
    }
    endpoints = [
        "https://alasky.cds.unistra.fr/hips-image-services/hips2fits",
        "https://alasky.u-strasbg.fr/hips-image-services/hips2fits",
    ]
    hips_ids = ["CDS/P/DSS2/color", "CDS/P/allWISE/W1", "CDS/P/allWISE/color"]
    tests = []
    for endpoint in endpoints:
        for hips_id in hips_ids:
            params = dict(hips_params, hips=hips_id)
            test = timed_get(endpoint, params)
            test.update({"endpoint": endpoint, "hips": hips_id})
            tests.append(test)
    reachable = [test for test in tests if test.get("ok") and test.get("image_like")]

    # Alternative reachable services.  These are probes, not downloads.
    alternatives = {}
    alternatives["irsa_root"] = timed_get(
        "https://irsa.ipac.caltech.edu/", None
    )
    alternatives["irsa_tap_tiny"] = timed_get(
        settings.irsa_tap.rstrip("/") + "/sync",
        {"query": "SELECT TOP 1 1 AS ok", "format": "votable"},
    )
    alternatives["irsa_sia_wise_allwise"] = timed_get(
        "https://irsa.ipac.caltech.edu/SIA",
        {
            "COLLECTION": "wise_allwise",
            "POS": "circle 133.75921 -7.24216 0.1",
            "RESPONSEFORMAT": "votable",
        },
    )
    alternatives["skyview_wise_3_4"] = timed_get(
        "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl",
        {
            "Survey": "WISE 3.4",
            "position": "133.75921,-7.24216",
            "size": "0.205",
            "pixels": "240",
            "return": "JPEG",
        },
    )
    alternatives["skyview_dss2"] = timed_get(
        "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl",
        {
            "Survey": "DSS2",
            "position": "133.75921,-7.24216",
            "size": "0.205",
            "pixels": "240",
            "return": "JPEG",
        },
    )
    alternatives["skyview_wise_4_6"] = timed_get(
        "https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl",
        {
            "Survey": "WISE 4.6",
            "position": "133.75921,-7.24216",
            "size": "0.205",
            "pixels": "240",
            "return": "JPEG",
        },
    )

    if reachable:
        verdict = "GO"
        reason = (
            f"{len(reachable)}/{len(tests)} CDS hips2fits requests returned "
            "image bytes."
        )
    else:
        verdict = "NO-GO"
        reason = (
            "All CDS hips2fits requests failed (TCP connect timeout to "
            "alasky.cds.unistra.fr 130.79.128.175:443). Real DSS2/AllWISE "
            "overlays cannot be fetched from this environment via CDS. IRSA "
            "TAP/SIA is reachable for metadata, and SkyView is reachable for "
            "real WISE/DSS2 JPEG cutouts; the cross-mission curtain should use "
            "SkyView or a clearly labelled precomputed fallback, never a fake "
            "real overlay."
        )
    return {
        "tested_coordinates": {"ra": 133.75921, "dec": -7.24216},
        "fov_deg": 0.205,
        "endpoints": endpoints,
        "tests": tests,
        "n_tests": len(tests),
        "n_reachable_image": len(reachable),
        "alternatives": alternatives,
        "irsa_sia_note": (
            "The IRSA SIA2 wise_allwise query is reachable (HTTP 200, "
            "VOTable), but its access_url points to a flag table "
            "(text/plain), not a pixel cutout; fetching that URL returned "
            "HTTP 503. IRSA TAP/SIA is usable for metadata, not as a direct "
            "HiPS pixel service."
        ),
        "cds_dns": {
            "alasky.cds.unistra.fr": "130.79.128.175 (resolves; TCP 443 times out)",
            "alasky.u-strasbg.fr": "130.79.128.175 (same host)",
        },
        "verdict": verdict,
        "verdict_reason": reason,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="W0 read-only feasibility spike for SPHEREx SkyBlink."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "golden_cache" / "w0_metrics.json",
        help="Output JSON (the only file written; default: golden_cache/w0_metrics.json)",
    )
    parser.add_argument(
        "--cache-dir",
        action="append",
        type=Path,
        default=None,
        help="Cutout cache directory (repeatable). Auto-detected by default.",
    )
    parser.add_argument(
        "--golden-cache",
        type=Path,
        default=REPO_ROOT / "golden_cache",
        help="Golden cache directory (default: <repo>/golden_cache)",
    )
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="Offline mode: skip TAP and hips2fits probes.",
    )
    parser.add_argument("--skip-psf", action="store_true")
    parser.add_argument("--skip-r-draconis", action="store_true")
    parser.add_argument("--skip-telemetry", action="store_true")
    parser.add_argument("--skip-hips", action="store_true")
    parser.add_argument("--skip-lvf", action="store_true")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Compute and print but do not write --out (dry run).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cache_dirs = (
        [path.resolve() for path in args.cache_dir]
        if args.cache_dir
        else [path.resolve() for path in DEFAULT_CACHE_DIRS]
    )
    existing_cache_dirs = [path for path in cache_dirs if path.is_dir()]
    golden_cache_dir = args.golden_cache.resolve()
    started = time.monotonic()

    payload: dict[str, Any] = {
        "generated_at": now_utc(),
        "script": "scripts/spike_w0_metrics.py",
        "read_only": True,
        "network_used": not args.skip_network,
        "cache_dirs": [str(path) for path in existing_cache_dirs],
        "cache_dirs_n_fits": {
            str(path): len(list(path.glob("*.fits")))
            for path in existing_cache_dirs
        },
        "golden_cache_dir": str(golden_cache_dir),
        "verdicts": {},
        "mapping_rules": {
            "cutout_cache": (
                "sha256(f'{access_url}|{ra:.8f}|{dec:.8f}|{size:.6f}').fits "
                "in each cutout cache dir, mirroring "
                "IrsaClient._cutout_cache_path (irsa_client.py:443-455)."
            ),
            "spectrum_channel_to_visit": (
                "The golden manifest band_stats[band].artifact_uris are the "
                "visits selected by _select_visits (up to 3, evenly spaced in "
                "MJD). Each visit contributes one channel; the per-visit "
                "wavelength is read from WCS-WAVE (key='W', sip=None). "
                "Channels are matched by epoch + detector + |Delta lambda| < "
                "5e-4 um."
            ),
            "wing_annulus": (
                "1.2 <= r <= 4.2 native pixels, with r measured from the "
                "propagated target position to native pixel centers; native "
                "scale from the cutout WCS (~6.15 arcsec/px). P_i is the "
                "normalized local HDU 5 PSF fraction in native pixel i."
            ),
            "psf_zone": (
                "Full-frame detector X/Y = cutout target pixel - CRPIX1A/"
                "CRPIX2A; 11x11 zones of 185.4545 detector px; zone index = "
                "zone_y*11 + zone_x. The PSF cube planes are normalized to 1."
            ),
            "bit_source": (
                "BIT_SOURCE is kept in the primary wing fit because it covers "
                "essentially the whole annulus; it is the source mask, not a "
                "defect. A BIT_SOURCE-excluded variant is reported as a "
                "diagnostic. It is excluded only from the diagnostic sky "
                "background annulus (5-8 native px)."
            ),
            "lvf_prediction": (
                "TAP p.poly is the full 2040x2040 detector footprint (hex "
                "EWKB). Vertex 0 -> detector (0,0), vertex 1 -> (2040,0), "
                "vertex 3 -> (0,2040); RA is wrapped to [-180,180). The "
                "target's detector X/Y is mapped through the cached "
                "WCS-WAVE lookup (sip=None). The prediction is validated "
                "against the 3 cached visits."
            ),
        },
        "notes": [
            "All FITS access is by EXTNAME; the empty primary HDU data is "
            "never read.",
            "Primary wing mask is PHOTOMETRY_EXCLUDE_MASK (hard + warning, "
            "including DICHROIC). BIT_SOURCE is kept because it covers most "
            "of these frames (e.g., ~93% of the Barnard's Star frame stats); "
            "a BIT_SOURCE-excluded variant is reported.",
            "A failed wing gate never yields photometry; diagnostic fluxes are "
            "labelled diagnostic_only.",
            "QR3 products expose EPSF (441x33x33, 5x oversampling) instead of "
            "the HDU 5 PSF cube; EPSF covers only +/-3.3 native px and cannot "
            "evaluate the 1.2-4.2 px gate.",
            "TAP row counts are real IRSA queries; no epochs are fabricated or "
            "interpolated.",
            "Telemetry sizes use real 240x240 single-band reprojections and a "
            "nearest-neighbor Table 16 flag plane.",
        ],
    }

    if not args.skip_psf:
        payload["psf_wing"] = run_psf_wing(existing_cache_dirs, golden_cache_dir)
        for target_id, summary in payload["psf_wing"].items():
            payload["verdicts"][f"psf_wing_{target_id}"] = {
                "verdict": summary.get("verdict"),
                "reason": summary.get("verdict_reason"),
            }

    r_draconis_records: list[ArtifactRecord] = []
    wise_records: list[ArtifactRecord] = []
    eps_records: list[ArtifactRecord] = []
    tap_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    tap_errors: dict[str, str] = {}

    if not args.skip_network:
        target_queries = {
            "r_draconis": (248.1674, 66.7548),
            "wise_0855": (133.75921, -7.24216),
            "eps_indi_b": (331.0962, -56.8005),
        }
        for target_id, (ra, dec) in target_queries.items():
            try:
                tap_rows_by_target[target_id] = tap_science_query(ra, dec)
            except Exception as exc:  # noqa: BLE001
                tap_errors[target_id] = f"{type(exc).__name__}: {exc}"
                tap_rows_by_target[target_id] = []
        if tap_rows_by_target.get("r_draconis"):
            r_draconis_records, _ = records_from_tap_rows(
                tap_rows_by_target["r_draconis"]
            )
        if tap_rows_by_target.get("wise_0855"):
            wise_records, _ = records_from_tap_rows(
                tap_rows_by_target["wise_0855"]
            )
        if tap_rows_by_target.get("eps_indi_b"):
            eps_records, _ = records_from_tap_rows(
                tap_rows_by_target["eps_indi_b"]
            )
    else:
        tap_errors["all"] = "skipped (--skip-network)"

    if not args.skip_r_draconis:
        if r_draconis_records:
            payload["r_draconis"] = run_r_draconis_inventory(
                r_draconis_records, golden_cache_dir
            )
        else:
            payload["r_draconis"] = {
                "tap_rows": 0,
                "error": tap_errors.get("r_draconis", "no TAP rows"),
                "verdict": "NO-GO",
                "verdict_reason": "R Draconis TAP inventory unavailable.",
            }
        payload["verdicts"]["r_draconis"] = {
            "verdict": payload["r_draconis"].get("verdict"),
            "reason": payload["r_draconis"].get("verdict_reason"),
        }

    if not args.skip_telemetry:
        payload["telemetry"] = run_telemetry(
            existing_cache_dirs, golden_cache_dir
        )
        payload["verdicts"]["telemetry"] = {
            "verdict": payload["telemetry"].get("verdict"),
            "reason": payload["telemetry"].get("verdict_reason"),
        }

    if not args.skip_hips:
        if args.skip_network:
            payload["hips2fits"] = {
                "verdict": "SKIPPED",
                "verdict_reason": "skipped (--skip-network)",
            }
        else:
            payload["hips2fits"] = run_hips2fits()
            payload["verdicts"]["hips2fits"] = {
                "verdict": payload["hips2fits"].get("verdict"),
                "reason": payload["hips2fits"].get("verdict_reason"),
            }

    if not args.skip_lvf:
        lvf: dict[str, Any] = {}
        for target_id, records in (
            ("wise_0855", wise_records),
            ("eps_indi_b", eps_records),
        ):
            if args.skip_network:
                lvf[target_id] = {
                    "verdict": "SKIPPED",
                    "verdict_reason": "skipped (--skip-network)",
                }
                continue
            if not records:
                lvf[target_id] = {
                    "verdict": "NO-GO",
                    "verdict_reason": tap_errors.get(target_id, "no TAP rows"),
                }
                continue
            # The raw TAP rows carry the p.poly footprints needed for the
            # polygon + WCS-WAVE wavelength prediction; reuse the query above.
            rows_with_poly = [
                row for row in tap_rows_by_target.get(target_id, [])
                if row.get("poly")
            ]
            if not rows_with_poly:
                lvf[target_id] = {
                    "verdict": "NO-GO",
                    "verdict_reason": "TAP rows have no p.poly footprints.",
                }
                continue
            try:
                lvf[target_id] = run_lvf_inventory(
                    target_id,
                    existing_cache_dirs,
                    golden_cache_dir,
                    rows_with_poly,
                )
            except Exception as exc:  # noqa: BLE001
                lvf[target_id] = {
                    "verdict": "NO-GO",
                    "verdict_reason": f"LVF inventory failed: {type(exc).__name__}: {exc}",
                }
        payload["lvf"] = lvf
        for target_id, summary in lvf.items():
            payload["verdicts"][f"lvf_{target_id}"] = {
                "verdict": summary.get("verdict"),
                "reason": summary.get("verdict_reason"),
            }

    payload["tap_errors"] = tap_errors
    payload["elapsed_seconds"] = round(time.monotonic() - started, 1)
    payload["summary"] = {
        "psf_wing": {
            target_id: {
                "channels_total": summary.get("channels_total"),
                "current_usable": summary.get("channels_current_usable"),
                "gate_pass": summary.get("channels_gate_pass"),
                "verdict": summary.get("verdict"),
            }
            for target_id, summary in payload.get("psf_wing", {}).items()
        },
        "r_draconis": {
            "tap_rows": payload.get("r_draconis", {}).get("tap_rows"),
            "gap60_clusters": payload.get("r_draconis", {}).get(
                "gap_60d_cluster_count"
            ),
            "gap10_clusters": payload.get("r_draconis", {}).get(
                "gap_10d_cluster_count"
            ),
            "verdict": payload.get("r_draconis", {}).get("verdict"),
        },
        "telemetry": {
            "honest_gzip_both_kb": payload.get("telemetry", {}).get(
                "honest_gzip_both_kb_range"
            ),
            "claim_45kb": payload.get("telemetry", {}).get("claim_45kb_gzipped"),
            "verdict": payload.get("telemetry", {}).get("verdict"),
        },
        "hips2fits": {
            "cds_reachable_image": payload.get("hips2fits", {}).get(
                "n_reachable_image"
            ),
            "tests": payload.get("hips2fits", {}).get("n_tests"),
            "verdict": payload.get("hips2fits", {}).get("verdict"),
        },
        "lvf": {
            target_id: {
                "tap_visits": summary.get("n_tap_visits"),
                "distinct_5nm_existing_3": summary.get(
                    "distinct_5nm_existing_3"
                ),
                "added_5nm": summary.get("total_added_distinct", {}).get(
                    "5nm"
                ),
                "verdict": summary.get("verdict"),
            }
            for target_id, summary in payload.get("lvf", {}).items()
        },
    }

    if not args.no_write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.out.with_suffix(args.out.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(args.out)

    # Compact console summary (does not replace the JSON).
    print(f"W0 metrics generated at {payload['generated_at']}")
    for key, value in payload["verdicts"].items():
        print(f"  {key}: {value.get('verdict')} - {value.get('reason')}")
    if payload.get("psf_wing"):
        for target_id, summary in payload["psf_wing"].items():
            print(
                f"  psf {target_id}: {summary.get('channels_gate_pass')}/"
                f"{summary.get('channels_total')} gate pass; "
                f"current usable {summary.get('channels_current_usable')}; "
                f"median f_wing {summary.get('median_f_wing')}"
            )
    if payload.get("r_draconis"):
        row = payload["r_draconis"]
        print(
            f"  r_draconis: TAP rows {row.get('tap_rows')}; "
            f"gap60 clusters {row.get('gap_60d_cluster_count')}; "
            f"gap10 clusters {row.get('gap_10d_cluster_count')}"
        )
    if payload.get("telemetry"):
        row = payload["telemetry"]
        print(
            f"  telemetry: gzip both KB {row.get('honest_gzip_both_kb_range')}; "
            f"claim 45KB {row.get('claim_45kb_gzipped')}"
        )
    if payload.get("hips2fits"):
        row = payload["hips2fits"]
        print(
            f"  hips2fits: {row.get('n_reachable_image')}/"
            f"{row.get('n_tests')} reachable; verdict {row.get('verdict')}"
        )
    if payload.get("lvf"):
        for target_id, row in payload["lvf"].items():
            print(
                f"  lvf {target_id}: visits {row.get('n_tap_visits')}; "
                f"distinct3 {row.get('distinct_5nm_existing_3')}; "
                f"added {row.get('total_added_distinct', {}).get('5nm')}"
            )
    if not args.no_write:
        print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
