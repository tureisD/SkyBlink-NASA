"""SPHEREx Level 2 pipeline: six-band coadds, normalization, differences (B2).

Pipeline summary
----------------
1. Query IRSA TAP for all science artifacts at the target/query position.
2. Group them into 6-month survey epochs (``{year}_E{index}`` on the full set).
3. Select a small, evenly spaced set of visits per band/epoch and download the
   cutouts in parallel.
4. Parse every cutout by ``EXTNAME`` (``IMAGE``, ``FLAGS``, ``VARIANCE``,
   ``ZODI``), subtract ``ZODI``, estimate a source-masked local background, and
   set only ``HARD_BAD_MASK`` pixels to ``NaN``.  ``BIT_SOURCE`` is preserved.
5. Reproject each visit onto the contract 240 x 240 north-up TAN grid
   (3.075 arcsec/pixel), then coadd the visits of each band with inverse
   variance weights: ``I = sum(w I) / sum(w)``, ``var = 1 / sum(w)``.
6. Compute the LAW 8 cross-epoch normalization from static ``BIT_SOURCE``
   pixels (p99.5), using the O1 reference/fallback/clamp algorithm.
7. Apply the per-band scales to the frames and ``scale**2`` to the variance.
8. Build the per-epoch band, ``all``, ``thermal`` and ``flag_overlay`` WebP
   frames, and the adjacent-epoch difference frames from the un-normalized
   frames.

All frames are real data.  Missing bands/epochs are omitted, never fabricated.
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.visualization import AsinhStretch, ZScaleInterval
from astropy.wcs import WCS
from PIL import Image
from reproject import reproject_interp

from core import flags as flag_policy
from core.cachekeys import is_valid_filename
from core.config import settings
from services import lvf as lvf_geometry
from services import telemetry as telemetry_codec
from services.halo import resolve_halo_decision
from services.background import estimate_background
from services.live_selection import select_pair, compact_selection, field_pixel_mask, ranked_candidate_pairs
from services.singleflight import run_once
from services.build_limits import live_build_slot
from services.product_metadata import observation_range, observation_label
from services.recording import record_images
from services.irsa_client import (
    DEFAULT_SIA_COLLECTIONS,
    ArtifactRecord,
    IRSANoData,
    IRSAUnavailable,
    IrsaClient,
)

logger = logging.getLogger(__name__)

GRID_WIDTH = 240
GRID_HEIGHT = 240
PIXEL_SCALE_ARCSEC = 3.075
NATIVE_PIXEL_SCALE_ARCSEC = 6.15
CDELT_DEG = 0.0008541667
CRPIX = (GRID_WIDTH + 1) / 2.0  # 120.5
CENTER_PIXEL = CRPIX - 1.0  # 119.5 in 0-based pixel coordinates
APERTURE_RADIUS_ARCSEC = 12.3
PSF_WINGS_FACTOR = 5.0
WINGS_RADIUS_ARCSEC = APERTURE_RADIUS_ARCSEC * PSF_WINGS_FACTOR  # 61.5"
WINGS_RADIUS_PIXELS = WINGS_RADIUS_ARCSEC / PIXEL_SCALE_ARCSEC  # 20.0 output px
CACHE_VERSION = 13

WEBP_QUALITY = 100
ASINH_A = 0.1

_SEVERITY = {
    "ok": 0,
    "fallback_all_pixels": 1,
    "clamped": 2,
    "insufficient_static_pixels": 3,
}

_ALERT_STATUS = "ALERT"


class PipelineError(RuntimeError):
    """Raised when a cutout cannot be parsed or reprojected."""


class NoUsablePixelsError(PipelineError):
    """The cutout contains no finite science pixels after masking."""


@dataclass(frozen=True)
class ParsedCutout:
    image_mjy_sr: np.ndarray
    variance_mjy_sr2: np.ndarray
    flags: np.ndarray
    warning_mask: np.ndarray
    source_mask: np.ndarray
    hard_bad_mask: np.ndarray
    spatial_wcs: WCS
    spectral_wavelength_um: float | None
    spectral_bandwidth_um: float | None
    local_background_mjy_sr: float
    variance_floor_mjy_sr2: float
    native_pixel_scale_arcsec: float
    target_x: float
    target_y: float
    native_shape: tuple[int, int]
    native_finite_count: int
    aperture_pixel_count: int
    aperture_warning_names: tuple[str, ...]
    aperture_source_bit: bool
    halo_pixel_count: int
    halo_aperture_pixel_count: int
    # Optional for backward compatibility with callers/tests that build a
    # ParsedCutout without the B4 display masks.  The live pipeline populates
    # both; when absent, reproject_to_grid derives them from hard_bad_mask and
    # the HALO flag.
    display_bad_mask: np.ndarray | None = None
    halo_mask: np.ndarray | None = None
    # B8 LVF geometry at the target position (contract 1.1.0).  ``None`` when
    # the target is off-detector or the WCS-WAVE lookup failed.
    lvf_pa_deg: float | None = None
    lvf_grad_um_per_arcsec: float | None = None
    background_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReprojectedFrame:
    image_mjy_sr: np.ndarray
    variance_mjy_sr2: np.ndarray
    warning_mask: np.ndarray
    source_mask: np.ndarray
    hard_bad_mask: np.ndarray
    display_bad_mask: np.ndarray
    halo_mask: np.ndarray
    footprint: np.ndarray
    # B8: nearest-neighbour Table 16 flag plane on the output grid.  This is
    # the raw bitmask (BIT_SOURCE preserved), not a boolean mask.
    flags: np.ndarray | None = None
    measurement_image_mjy_sr: np.ndarray | None = None
    measurement_variance_mjy_sr2: np.ndarray | None = None


@dataclass(frozen=True)
class EpochBucket:
    epoch_id: str
    index: int
    year: int
    semester: int
    label: str
    records: tuple[ArtifactRecord, ...]
    mjd_start: float
    mjd_end: float

    @property
    def mjd_mean(self) -> float:
        if not self.records:
            return self.mjd_start
        return float(np.mean([record.mjd_mid for record in self.records]))


@dataclass
class BandCoadd:
    band: int
    image_mjy_sr: np.ndarray
    variance_mjy_sr2: np.ndarray
    warning_mask: np.ndarray
    source_mask: np.ndarray
    hard_bad_mask: np.ndarray
    halo_mask: np.ndarray
    footprint: np.ndarray
    # B8: raw Table 16 flag plane on the output grid (bitwise OR of visits).
    flags: np.ndarray
    requested_visits: int
    used_visits: int
    artifact_uris: tuple[str, ...]
    mjd_values: tuple[float, ...]
    wavelengths_um: tuple[float, ...]
    bandwidths_um: tuple[float, ...]
    native_pixel_scale_arcsec: float
    aperture_warning_names: frozenset[str]
    aperture_source_bit: bool
    halo_pixel_count: int
    halo_aperture_pixel_count: int
    aperture_pixel_count: int
    native_finite_count: int
    stats: dict[str, Any] = field(default_factory=dict)
    # B8: per-visit LVF geometry at the target position (detector is ``band``).
    lvf_pa_deg_values: tuple[float, ...] = ()
    lvf_grad_values: tuple[float, ...] = ()
    normalized_image_mjy_sr: np.ndarray | None = None
    normalized_variance_mjy_sr2: np.ndarray | None = None
    scale: float = 1.0
    display_image_mjy_sr: np.ndarray | None = None
    background_metadata: tuple[dict, ...] = ()


# ---------------------------------------------------------------------------
# Small numeric / serialization helpers
# ---------------------------------------------------------------------------
def _json_float(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _valid_number(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > 0.0


def _percentile(values: np.ndarray, q: float = 99.5) -> float | None:
    if values.size == 0:
        return None
    value = float(np.percentile(values, q))
    return value if math.isfinite(value) else None


def _mjd_to_date(mjd: float) -> date:
    return Time(float(mjd), format="mjd", scale="utc").to_datetime().date()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _check_deadline(started: float, deadline_seconds: float | None) -> None:
    if deadline_seconds is None:
        return
    if (time.monotonic() - started) > float(deadline_seconds):
        raise IRSAUnavailable(
            "Live archive processing exceeded the server time budget. Retry the request."
        )


# ---------------------------------------------------------------------------
# WCS helpers
# ---------------------------------------------------------------------------
def output_wcs(ra: float, dec: float) -> WCS:
    """Build the contract 240 x 240 north-up TAN grid centered on (ra, dec)."""
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.cunit = ["deg", "deg"]
    wcs.wcs.crval = [float(ra), float(dec)]
    wcs.wcs.crpix = [CRPIX, CRPIX]
    wcs.wcs.cdelt = [-CDELT_DEG, CDELT_DEG]
    wcs.wcs.set()
    return wcs


def _native_pixel_scale_arcsec(wcs: WCS) -> float:
    matrix = np.asarray(wcs.pixel_scale_matrix, dtype=float)
    determinant = abs(float(np.linalg.det(matrix)))
    if determinant <= 0 or not math.isfinite(determinant):
        return NATIVE_PIXEL_SCALE_ARCSEC
    return math.sqrt(determinant) * 3600.0


def _normalization_region() -> np.ndarray:
    """Frame pixels outside the target aperture and its PSF wings."""
    yy, xx = np.indices((GRID_HEIGHT, GRID_WIDTH))
    radius = np.hypot(xx - CENTER_PIXEL, yy - CENTER_PIXEL)
    return radius > WINGS_RADIUS_PIXELS


# ---------------------------------------------------------------------------
# Cutout parsing
# ---------------------------------------------------------------------------
def _native_aperture_stats(
    flags: np.ndarray,
    target_x: float,
    target_y: float,
    native_pixel_scale_arcsec: float,
) -> dict[str, Any]:
    """Target-aperture warning/source/HALO measurements on the native grid."""
    radius_pixels = APERTURE_RADIUS_ARCSEC / max(native_pixel_scale_arcsec, 1e-6)
    yy, xx = np.indices(flags.shape)
    aperture = np.hypot(xx - target_x, yy - target_y) <= radius_pixels
    count = int(np.count_nonzero(aperture))
    if count:
        aperture_flags = flags[aperture]
        warning_union = int(
            np.bitwise_or.reduce(
                aperture_flags & flag_policy.ARTIFACT_WARNING_MASK
            )
        )
        warning_names = sorted(flag_policy.names_for(warning_union))
        source_bit = bool(np.any(aperture_flags & flag_policy.BIT_SOURCE))
        halo_aperture = int(np.count_nonzero(aperture_flags & flag_policy.HALO_BIT))
    else:
        warning_names = []
        source_bit = False
        halo_aperture = 0
    return {
        "aperture_pixel_count": count,
        "aperture_warning_names": tuple(warning_names),
        "aperture_source_bit": source_bit,
        "halo_aperture_pixel_count": halo_aperture,
    }


def parse_cutout(
    content: bytes,
    target_ra: float,
    target_dec: float,
    *,
    display_bad_mask: int = flag_policy.HARD_BAD_MASK,
) -> ParsedCutout:
    """Parse one FITS cutout by ``EXTNAME`` and apply the science preparation.

    ``display_bad_mask`` controls which hard bits become ``NaN`` in the
    displayed image.  It defaults to the full hard mask; when the HALO
    display-only gate is active, callers pass
    :data:`core.flags.HALO_DISPLAY_BAD_MASK` so HALO pixels are shown.  The
    photometry hard mask in ``hard_bad_mask`` always retains HALO.
    """
    with fits.open(io.BytesIO(content), cache=False, memmap=False) as hdul:
        names = {str(hdu.name).upper() for hdu in hdul}
        required = {"IMAGE", "FLAGS", "VARIANCE", "ZODI"}
        missing = required - names
        if missing:
            raise PipelineError(
                f"Cutout is missing required extensions: {sorted(missing)}"
            )

        image = np.array(hdul["IMAGE"].data, dtype=np.float64, copy=True)
        flags = np.array(hdul["FLAGS"].data, dtype=np.uint32, copy=True)
        variance = np.array(hdul["VARIANCE"].data, dtype=np.float64, copy=True)
        zodi = np.array(hdul["ZODI"].data, dtype=np.float64, copy=True)

        if image.shape != flags.shape or image.shape != zodi.shape:
            raise PipelineError(
                "IMAGE, FLAGS and ZODI shapes differ: "
                f"{image.shape}, {flags.shape}, {zodi.shape}"
            )
        if image.shape != variance.shape:
            variance = np.broadcast_to(variance, image.shape).astype(
                np.float64, copy=True
            )

        # 1. Zodiacal light is not subtracted in the Level 2 product.
        image = image - zodi
        image[~np.isfinite(zodi)] = np.nan

        # 2. Local background on source-masked, artifact-masked pixels only.
        background = estimate_background(image, flags)
        local_background = float(np.median(background.model))
        image = image - background.model

        # 3. Hard-mask defects only; BIT_SOURCE is preserved in the image.
        #    HALO display mode keeps HALO pixels visible but still records them
        #    in the all-hard mask used by photometry.
        hard_bad = (flags & flag_policy.HARD_BAD_MASK) != 0
        display_bad = (flags & int(display_bad_mask)) != 0
        halo_mask = (flags & flag_policy.HALO_BIT) != 0
        image[display_bad] = np.nan

        warning = (flags & flag_policy.ARTIFACT_WARNING_MASK) != 0
        source = (flags & flag_policy.BIT_SOURCE) != 0

        variance_bad = display_bad | ~np.isfinite(variance) | (variance <= 0)
        variance = np.where(variance_bad, np.nan, variance)
        valid_variance = variance[~display_bad & np.isfinite(variance) & (variance > 0)]
        variance_floor = (
            float(np.nanmedian(valid_variance)) if valid_variance.size > 0 else 0.0
        )

        image_header = hdul["IMAGE"].header.copy()
        spatial_wcs = WCS(image_header)
        native_scale = _native_pixel_scale_arcsec(spatial_wcs)

        target = SkyCoord(
            ra=float(target_ra), dec=float(target_dec), unit="deg", frame="icrs"
        )
        target_x, target_y = spatial_wcs.world_to_pixel(target)
        target_x = float(target_x)
        target_y = float(target_y)

        wavelength_um: float | None = None
        bandwidth_um: float | None = None
        lvf_pa_deg: float | None = None
        lvf_grad: float | None = None
        if (
            np.isfinite(target_x)
            and np.isfinite(target_y)
            and 0.0 <= target_x <= image.shape[1] - 1
            and 0.0 <= target_y <= image.shape[0] - 1
        ):
            # LAW 3: the spectral lookup must not inherit the spatial SIP.
            astropy_logger = logging.getLogger("astropy")
            astropy_wcs_logger = logging.getLogger("astropy.wcs")
            astropy_wcs_wcs_logger = logging.getLogger("astropy.wcs.wcs")
            previous_levels = {
                "astropy": astropy_logger.level,
                "astropy.wcs": astropy_wcs_logger.level,
                "astropy.wcs.wcs": astropy_wcs_wcs_logger.level,
            }
            astropy_logger.setLevel(logging.ERROR)
            astropy_wcs_logger.setLevel(logging.ERROR)
            astropy_wcs_wcs_logger.setLevel(logging.ERROR)
            try:
                spectral_wcs = WCS(image_header, fobj=hdul, key="W")
                spectral_wcs.sip = None
                wave, bandwidth = spectral_wcs.pixel_to_world(target_x, target_y)
            finally:
                astropy_logger.setLevel(previous_levels["astropy"])
                astropy_wcs_logger.setLevel(previous_levels["astropy.wcs"])
                astropy_wcs_wcs_logger.setLevel(previous_levels["astropy.wcs.wcs"])
            wavelength_um = float(wave.to(u.micrometer).value)
            bandwidth_um = float(bandwidth.to(u.micrometer).value)
            geometry = lvf_geometry.geometry_at(
                spectral_wcs, spatial_wcs, target_x, target_y
            )
            if geometry is not None:
                lvf_pa_deg, lvf_grad = geometry

        aperture = _native_aperture_stats(flags, target_x, target_y, native_scale)
        # Denominator for the HALO gate: exclude all hard pixels (including
        # HALO) even when HALO is visible in display mode, so the fraction is
        # stable between golden and live manifests.
        native_finite = int(
            np.count_nonzero(np.isfinite(image) & ~hard_bad)
        )
        halo_pixels = int(np.count_nonzero(flags & flag_policy.HALO_BIT))

        return ParsedCutout(
            image_mjy_sr=image,
            variance_mjy_sr2=variance,
            flags=flags,
            warning_mask=warning,
            source_mask=source,
            hard_bad_mask=hard_bad,
            display_bad_mask=display_bad,
            halo_mask=halo_mask,
            spatial_wcs=spatial_wcs,
            spectral_wavelength_um=wavelength_um,
            spectral_bandwidth_um=bandwidth_um,
            local_background_mjy_sr=local_background,
            variance_floor_mjy_sr2=variance_floor,
            native_pixel_scale_arcsec=native_scale,
            target_x=target_x,
            target_y=target_y,
            native_shape=(int(image.shape[1]), int(image.shape[0])),
            native_finite_count=native_finite,
            aperture_pixel_count=aperture["aperture_pixel_count"],
            aperture_warning_names=aperture["aperture_warning_names"],
            aperture_source_bit=aperture["aperture_source_bit"],
            halo_pixel_count=halo_pixels,
            halo_aperture_pixel_count=aperture["halo_aperture_pixel_count"],
            lvf_pa_deg=lvf_pa_deg,
            lvf_grad_um_per_arcsec=lvf_grad,
            background_metadata=background.metadata,
        )


# ---------------------------------------------------------------------------
# Reprojection
# ---------------------------------------------------------------------------
def reproject_to_grid(parsed: ParsedCutout, out_wcs: WCS) -> ReprojectedFrame:
    """Reproject the prepared cutout to the contract grid (approx. variance)."""
    shape_out = (GRID_HEIGHT, GRID_WIDTH)
    display_mask = parsed.display_bad_mask
    if display_mask is None:
        display_mask = parsed.hard_bad_mask
    halo_mask = parsed.halo_mask
    if halo_mask is None:
        halo_mask = (parsed.flags & flag_policy.HALO_BIT) != 0
    image_out, footprint = reproject_interp(
        (parsed.image_mjy_sr, parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="bilinear",
    )
    variance_out, _ = reproject_interp(
        (parsed.variance_mjy_sr2, parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="bilinear",
    )
    warning_raw, _ = reproject_interp(
        (parsed.warning_mask.astype(np.uint8), parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
    )
    hard_raw, _ = reproject_interp(
        (parsed.hard_bad_mask.astype(np.uint8), parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
    )
    display_raw, _ = reproject_interp(
        (display_mask.astype(np.uint8), parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
    )
    halo_raw, _ = reproject_interp(
        (halo_mask.astype(np.uint8), parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
    )
    source_raw, _ = reproject_interp(
        (parsed.source_mask.astype(np.uint8), parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
    )
    # B8 telemetry: reproject the raw Table 16 bitmask with nearest-neighbour.
    # Values up to 2**32-1 are exactly representable in float64, so the
    # round-trip through reproject (which works in float) is lossless.
    flags_raw, _ = reproject_interp(
        (parsed.flags.astype(np.float64), parsed.spatial_wcs),
        out_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
    )

    coverage = np.asarray(footprint, dtype=float) > 0.0
    warning_out = np.asarray(warning_raw, dtype=float) > 0.5
    hard_out = np.asarray(hard_raw, dtype=float) > 0.5
    display_out = np.asarray(display_raw, dtype=float) > 0.5
    halo_out = np.asarray(halo_raw, dtype=float) > 0.5
    source_out = np.asarray(source_raw, dtype=float) > 0.5

    image_out = np.asarray(image_out, dtype=np.float64)
    image_out = np.where(coverage, image_out, np.nan)
    image_out[display_out] = np.nan

    flags_out = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=np.uint32)
    flags_valid = coverage & np.isfinite(flags_raw)
    if np.any(flags_valid):
        flags_out[flags_valid] = np.rint(
            np.asarray(flags_raw, dtype=np.float64)[flags_valid]
        ).astype(np.uint32)

    variance_out = np.asarray(variance_out, dtype=np.float64)
    variance_out = np.where(
        np.isfinite(variance_out) & (variance_out > 0),
        variance_out,
        parsed.variance_floor_mjy_sr2,
    )
    if parsed.variance_floor_mjy_sr2 > 0:
        # Interpolating variance under-estimates noise; floor it and label the
        # uncertainty as approximate (AGENTS.md §4.4).
        variance_out = np.fmax(variance_out, parsed.variance_floor_mjy_sr2)
    variance_out[~coverage | display_out | ~np.isfinite(image_out)] = np.nan

    # Mask BEFORE interpolation: otherwise a warning pixel can contaminate a
    # clean nearest-neighbour flag pixel through its bilinear neighbours.
    measurement_clean = ((parsed.flags & flag_policy.PHOTOMETRY_EXCLUDE_MASK) == 0)
    if parsed.background_metadata is not None and not parsed.background_metadata.get("subtracted"):
        measurement_clean[:] = False
    science_image, science_footprint = reproject_interp(
        (np.where(measurement_clean, parsed.image_mjy_sr, np.nan), parsed.spatial_wcs),
        out_wcs, shape_out=shape_out, order="bilinear",
    )
    science_variance, _ = reproject_interp(
        (np.where(measurement_clean, parsed.variance_mjy_sr2, np.nan), parsed.spatial_wcs),
        out_wcs, shape_out=shape_out, order="bilinear",
    )
    science_image = np.asarray(science_image, dtype=float)
    science_variance = np.asarray(science_variance, dtype=float)
    science_valid = (np.asarray(science_footprint) > 0) & np.isfinite(science_image) & np.isfinite(science_variance) & (science_variance > 0)
    science_image[~science_valid] = np.nan
    science_variance = np.where(science_valid, np.maximum(science_variance, parsed.variance_floor_mjy_sr2), np.nan)

    return ReprojectedFrame(
        image_mjy_sr=image_out,
        variance_mjy_sr2=variance_out,
        warning_mask=warning_out,
        source_mask=source_out,
        hard_bad_mask=hard_out,
        display_bad_mask=display_out,
        halo_mask=halo_out,
        footprint=coverage.astype(float),
        flags=flags_out,
        measurement_image_mjy_sr=science_image,
        measurement_variance_mjy_sr2=science_variance,
    )


# ---------------------------------------------------------------------------
# Epoch grouping and visit selection
# ---------------------------------------------------------------------------
def _semester_of(mjd: float) -> tuple[int, int]:
    """Map an MJD to the survey semester (start year, 1=May-Oct, 2=Nov-Apr)."""
    moment = Time(float(mjd), format="mjd", scale="utc").to_datetime()
    year, month = moment.year, moment.month
    if 5 <= month <= 10:
        return year, 1
    if month >= 11:
        return year, 2
    return year - 1, 2


def _semester_label(year: int, semester: int) -> str:
    if semester == 1:
        return f"May\u2013Oct {year}"
    return f"Nov {year}\u2013Apr {year + 1}"


def group_epochs(records: list[ArtifactRecord]) -> list[EpochBucket]:
    """Group TAP/SIA2 records into 6-month survey epochs.

    Epoch IDs are ``{start_year}_E{index}`` with a 1-based chronological index
    within that start year, computed on the full available set (O1 §8).
    """
    buckets: dict[tuple[int, int], list[ArtifactRecord]] = defaultdict(list)
    for record in records:
        buckets[_semester_of(record.mjd_lower)].append(record)

    per_year_index: dict[int, int] = defaultdict(int)
    epochs: list[EpochBucket] = []
    for (year, semester) in sorted(buckets):
        per_year_index[year] += 1
        index = per_year_index[year]
        epoch_records = tuple(
            sorted(
                buckets[(year, semester)],
                key=lambda item: (item.mjd_lower, item.band, item.uri),
            )
        )
        epochs.append(
            EpochBucket(
                epoch_id=f"{year}_E{index}",
                index=index,
                year=year,
                semester=semester,
                label=f"Survey Epoch {index} ({_semester_label(year, semester)})",
                records=epoch_records,
                mjd_start=min(record.mjd_lower for record in epoch_records),
                mjd_end=max(record.mjd_mid for record in epoch_records),
            )
        )
    return epochs


def mixed_release_label(releases: set[str]) -> str:
    """Return the contract label for an epoch built from differing releases.

    Revision-2 historical data mixed QR2 with QR3 (per-epoch labels may already
    be ``QR2+QR3``).  After DR1, any mixture involving DR1 is labelled
    ``DR1+QR3`` (the accepted contract value).
    """
    if all("DR1" not in release for release in releases):
        return "QR2+QR3"
    return "DR1+QR3"


def epoch_collection_release(epoch: EpochBucket) -> tuple[str, str]:
    """Per-epoch collection/release, ``mixed`` if the records differ."""
    releases = {record.release for record in epoch.records if record.release != "unknown"}
    if not releases:
        return "spherex", "unknown"
    if len(releases) == 1:
        release = next(iter(releases))
        return (f"spherex_{release.lower()}", release)
    return "mixed", mixed_release_label(releases)


def _select_visits(records: list[ArtifactRecord], max_visits: int) -> list[ArtifactRecord]:
    """Pick up to ``max_visits`` evenly spaced visits from a band/epoch."""
    ordered = sorted(records, key=lambda item: (item.mjd_lower, item.uri))
    if len(ordered) <= max_visits:
        return ordered
    count = max(1, int(max_visits))
    indices = np.unique(
        np.linspace(0, len(ordered) - 1, num=count, dtype=int)
    ).tolist()
    return [ordered[index] for index in indices]


# ---------------------------------------------------------------------------
# Coadding
# ---------------------------------------------------------------------------
def _combine_arrays(arrays: list[np.ndarray]) -> np.ndarray | None:
    """NaN-aware mean of several same-shape arrays."""
    if not arrays:
        return None
    stack = np.stack(arrays)
    if not np.any(np.isfinite(stack)):
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(stack, axis=0)


def _coadd_band(
    epoch_id: str,
    band: int,
    records: list[ArtifactRecord],
    contents: dict[ArtifactRecord, bytes],
    out_wcs: WCS,
    target_ra: float,
    target_dec: float,
    display_bad_mask: int = flag_policy.HARD_BAD_MASK,
    field_size_deg: float | None = None,
) -> BandCoadd | None:
    """Inverse-variance coadd of one band's visits in one epoch."""
    shape = (GRID_HEIGHT, GRID_WIDTH)
    sum_weight = np.zeros(shape, dtype=np.float64)
    sum_weight_image = np.zeros(shape, dtype=np.float64)
    display_weight = np.zeros(shape, dtype=np.float64)
    display_weight_image = np.zeros(shape, dtype=np.float64)
    backgrounds = []
    warning_mask = np.zeros(shape, dtype=bool)
    source_mask = np.zeros(shape, dtype=bool)
    hard_mask = np.zeros(shape, dtype=bool)
    halo_mask = np.zeros(shape, dtype=bool)
    footprint = np.zeros(shape, dtype=bool)
    flags_union = np.zeros(shape, dtype=np.uint32)

    used_records: list[ArtifactRecord] = []
    mjd_values: list[float] = []
    wavelengths: list[float] = []
    bandwidths: list[float] = []
    lvf_pa_values: list[float] = []
    lvf_grad_values: list[float] = []
    native_scales: list[float] = []
    aperture_names: set[str] = set()
    aperture_source = False
    halo_pixels = 0
    halo_aperture = 0
    aperture_count = 0
    native_finite = 0

    for record in records:
        content = contents.get(record)
        if content is None:
            continue
        parsed = parse_cutout(
            content,
            target_ra,
            target_dec,
            display_bad_mask=display_bad_mask,
        )
        frame = reproject_to_grid(parsed, out_wcs)
        if field_size_deg is not None:
            retained = field_pixel_mask(field_size_deg)
            frame = replace(frame,
                image_mjy_sr=np.where(retained, frame.image_mjy_sr, np.nan),
                variance_mjy_sr2=np.where(retained, frame.variance_mjy_sr2, np.nan),
                measurement_image_mjy_sr=np.where(retained, frame.measurement_image_mjy_sr, np.nan),
                measurement_variance_mjy_sr2=np.where(retained, frame.measurement_variance_mjy_sr2, np.nan),
                warning_mask=frame.warning_mask & retained, source_mask=frame.source_mask & retained,
                hard_bad_mask=frame.hard_bad_mask & retained, display_bad_mask=frame.display_bad_mask & retained,
                halo_mask=frame.halo_mask & retained, footprint=np.where(retained, frame.footprint, 0),
                flags=np.where(retained, frame.flags, 0).astype(np.uint32),
            )

        display_valid = (
            np.isfinite(frame.image_mjy_sr)
            & np.isfinite(frame.variance_mjy_sr2)
            & (frame.variance_mjy_sr2 > 0)
        )
        display_w = np.where(display_valid, 1.0 / np.where(display_valid, frame.variance_mjy_sr2, 1.0), 0.0)
        display_weight += display_w
        display_weight_image += display_w * np.where(display_valid, frame.image_mjy_sr, 0.0)
        science_image = frame.measurement_image_mjy_sr
        science_variance = frame.measurement_variance_mjy_sr2
        if science_image is None or science_variance is None:
            raise PipelineError("Measurement reprojection was not produced")
        valid = np.isfinite(science_image) & np.isfinite(science_variance) & (science_variance > 0)
        safe_variance = np.where(valid, science_variance, 1.0)
        weight = np.where(valid, 1.0 / safe_variance, 0.0)
        sum_weight += weight
        sum_weight_image += weight * np.where(valid, science_image, 0.0)
        backgrounds.append(parsed.background_metadata or {"status": "unknown", "subtracted": False})

        warning_mask |= frame.warning_mask
        source_mask |= frame.source_mask
        hard_mask |= frame.hard_bad_mask
        halo_mask |= frame.halo_mask
        footprint |= frame.footprint > 0.0
        if frame.flags is not None:
            flags_union |= frame.flags

        used_records.append(record)
        mjd_values.append(record.mjd_mid)
        if parsed.spectral_wavelength_um is not None:
            wavelengths.append(parsed.spectral_wavelength_um)
        if parsed.spectral_bandwidth_um is not None:
            bandwidths.append(parsed.spectral_bandwidth_um)
        if (
            parsed.lvf_pa_deg is not None
            and parsed.lvf_grad_um_per_arcsec is not None
        ):
            lvf_pa_values.append(float(parsed.lvf_pa_deg))
            lvf_grad_values.append(float(parsed.lvf_grad_um_per_arcsec))
        native_scales.append(parsed.native_pixel_scale_arcsec)
        aperture_names.update(parsed.aperture_warning_names)
        aperture_source = aperture_source or parsed.aperture_source_bit
        halo_pixels += parsed.halo_pixel_count
        halo_aperture += parsed.halo_aperture_pixel_count
        aperture_count += parsed.aperture_pixel_count
        native_finite += parsed.native_finite_count

    if not used_records:
        return None

    good = sum_weight > 0.0
    image = np.full(shape, np.nan, dtype=np.float64)
    variance = np.full(shape, np.nan, dtype=np.float64)
    image[good] = sum_weight_image[good] / sum_weight[good]
    variance[good] = 1.0 / sum_weight[good]
    display_image = np.full(shape, np.nan, dtype=np.float64)
    display_good = display_weight > 0
    display_image[display_good] = display_weight_image[display_good] / display_weight[display_good]

    coadd = BandCoadd(
        band=band,
        image_mjy_sr=image,
        variance_mjy_sr2=variance,
        warning_mask=warning_mask,
        source_mask=source_mask,
        hard_bad_mask=hard_mask,
        halo_mask=halo_mask,
        footprint=footprint,
        flags=flags_union,
        requested_visits=len(records),
        used_visits=len(used_records),
        artifact_uris=tuple(record.uri for record in used_records),
        mjd_values=tuple(mjd_values),
        wavelengths_um=tuple(wavelengths),
        bandwidths_um=tuple(bandwidths),
        native_pixel_scale_arcsec=(
            float(np.mean(native_scales)) if native_scales else NATIVE_PIXEL_SCALE_ARCSEC
        ),
        aperture_warning_names=frozenset(aperture_names),
        aperture_source_bit=bool(aperture_source),
        halo_pixel_count=int(halo_pixels),
        halo_aperture_pixel_count=int(halo_aperture),
        aperture_pixel_count=int(aperture_count),
        native_finite_count=int(native_finite),
        lvf_pa_deg_values=tuple(lvf_pa_values),
        lvf_grad_values=tuple(lvf_grad_values),
        display_image_mjy_sr=display_image,
        background_metadata=tuple(backgrounds),
    )
    coadd.stats = _compute_band_stats(coadd)
    return coadd


def _compute_band_stats(coadd: BandCoadd) -> dict[str, Any]:
    image = coadd.image_mjy_sr
    finite = np.isfinite(image)
    finite_count = int(np.count_nonzero(finite))
    coverage_count = int(np.count_nonzero(coadd.footprint))
    p5, p50, p99_5 = (
        (None, None, None)
        if finite_count == 0
        else tuple(
            float(value)
            for value in np.percentile(image[finite], [5.0, 50.0, 99.5])
        )
    )
    display_finite = np.isfinite(coadd.display_image_mjy_sr) if coadd.display_image_mjy_sr is not None else finite
    display_count = int(np.count_nonzero(display_finite))
    artifact_pixels = int(np.count_nonzero(coadd.warning_mask & display_finite))
    source_pixels = int(np.count_nonzero(coadd.source_mask & finite))
    hard_pixels = int(
        np.count_nonzero(
            coadd.hard_bad_mask & np.isfinite(image) & ~coadd.halo_mask
        )
    )
    halo_fraction = (
        coadd.halo_pixel_count / coadd.native_finite_count
        if coadd.native_finite_count
        else 0.0
    )
    halo_aperture_fraction = (
        coadd.halo_aperture_pixel_count / coadd.aperture_pixel_count
        if coadd.aperture_pixel_count
        else 0.0
    )
    return {
        "band": int(coadd.band),
        "wavelength_um": _json_float(
            float(np.mean(coadd.wavelengths_um)) if coadd.wavelengths_um else None
        ),
        "bandwidth_um": _json_float(
            float(np.mean(coadd.bandwidths_um)) if coadd.bandwidths_um else None
        ),
        "native_pixel_scale_arcsec": _json_float(coadd.native_pixel_scale_arcsec),
        "requested_visits": int(coadd.requested_visits),
        "used_visits": int(coadd.used_visits),
        "mjd_mean": _json_float(float(np.mean(coadd.mjd_values)) if coadd.mjd_values else None),
        "mjd_min": min(coadd.mjd_values) if coadd.mjd_values else None,
        "mjd_max": max(coadd.mjd_values) if coadd.mjd_values else None,
        "wavelength_samples_um": list(coadd.wavelengths_um),
        "bandwidth_samples_um": list(coadd.bandwidths_um),
        "measurement_mask": "HARD_BAD_MASK | ARTIFACT_WARNING_MASK before interpolation",
        "background_estimates": list(coadd.background_metadata),
        "p5_mjy_sr": _json_float(p5),
        "p50_mjy_sr": _json_float(p50),
        "p99_5_mjy_sr": _json_float(p99_5),
        "min_mjy_sr": _json_float(float(np.nanmin(image)) if finite_count else None),
        "max_mjy_sr": _json_float(float(np.nanmax(image)) if finite_count else None),
        "finite_pixels": finite_count,
        "coverage_fraction": coverage_count / (GRID_WIDTH * GRID_HEIGHT),
        "artifact_pixel_count": artifact_pixels,
        "artifact_pixel_fraction": artifact_pixels / display_count if display_count else 0.0,
        "source_pixel_count": source_pixels,
        "source_pixel_fraction": source_pixels / finite_count if finite_count else 0.0,
        "hard_bad_pixel_count": hard_pixels,
        "hard_bad_fraction": hard_pixels / coverage_count if coverage_count else 0.0,
        "halo_pixel_count": int(coadd.halo_pixel_count),
        "halo_fraction": float(halo_fraction),
        "halo_aperture_pixel_count": int(coadd.halo_aperture_pixel_count),
        "halo_aperture_fraction": float(halo_aperture_fraction),
        "aperture_pixel_count": int(coadd.aperture_pixel_count),
        "aperture_warning_flags": sorted(coadd.aperture_warning_names),
        "source_bit_set": bool(coadd.aperture_source_bit),
        "artifact_uris": list(coadd.artifact_uris),
    }


# ---------------------------------------------------------------------------
# LAW 8 normalization
# ---------------------------------------------------------------------------
def _normalization_candidates(
    coadds: dict[tuple[str, int], BandCoadd],
) -> dict[tuple[str, int], dict[str, Any]]:
    region = _normalization_region()
    candidates: dict[tuple[str, int], dict[str, Any]] = {}
    for key, coadd in coadds.items():
        finite = np.isfinite(coadd.image_mjy_sr)
        clean = ~coadd.warning_mask & ~coadd.hard_bad_mask & finite & region
        static = clean & coadd.source_mask
        fallback = clean
        candidates[key] = {
            "n_static": int(np.count_nonzero(static)),
            "p_static": _percentile(coadd.image_mjy_sr[static], 99.5),
            "n_fallback": int(np.count_nonzero(fallback)),
            "p_fallback": _percentile(coadd.image_mjy_sr[fallback], 99.5),
        }
    return candidates


def _compute_normalization(
    candidates: dict[tuple[str, int], dict[str, Any]],
    epochs: list[EpochBucket],
    bands_by_epoch: dict[str, set[int]],
) -> dict[str, Any]:
    """O1 §5 reference selection, fallback, clamp, and status aggregation."""
    epoch_ids = [epoch.epoch_id for epoch in epochs]
    band_set = sorted(set().union(*bands_by_epoch.values())) if bands_by_epoch else []
    scale_by: dict[str, dict[str, float]] = defaultdict(dict)
    raw_scale_by: dict[str, dict[str, float | None]] = defaultdict(dict)
    method_by: dict[str, dict[str, str]] = defaultdict(dict)
    status_by: dict[str, dict[str, str]] = defaultdict(dict)
    n_static_by: dict[str, dict[str, int]] = defaultdict(dict)
    n_fallback_by: dict[str, dict[str, int]] = defaultdict(dict)

    def _passes_static(epoch_id: str, band: int) -> bool:
        return candidates[(epoch_id, band)]["n_static"] >= 50

    def _passes_fallback(epoch_id: str, band: int) -> bool:
        return candidates[(epoch_id, band)]["n_fallback"] >= 100

    if len(epoch_ids) == 1:
        epoch_id = epoch_ids[0]
        for band in band_set:
            scale_by[epoch_id][str(band)] = 1.0
            raw_scale_by[epoch_id][str(band)] = 1.0
            method_by[epoch_id][str(band)] = "not_needed_single_epoch"
            status_by[epoch_id][str(band)] = "not_needed_single_epoch"
            n_static_by[epoch_id][str(band)] = candidates[(epoch_id, band)]["n_static"]
            n_fallback_by[epoch_id][str(band)] = candidates[(epoch_id, band)]["n_fallback"]
        return {
            "method": "not_needed_single_epoch",
            "status": "not_needed_single_epoch",
            "reference_epoch": epoch_id,
            "reference_epoch_by_band": {str(band): epoch_id for band in band_set},
            "reference_percentile_by_band": {},
            "applied": False,
            "clamped": False,
            "raw_scale_by_epoch_band": dict(raw_scale_by),
            "scale_by_epoch_band": dict(scale_by),
            "method_by_epoch_band": dict(method_by),
            "status_by_epoch_band": dict(status_by),
            "n_static_by_epoch_band": dict(n_static_by),
            "n_fallback_by_epoch_band": dict(n_fallback_by),
            "band_weights_by_epoch": {
                epoch_id: {
                    str(band): 1.0 / len(bands_by_epoch[epoch_id])
                    for band in sorted(bands_by_epoch[epoch_id])
                }
                for epoch_id in epoch_ids
            },
        }

    # 1. Choose the global reference epoch.
    global_reference: str | None = None
    for epoch_id in epoch_ids:
        bands = sorted(bands_by_epoch[epoch_id])
        if bands and all(_passes_static(epoch_id, band) for band in bands):
            global_reference = epoch_id
            break
    if global_reference is None:
        best_count = -1
        for epoch_id in epoch_ids:
            count = sum(
                1 for band in bands_by_epoch[epoch_id] if _passes_static(epoch_id, band)
            )
            if count > best_count:
                best_count = count
                global_reference = epoch_id
    if global_reference is None:
        global_reference = epoch_ids[0]

    # 2. Choose a reference epoch per band, with the all-pixel fallback.
    reference_by_band: dict[int, dict[str, Any]] = {}
    for band in band_set:
        reference: dict[str, Any]
        if band in bands_by_epoch[global_reference] and _passes_static(
            global_reference, band
        ):
            reference = {
                "epoch_id": global_reference,
                "mode": "static_source_p99_5",
                "p_ref": candidates[(global_reference, band)]["p_static"],
            }
        else:
            static_epochs = [
                epoch_id
                for epoch_id in epoch_ids
                if band in bands_by_epoch[epoch_id] and _passes_static(epoch_id, band)
            ]
            if static_epochs:
                ref = static_epochs[0]
                reference = {
                    "epoch_id": ref,
                    "mode": "static_source_p99_5",
                    "p_ref": candidates[(ref, band)]["p_static"],
                }
            else:
                fallback_epochs = [
                    epoch_id
                    for epoch_id in epoch_ids
                    if band in bands_by_epoch[epoch_id]
                    and _passes_fallback(epoch_id, band)
                ]
                if fallback_epochs:
                    ref = fallback_epochs[0]
                    reference = {
                        "epoch_id": ref,
                        "mode": "all_pixels_p99_5_fallback",
                        "p_ref": candidates[(ref, band)]["p_fallback"],
                    }
                else:
                    reference = {
                        "epoch_id": None,
                        "mode": "insufficient_static_pixels",
                        "p_ref": None,
                    }
        reference_by_band[band] = reference

    # 3. Compute scales per epoch/band.
    any_applied = False
    any_clamped = False
    for epoch_id in epoch_ids:
        for band in sorted(bands_by_epoch[epoch_id]):
            reference = reference_by_band[band]
            candidate = candidates[(epoch_id, band)]
            n_static_by[epoch_id][str(band)] = candidate["n_static"]
            n_fallback_by[epoch_id][str(band)] = candidate["n_fallback"]

            raw_scale: float | None = None
            scale = 1.0
            method = "insufficient_static_pixels"
            status = "insufficient_static_pixels"

            if reference["mode"] == "insufficient_static_pixels":
                pass
            elif reference["mode"] == "static_source_p99_5":
                if candidate["n_static"] >= 50 and _valid_number(candidate["p_static"]):
                    p_epoch = candidate["p_static"]
                    method = "static_source_p99_5"
                    status = "ok"
                elif candidate["n_fallback"] >= 100 and _valid_number(
                    candidate["p_fallback"]
                ):
                    p_epoch = candidate["p_fallback"]
                    method = "all_pixels_p99_5_fallback"
                    status = "fallback_all_pixels"
                else:
                    p_epoch = None
                if p_epoch is not None and _valid_number(reference["p_ref"]):
                    raw_scale = float(reference["p_ref"]) / float(p_epoch)
                    clamped = raw_scale < 0.5 or raw_scale > 2.0
                    scale = min(2.0, max(0.5, raw_scale))
                    if clamped:
                        status = "clamped"
                        any_clamped = True
                else:
                    scale = 1.0
                    method = "insufficient_static_pixels"
                    status = "insufficient_static_pixels"
            else:  # all-pixel fallback reference
                if candidate["n_fallback"] >= 100 and _valid_number(
                    candidate["p_fallback"]
                ):
                    p_epoch = candidate["p_fallback"]
                    method = "all_pixels_p99_5_fallback"
                    status = "fallback_all_pixels"
                    if _valid_number(reference["p_ref"]):
                        raw_scale = float(reference["p_ref"]) / float(p_epoch)
                        clamped = raw_scale < 0.5 or raw_scale > 2.0
                        scale = min(2.0, max(0.5, raw_scale))
                        if clamped:
                            status = "clamped"
                            any_clamped = True
                    else:
                        scale = 1.0
                        method = "insufficient_static_pixels"
                        status = "insufficient_static_pixels"
                else:
                    scale = 1.0
                    method = "insufficient_static_pixels"
                    status = "insufficient_static_pixels"

            if (
                reference["epoch_id"] is not None
                and epoch_id != reference["epoch_id"]
                and abs(scale - 1.0) > 1e-6
            ):
                any_applied = True
            scale_by[epoch_id][str(band)] = float(scale)
            raw_scale_by[epoch_id][str(band)] = _json_float(raw_scale)
            method_by[epoch_id][str(band)] = method
            status_by[epoch_id][str(band)] = status

    # 4. Aggregate status and references.
    all_statuses = [
        status
        for epoch_id in epoch_ids
        for status in status_by[epoch_id].values()
    ]
    worst_status = max(all_statuses, key=lambda value: _SEVERITY.get(value, 3))
    references = {reference["epoch_id"] for reference in reference_by_band.values()}
    if len(references) == 1 and global_reference in references:
        reference_epoch: str | None = global_reference
    else:
        reference_epoch = "mixed"

    methods = {
        method for epoch_id in epoch_ids for method in method_by[epoch_id].values()
    }
    method = "static_source_p99_5" if methods == {"static_source_p99_5"} else "mixed"

    return {
        "method": method,
        "status": worst_status,
        "reference_epoch": reference_epoch,
        "reference_epoch_by_band": {
            str(band): reference["epoch_id"] for band, reference in reference_by_band.items()
        },
        "reference_percentile_by_band": {
            str(band): _json_float(reference["p_ref"])
            for band, reference in reference_by_band.items()
        },
        "reference_mode_by_band": {
            str(band): reference["mode"] for band, reference in reference_by_band.items()
        },
        "applied": bool(any_applied),
        "clamped": bool(any_clamped),
        "raw_scale_by_epoch_band": dict(raw_scale_by),
        "scale_by_epoch_band": dict(scale_by),
        "method_by_epoch_band": dict(method_by),
        "status_by_epoch_band": dict(status_by),
        "n_static_by_epoch_band": dict(n_static_by),
        "n_fallback_by_epoch_band": dict(n_fallback_by),
        "band_weights_by_epoch": {
            epoch_id: {
                str(band): 1.0 / len(bands_by_epoch[epoch_id])
                for band in sorted(bands_by_epoch[epoch_id])
            }
            for epoch_id in epoch_ids
        },
    }


def _apply_normalization(
    coadds: dict[tuple[str, int], BandCoadd],
    normalization: dict[str, Any],
) -> None:
    for (epoch_id, band), coadd in coadds.items():
        scale = float(normalization["scale_by_epoch_band"][epoch_id][str(band)])
        coadd.scale = scale
        display_image = coadd.display_image_mjy_sr if coadd.display_image_mjy_sr is not None else coadd.image_mjy_sr
        coadd.normalized_image_mjy_sr = display_image * scale
        coadd.normalized_variance_mjy_sr2 = coadd.variance_mjy_sr2 * (scale**2)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _display_limits(image: np.ndarray) -> tuple[float, float] | None:
    finite = np.isfinite(image)
    if int(np.count_nonzero(finite)) < 10:
        return None
    data = image[finite]
    try:
        vmin, vmax = ZScaleInterval(contrast=0.25, krej=2.5).get_limits(data)
    except Exception:  # noqa: BLE001 - fall back to percentiles
        vmin, vmax = np.percentile(data, [1.0, 99.0])
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        return None
    if vmax <= vmin:
        vmax = vmin + 1.0
    return float(vmin), float(vmax)


def _save_webp(pixels: np.ndarray, path: Path) -> None:
    image = Image.fromarray(pixels, mode="L")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    image.save(
        temporary,
        format="WEBP",
        lossless=True,
        quality=WEBP_QUALITY,
        method=6,
    )
    os.replace(temporary, path)


def render_webp(
    image_mjy_sr: np.ndarray,
    path: Path,
    *,
    limits: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    """Render a shared-stretch 8-bit grayscale WebP frame."""
    finite = np.isfinite(image_mjy_sr)
    if int(np.count_nonzero(finite)) < 10:
        raise NoUsablePixelsError("Not enough finite pixels to render a frame")
    active_limits = limits or _display_limits(image_mjy_sr)
    if active_limits is None:
        raise NoUsablePixelsError("Could not determine display limits")
    vmin, vmax = active_limits
    if vmax <= vmin:
        vmax = vmin + 1.0
    filled = np.where(finite, image_mjy_sr, vmin)
    unit = np.clip((filled - vmin) / (vmax - vmin), 0.0, 1.0)
    pixels = (np.clip(AsinhStretch(a=ASINH_A)(unit), 0.0, 1.0) * 255.0).astype(
        np.uint8
    )
    _save_webp(pixels, path)
    return active_limits


def _symmetric_limit(arrays: list[np.ndarray]) -> float | None:
    values: list[float] = []
    for array in arrays:
        finite = array[np.isfinite(array)]
        if finite.size:
            values.append(float(np.percentile(np.abs(finite), 99.5)))
    if not values:
        return None
    vmax = max(values)
    return vmax if vmax > 0 else 1e-6


def render_difference_webp(
    difference: np.ndarray,
    path: Path,
    *,
    vmax: float | None = None,
) -> float | None:
    """Render a zero-centred 8-bit grayscale difference frame."""
    finite = np.isfinite(difference)
    if int(np.count_nonzero(finite)) < 10:
        return None
    active_vmax = vmax if vmax is not None and vmax > 0 else _symmetric_limit([difference])
    if active_vmax is None or active_vmax <= 0:
        active_vmax = 1e-6
    unit = np.clip((difference + active_vmax) / (2.0 * active_vmax), 0.0, 1.0)
    unit = np.where(np.isfinite(unit), unit, 0.5)
    pixels = (unit * 255.0).astype(np.uint8)
    _save_webp(pixels, path)
    return active_vmax


def render_mask_webp(mask: np.ndarray, path: Path) -> None:
    """Render a binary artifact mask; white pixels carry warning bits."""
    pixels = (np.asarray(mask, dtype=bool).astype(np.uint8)) * 255
    _save_webp(pixels, path)


# ---------------------------------------------------------------------------
# Flag summary
# ---------------------------------------------------------------------------
def _flag_summary(
    band_coadds: dict[int, BandCoadd],
    *,
    halo_display_mode: bool = False,
) -> dict[str, Any]:
    aperture_names = sorted(
        {
            name
            for coadd in band_coadds.values()
            for name in coadd.aperture_warning_names
        }
    )
    names = sorted(
        set(aperture_names) | ({"HALO"} if halo_display_mode else set())
    )
    source_bit = any(coadd.aperture_source_bit for coadd in band_coadds.values())
    fraction = max(
        (
            float(coadd.stats.get("artifact_pixel_fraction", 0.0))
            for coadd in band_coadds.values()
        ),
        default=0.0,
    )
    status = flag_policy.flag_status(
        names, fraction, halo_display_mode=halo_display_mode
    )

    pieces: list[str] = []
    prefix = "Multiple bands. " if len(band_coadds) > 1 else ""
    if aperture_names:
        pieces.append(
            f"{prefix}Warning flags in the 12.3\u2033 target aperture: "
            f"{', '.join(aperture_names)}."
        )
    else:
        pieces.append(
            f"{prefix}No warning flags in the 12.3\u2033 target aperture."
        )
    if source_bit:
        pieces.append("Bit 21 (SOURCE) confirms a cataloged object.")
    else:
        pieces.append("Bit 21 (SOURCE) is not set in the aperture.")
    pieces.append(f"Artifact pixels cover {fraction:.1%} of the finite frame.")
    if status == _ALERT_STATUS:
        pieces.append("Alert-level warning flags are present; inspect the flag data.")
    elif status == "CAUTION":
        pieces.append("Caution advised.")
    else:
        pieces.append("No listed aperture warnings; this does not establish calibrated photometry.")
    if halo_display_mode:
        pieces.append(
            "HALO is shown in display-only mode and remains excluded from photometry."
        )
    backgrounds = [item for coadd in band_coadds.values() for item in coadd.background_metadata]
    if any(not item.get("subtracted") for item in backgrounds):
        pieces.append("Insufficient clean sky pixels for local background subtraction; affected measurements are unavailable.")
    pieces.append("Warning pixels remain visible but are excluded from measurement coadds and differences. Uncertainties are approximate.")

    return {
        "status": status,
        "source_bit_set": bool(source_bit),
        "artifact_pixel_fraction": float(fraction),
        "active_warning_flags": names,
        "human_explanation": " ".join(pieces),
    }


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------
def source_label(release: str) -> str:
    if release == "DR1":
        return "NASA/IPAC IRSA SPHEREx DR1"
    if release == "DR1+QR3":
        return "NASA/IPAC IRSA SPHEREx DR1/QR3"
    if release == "QR2":
        return "NASA/IPAC IRSA SPHEREx QR2"
    if release == "QR3":
        return "NASA/IPAC IRSA SPHEREx QR3"
    if release == "QR2+QR3":
        return "NASA/IPAC IRSA SPHEREx QR3/QR2"
    return "NASA/IPAC IRSA SPHEREx"


def _top_level_provenance(
    epochs_payload: list[dict[str, Any]],
    normalization: dict[str, Any],
) -> dict[str, Any]:
    releases = {
        str(epoch["release"]) for epoch in epochs_payload if epoch["release"] != "unknown"
    }
    if not releases:
        release = "unknown"
        collection = "spherex"
    elif len(releases) == 1:
        release = next(iter(releases))
        if release in {"QR2+QR3", "DR1+QR3"}:
            collection = "mixed"
        else:
            collection = f"spherex_{release.lower()}"
    else:
        release = mixed_release_label(releases)
        collection = "mixed"
    return {
        "source": source_label(release),
        "collection": collection,
        "release": release,
        "zodi_subtracted": True,
        "background_subtracted": all(
            entry.get("subtracted", False)
            for epoch in epochs_payload for stats in epoch.get("band_stats", {}).values()
            for entry in stats.get("background_estimates", [{"subtracted": False}])
        ),
        "flux_normalization": {
            "method": normalization["method"],
            "scope": "per_band_across_epochs",
            "reference_epoch": normalization["reference_epoch"],
            "applied": bool(normalization["applied"]),
            "status": normalization["status"],
            "clamped": bool(normalization["clamped"]),
            "raw_stats_location": "server_only",
        },
        "is_simulated_fallback": False,
        "citation": "SPHEREx Quick Release (JPL/Caltech/IRSA)",
    }


def _telemetry_flux_band(asset_key: str, available_bands: list[int]) -> str:
    """Contract 1.1.0: WISE 0855 ships the thermal coadd, everyone else ``all``."""
    if asset_key == "wise_0855" and any(band in (5, 6) for band in available_bands):
        return "thermal"
    return "all"


def _telemetry_bands(flux_band: str, available_bands: list[int]) -> list[int]:
    if flux_band == "thermal":
        return [band for band in (5, 6) if band in available_bands]
    return list(available_bands)


def epoch_lvf_geometry(
    band_coadds: dict[int, BandCoadd],
) -> list[dict[str, float | int]] | None:
    """One finite ``{detector, pa_deg, grad_um_per_arcsec}`` per usable band."""
    entries = [
        (
            band,
            coadd.lvf_pa_deg_values,
            coadd.lvf_grad_values,
        )
        for band, coadd in sorted(band_coadds.items())
    ]
    payload = lvf_geometry.aggregate_epoch_geometry(entries)
    return payload or None


def write_epoch_telemetry(
    asset_dir: Path,
    epoch_id: str,
    band_coadds: dict[int, BandCoadd],
    available_bands: list[int],
    asset_key: str,
) -> dict[str, Any] | None:
    """Write ``telemetry_{epoch_id}.bin.gz`` for normalized display intensity.

    The float16 plane is the same pre-normalized coadd that is rendered to the
    epoch ``all``/``thermal`` WebP.  The uint32 plane is the bitwise-OR union
    of the raw Table 16 flags of those bands on the reprojected grid.
    ``BIT_SOURCE`` is preserved; this sidecar never feeds photometry.
    """
    flux_band = _telemetry_flux_band(asset_key, available_bands)
    bands = _telemetry_bands(flux_band, available_bands)
    images = [
        band_coadds[band].normalized_image_mjy_sr
        for band in bands
        if band in band_coadds
        and band_coadds[band].normalized_image_mjy_sr is not None
    ]
    if not images:
        return None
    image = _combine_arrays(images)
    if image is None:
        return None
    flags = np.bitwise_or.reduce(
        [band_coadds[band].flags for band in bands if band in band_coadds]
    )
    filename = telemetry_codec.telemetry_filename(epoch_id)
    try:
        byte_size = telemetry_codec.write_telemetry_sidecar(
            asset_dir / filename, image, flags
        )
    except (OSError, telemetry_codec.TelemetryError) as exc:  # noqa: BLE001
        logger.warning("Telemetry sidecar failed for %s: %s", epoch_id, exc)
        return None
    return {
        "url": filename,
        "format": telemetry_codec.TELEMETRY_FORMAT,
        "width": telemetry_codec.TELEMETRY_WIDTH,
        "height": telemetry_codec.TELEMETRY_HEIGHT,
        "byte_size": int(byte_size),
        "flux_band": flux_band,
        "quantity": "normalized_display_intensity",
        "normalization_applied": any(abs(band_coadds[band].scale - 1.0) > 1e-6 for band in bands),
    }


def _build_epoch_payloads(
    epochs: list[EpochBucket],
    coadds: dict[tuple[str, int], BandCoadd],
    bands_by_epoch: dict[str, set[int]],
    normalization: dict[str, Any],
    candidates: dict[tuple[str, int], dict[str, Any]],
    asset_dir: Path,
    *,
    asset_key: str,
    halo_display_mode: bool = False,
    check_deadline: Callable[[], None] = lambda: None,
) -> list[dict[str, Any]]:
    epoch_ids = [epoch.epoch_id for epoch in epochs]
    band_limits: dict[int, tuple[float, float] | None] = {}
    for band in sorted({band for bands in bands_by_epoch.values() for band in bands}):
        reference_epoch = normalization["reference_epoch_by_band"].get(str(band))
        reference_coadd = (
            coadds.get((reference_epoch, band)) if reference_epoch else None
        )
        if reference_coadd is None:
            reference_coadd = next(
                (
                    coadds[(epoch_id, band)]
                    for epoch_id in epoch_ids
                    if (epoch_id, band) in coadds
                ),
                None,
            )
        band_limits[band] = (
            _display_limits(reference_coadd.normalized_image_mjy_sr)
            if reference_coadd is not None
            and reference_coadd.normalized_image_mjy_sr is not None
            else None
        )

    def _combined_limits(frame_type: str) -> tuple[float, float] | None:
        reference_epoch = normalization.get("reference_epoch")
        candidates = []
        if isinstance(reference_epoch, str) and reference_epoch != "mixed":
            candidates.append(reference_epoch)
        candidates.extend(epoch_id for epoch_id in epoch_ids if epoch_id not in candidates)
        for epoch_id in candidates:
            bands = sorted(bands_by_epoch.get(epoch_id, set()))
            if frame_type == "thermal":
                bands = [band for band in bands if band in (5, 6)]
            images = [
                coadds[(epoch_id, band)].normalized_image_mjy_sr
                for band in bands
                if (epoch_id, band) in coadds
                and coadds[(epoch_id, band)].normalized_image_mjy_sr is not None
            ]
            combined = _combine_arrays(images)
            limits = _display_limits(combined) if combined is not None else None
            if limits is not None:
                return limits
        return None

    all_limits = _combined_limits("all")
    thermal_limits = _combined_limits("thermal")

    payloads: list[dict[str, Any]] = []
    for epoch in epochs:
        check_deadline()
        bands = sorted(bands_by_epoch.get(epoch.epoch_id, set()))
        if not bands:
            continue
        band_coadds = {band: coadds[(epoch.epoch_id, band)] for band in bands}
        frames: dict[str, str] = {}
        band_stats: dict[str, Any] = {}

        for band in bands:
            check_deadline()
            coadd = band_coadds[band]
            filename = f"{epoch.epoch_id}_D{band}.webp"
            used_limits = band_limits.get(band)
            try:
                used_limits = render_webp(
                    coadd.normalized_image_mjy_sr,
                    asset_dir / filename,
                    limits=used_limits,
                )
            except NoUsablePixelsError:
                logger.warning("No finite pixels for %s D%s; omitting", epoch.epoch_id, band)
                continue
            frames[str(band)] = filename
            stats = dict(coadd.stats)
            stats["normalization"] = {
                "scale": float(coadd.scale),
                "raw_scale": normalization["raw_scale_by_epoch_band"]
                .get(epoch.epoch_id, {})
                .get(str(band)),
                "method": normalization["method_by_epoch_band"]
                .get(epoch.epoch_id, {})
                .get(str(band)),
                "status": normalization["status_by_epoch_band"]
                .get(epoch.epoch_id, {})
                .get(str(band)),
                "reference_epoch": normalization["reference_epoch_by_band"].get(str(band)),
                "n_static": normalization["n_static_by_epoch_band"]
                .get(epoch.epoch_id, {})
                .get(str(band)),
                "n_fallback": normalization["n_fallback_by_epoch_band"]
                .get(epoch.epoch_id, {})
                .get(str(band)),
                "p_static": _json_float(
                    candidates[(epoch.epoch_id, band)]["p_static"]
                ),
                "p_fallback": _json_float(
                    candidates[(epoch.epoch_id, band)]["p_fallback"]
                ),
            }
            band_stats[str(band)] = stats

        available_bands = [band for band in bands if str(band) in frames]
        if not available_bands:
            continue

        all_images = [
            band_coadds[band].normalized_image_mjy_sr for band in available_bands
        ]
        all_image = _combine_arrays(all_images)
        if all_image is not None:
            all_name = f"{epoch.epoch_id}_ALL.webp"
            try:
                render_webp(all_image, asset_dir / all_name, limits=all_limits)
                frames["all"] = all_name
            except NoUsablePixelsError:
                logger.warning("No finite all-band coadd for %s", epoch.epoch_id)

        thermal_bands = [band for band in (5, 6) if band in available_bands]
        if thermal_bands:
            thermal_images = [
                band_coadds[band].normalized_image_mjy_sr for band in thermal_bands
            ]
            thermal_image = _combine_arrays(thermal_images)
            if thermal_image is not None:
                thermal_name = f"{epoch.epoch_id}_B56.webp"
                try:
                    render_webp(
                        thermal_image,
                        asset_dir / thermal_name,
                        limits=thermal_limits,
                    )
                    frames["thermal"] = thermal_name
                except NoUsablePixelsError:
                    logger.warning(
                        "No finite thermal coadd for %s", epoch.epoch_id
                    )

        overlay = np.zeros((GRID_HEIGHT, GRID_WIDTH), dtype=bool)
        for coadd in band_coadds.values():
            overlay |= coadd.warning_mask
            if halo_display_mode:
                overlay |= coadd.halo_mask
        overlay_name = f"{epoch.epoch_id}_FLAGS.webp"
        render_mask_webp(overlay, asset_dir / overlay_name)
        frames["flag_overlay"] = overlay_name

        telemetry_payload = write_epoch_telemetry(
            asset_dir,
            epoch.epoch_id,
            band_coadds,
            available_bands,
            asset_key,
        )
        lvf_payload = epoch_lvf_geometry(band_coadds)

        mjd_values = [value for coadd in band_coadds.values() for value in coadd.mjd_values]
        mjd_mean = float(np.mean(mjd_values)) if mjd_values else epoch.mjd_mean
        collection, release = epoch_collection_release(epoch)
        payloads.append(
            {
                "epoch_id": epoch.epoch_id,
                "label": observation_label(observation_range(epoch.records), epoch.label),
                "observation_range": observation_range(epoch.records),
                "mjd_min": min(mjd_values) if mjd_values else None,
                "mjd_max": max(mjd_values) if mjd_values else None,
                "collection": collection,
                "release": release,
                "mjd_mean": mjd_mean,
                "date_iso": _mjd_to_date(mjd_mean).isoformat(),
                "frames": frames,
                "bands": sorted(available_bands),
                "all_bands": sorted(available_bands),
                "thermal_bands": thermal_bands,
                "halo_display_mode": bool(halo_display_mode),
                "flag_summary": _flag_summary(
                    band_coadds, halo_display_mode=halo_display_mode
                ),
                "telemetry": telemetry_payload,
                "lvf_geometry": lvf_payload,
                "band_stats": band_stats,
                "display_limits": {
                    str(band): list(limits) if limits is not None else None
                    for band, limits in band_limits.items()
                },
            }
        )
    return payloads


def _build_differences(
    epochs: list[EpochBucket],
    coadds: dict[tuple[str, int], BandCoadd],
    bands_by_epoch: dict[str, set[int]],
    asset_dir: Path,
    check_deadline: Callable[[], None] = lambda: None,
) -> dict[str, Any]:
    pair_data: list[dict[str, Any]] = []
    for earlier, later in zip(epochs, epochs[1:]):
        check_deadline()
        common_bands = sorted(
            bands_by_epoch.get(earlier.epoch_id, set())
            & bands_by_epoch.get(later.epoch_id, set())
        )
        if not common_bands:
            continue
        differences = {
            band: coadds[(later.epoch_id, band)].image_mjy_sr
            - coadds[(earlier.epoch_id, band)].image_mjy_sr
            for band in common_bands
        }
        all_difference = _combine_arrays(
            [differences[band] for band in common_bands]
        )
        thermal_bands = [band for band in (5, 6) if band in common_bands]
        thermal_difference = (
            _combine_arrays([differences[band] for band in thermal_bands])
            if len(thermal_bands) == 2
            else None
        )
        pair_data.append(
            {
                "earlier": earlier,
                "later": later,
                "common_bands": common_bands,
                "differences": differences,
                "all_difference": all_difference,
                "thermal_bands": thermal_bands,
                "thermal_difference": thermal_difference,
            }
        )

    band_limits: dict[int, float | None] = {}
    for band in range(1, 7):
        arrays = [
            item["differences"][band]
            for item in pair_data
            if band in item["differences"]
        ]
        band_limits[band] = _symmetric_limit(arrays)
    all_limit = _symmetric_limit(
        [
            item["all_difference"]
            for item in pair_data
            if item["all_difference"] is not None
        ]
    )
    thermal_limit = _symmetric_limit(
        [
            item["thermal_difference"]
            for item in pair_data
            if item["thermal_difference"] is not None
        ]
    )

    result: dict[str, Any] = {}
    for item in pair_data:
        check_deadline()
        earlier: EpochBucket = item["earlier"]
        later: EpochBucket = item["later"]
        prefix = f"diff_{later.epoch_id}_minus_{earlier.epoch_id}"
        frames: dict[str, str] = {}
        for band in item["common_bands"]:
            check_deadline()
            filename = f"{prefix}_D{band}.webp"
            if (
                render_difference_webp(
                    item["differences"][band],
                    asset_dir / filename,
                    vmax=band_limits.get(band),
                )
                is not None
            ):
                frames[str(band)] = filename
        if item["all_difference"] is not None:
            filename = f"{prefix}_ALL.webp"
            if (
                render_difference_webp(
                    item["all_difference"],
                    asset_dir / filename,
                    vmax=all_limit,
                )
                is not None
            ):
                frames["all"] = filename
        if item["thermal_difference"] is not None:
            filename = f"{prefix}_B56.webp"
            if (
                render_difference_webp(
                    item["thermal_difference"],
                    asset_dir / filename,
                    vmax=thermal_limit,
                )
                is not None
            ):
                frames["thermal"] = filename
        if not frames:
            continue
        result[f"{later.epoch_id}_minus_{earlier.epoch_id}"] = {
            "frames": frames,
            "common_bands": item["common_bands"],
            "thermal_bands": item["thermal_bands"],
        }
    return result


# ---------------------------------------------------------------------------
# Frame cache
# ---------------------------------------------------------------------------
def _asset_dir(asset_key: str) -> Path:
    return settings.live_cache_dir / asset_key


def _manifest_path(asset_key: str) -> Path:
    return _asset_dir(asset_key) / "frame.json"


def _load_cached_manifest(
    asset_key: str,
    ra: float,
    dec: float,
    cutout_size_deg: float,
    max_visits_per_band: int,
    halo_display_mode: bool | None,
    max_epochs: int | None = None,
) -> dict[str, Any] | None:
    path = _manifest_path(asset_key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    provenance = payload.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("is_simulated_fallback") is not False
    ):
        return None
    if payload.get("version") != CACHE_VERSION:
        return None
    query = payload.get("query") or {}
    if abs(float(query.get("ra", -999.0)) - float(ra)) > 1e-6:
        return None
    if abs(float(query.get("dec", -999.0)) - float(dec)) > 1e-6:
        return None
    if abs(float(query.get("cutout_size_deg", -1.0)) - float(cutout_size_deg)) > 1e-4:
        return None
    if int(payload.get("max_visits_per_band", -1)) != int(max_visits_per_band):
        return None
    if payload.get("max_epochs") != max_epochs:
        return None
    if max_epochs is not None and not payload.get("discovered_epoch_ids"):
        return None
    if (
        halo_display_mode is not None
        and bool(payload.get("halo_display_mode", False)) != bool(halo_display_mode)
    ):
        return None
    generated_text = payload.get("generated_at")
    if not generated_text:
        return None
    try:
        generated = datetime.fromisoformat(str(generated_text))
    except ValueError:
        return None
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    age = (_now_utc() - generated.astimezone(timezone.utc)).total_seconds()
    if age < 0 or age > settings.cache_ttl_seconds:
        return None
    asset_dir = _asset_dir(asset_key)
    for epoch in payload.get("epochs", []):
        for filename in epoch.get("frames", {}).values():
            if not (asset_dir / str(filename)).is_file():
                return None
        telemetry = epoch.get("telemetry")
        if isinstance(telemetry, dict):
            filename = telemetry.get("url")
            if not isinstance(filename, str) or not is_valid_filename(filename):
                return None
            path = asset_dir / filename
            if not path.is_file():
                return None
            if int(telemetry.get("byte_size", -1)) != path.stat().st_size:
                return None
    for pair in payload.get("differences", {}).values():
        for filename in pair.get("frames", {}).values():
            if not (asset_dir / str(filename)).is_file():
                return None
    return payload


def load_cached_manifest_any_mode(
    asset_key: str,
    ra: float,
    dec: float,
    cutout_size_deg: float,
    max_visits_per_band: int,
    max_epochs: int | None = None,
) -> dict[str, Any] | None:
    """Load a cached live manifest regardless of its HALO display mode.

    Used by the router to avoid rebuilding a HALO-display cache as hard-masked
    and then rebuilding it again on every live fallback request.
    """
    return _load_cached_manifest(
        asset_key,
        float(ra),
        float(dec),
        float(cutout_size_deg),
        int(max_visits_per_band),
        None,
        max_epochs,
    )


def _write_manifest(manifest: dict[str, Any]) -> None:
    path = _manifest_path(str(manifest["asset_key"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_manifest(
    asset_key: str,
    ra: float,
    dec: float,
    *,
    cutout_size_deg: float,
    max_visits_per_band: int | None = None,
    max_epochs: int | None = None,
    halo_display_mode: bool = False,
    live_mode: bool = False,
    deadline_seconds: float | None = None,
    force_refresh: bool = False,
    allow_single_epoch: bool = False,
    discovery_mode: str = "live",
    target_id: str | None = None,
) -> dict[str, Any]:
    """Share a build among concurrent requests for the same canonical field."""
    deadline_at = None if deadline_seconds is None else time.monotonic() + deadline_seconds
    # Filters are applied by the router after building. All configuration that
    # affects the underlying products belongs in this in-process work key.
    if live_mode:
        max_epochs = max(2, int(max_epochs or settings.live_sky_max_epochs))
    key = ("sky", asset_key, ra, dec, cutout_size_deg, max_visits_per_band,
           max_epochs, halo_display_mode, live_mode, force_refresh, allow_single_epoch,
           discovery_mode, target_id)
    return run_once(key, deadline_at, lambda: _build_manifest(
        asset_key, ra, dec, cutout_size_deg=cutout_size_deg,
        max_visits_per_band=max_visits_per_band, max_epochs=max_epochs,
        halo_display_mode=halo_display_mode, live_mode=live_mode,
        deadline_seconds=None if deadline_at is None else max(0.0, deadline_at - time.monotonic()),
        force_refresh=force_refresh,
        allow_single_epoch=allow_single_epoch,
        discovery_mode=discovery_mode, target_id=target_id,
    ), admission=(lambda: live_build_slot(settings)) if live_mode else None)


def _build_manifest(
    asset_key: str, ra: float, dec: float, *, cutout_size_deg: float,
    max_visits_per_band: int | None = None, max_epochs: int | None = None,
    halo_display_mode: bool = False, live_mode: bool = False,
    deadline_seconds: float | None = None, force_refresh: bool = False,
    archive_client: IrsaClient | None = None,
    allow_single_epoch: bool = False,
    discovery_mode: str = "live", target_id: str | None = None,
) -> dict[str, Any]:
    """Build (or load) the full per-position sky manifest.

    ``max_epochs`` limits the build to the latest N epochs (used by the live
    arbitrary-coordinate candidate budget). Live comparisons select a pair
    whose measured spectral WCS agrees across the requested output field. Discovery,
    SIA fallback, downloads and processing share a remaining deadline.
    """
    started = time.monotonic()
    if discovery_mode not in {"live", "known"}:
        raise ValueError("Unknown discovery mode")
    if discovery_mode == "known":
        if not live_mode or not target_id:
            raise ValueError("Known discovery requires an explicit live catalog request")
        force_refresh = True
    deadline_at = None if deadline_seconds is None else started + deadline_seconds
    visits = max(1, int(max_visits_per_band or settings.max_visits_per_band))
    if not force_refresh:
        cached = _load_cached_manifest(
            asset_key,
            float(ra),
            float(dec),
            float(cutout_size_deg),
            visits,
            bool(halo_display_mode),
            max_epochs,
        )
        if cached is not None:
            return cached

    display_bad_mask = (
        flag_policy.HALO_DISPLAY_BAD_MASK
        if halo_display_mode
        else flag_policy.HARD_BAD_MASK
    )
    if live_mode:
        live_settings = replace(
            settings,
            retries=settings.live_retries,
            retry_backoff_seconds=settings.live_retry_backoff_seconds,
            connect_timeout_seconds=settings.live_connect_timeout_seconds,
            request_timeout_seconds=settings.live_request_timeout_seconds,
            tap_timeout_seconds=settings.live_tap_timeout_seconds,
        )
        client = IrsaClient(live_settings, deadline_at=deadline_at, use_cache=not force_refresh)
    else:
        client = IrsaClient(deadline_at=deadline_at, use_cache=not force_refresh)

    if discovery_mode == "known":
        from services.known_exposures import KnownExposureClient
        client = KnownExposureClient(client.settings, target_id=target_id, deadline_at=deadline_at)
    if archive_client is not None:
        if discovery_mode == "known":
            raise ValueError("Known discovery cannot substitute a caller-provided inventory")
        client = archive_client
    records = client.query_artifacts(
        float(ra),
        float(dec),
        bands=None,
        fallback=True,
        allow_partial=live_mode,
    )
    _check_deadline(started, deadline_seconds)
    epochs = group_epochs(records)
    if not epochs:
        raise IRSANoData(
            "No SPHEREx observations cover this position.",
            collections_tried=list(DEFAULT_SIA_COLLECTIONS),
            detail={"ra": float(ra), "dec": float(dec)},
        )
    discovered_epoch_ids = [epoch.epoch_id for epoch in epochs]
    if max_epochs is not None and int(max_epochs) > 0 and len(epochs) > int(max_epochs):
        epochs = epochs[-int(max_epochs):]

    selected_by_epoch_band: dict[tuple[str, int], list[ArtifactRecord]] = {}
    selected_records: list[ArtifactRecord] = []
    for epoch in epochs:
        for band in range(1, 7):
            band_records = [
                record for record in epoch.records if record.band == band
            ]
            if not band_records:
                continue
            candidate_visits = max(3, visits) if len(epochs) > 1 else 1
            chosen = _select_visits(band_records, candidate_visits)
            selected_by_epoch_band[(epoch.epoch_id, band)] = chosen
            selected_records.extend(chosen)

    if not selected_records:
        raise IRSANoData(
            "No SPHEREx science artifacts matched the requested bands.",
            collections_tried=sorted({record.collection for record in records}),
            detail={"ra": float(ra), "dec": float(dec)},
        )

    # IRSA crops on the detector axes. A rotated native square of the same
    # width can miss corners of the requested north-up square. Enclose its
    # diagonal plus one native pixel on each side; the output/query FOV stays
    # unchanged. Actual detector edges may still leave missing coverage.
    comparison_size_deg = float(cutout_size_deg) if live_mode else GRID_WIDTH * CDELT_DEG
    download_size_deg = math.sqrt(2.0) * comparison_size_deg + 2 * NATIVE_PIXEL_SCALE_ARCSEC / 3600.0
    download_options = {}
    if live_mode and deadline_at is not None:
        # Keep enough of the single request budget to process real downloaded
        # pixels. Waiting for every slow candidate must not discard all images.
        download_options = {"stage_deadline_at": time.monotonic() + .55 * max(0., deadline_at-time.monotonic()),
                            "allow_partial": True}
    comparison_first = live_mode and len(epochs) > 1
    contents = {} if comparison_first else client.fetch_cutouts(
        selected_records,
        float(ra),
        float(dec),
        download_size_deg,
        **download_options,
    )
    _check_deadline(started, deadline_seconds)
    missing_candidates = sum(record not in contents for record in selected_records)
    if not contents and not comparison_first:
        if live_mode:
            raise IRSAUnavailable("No live cutouts could be downloaded.")
        raise NoUsablePixelsError("No cutouts could be downloaded")

    candidate_selection = {key: list(values) for key, values in selected_by_epoch_band.items()}
    comparison_note = None
    candidate_epoch_ids = [epoch.epoch_id for epoch in epochs]
    out_wcs = output_wcs(float(ra), float(dec))
    candidate_coadds: dict[ArtifactRecord, BandCoadd | None] = {}
    record_epochs = {record: epoch.epoch_id for epoch in epochs for record in epoch.records}

    def usable_candidate(record: ArtifactRecord) -> bool:
        _check_deadline(started, deadline_seconds)
        if record not in candidate_coadds:
            candidate_coadds[record] = _coadd_band(
                record_epochs[record], record.band, [record], {record: contents[record]},
                out_wcs, float(ra), float(dec), display_bad_mask=display_bad_mask,
                field_size_deg=comparison_size_deg,
            )
        _check_deadline(started, deadline_seconds)
        value = candidate_coadds[record]
        return value is not None and np.count_nonzero(np.isfinite(value.image_mjy_sr)) >= 10

    comparison_status = "single_epoch"
    comparison_reason = None
    class ComparisonBudgetReached(Exception):
        pass
    search_end = (time.monotonic() + .75 * max(0., deadline_at-time.monotonic())
                  if live_mode and deadline_at is not None else None)
    def comparison_deadline():
        _check_deadline(started, deadline_seconds)
        if search_end is not None and time.monotonic() >= search_end:
            raise ComparisonBudgetReached("Bounded comparison search ended; preserve time for an observed image")
    retrieval_rounds = []
    ranked_pairs = []

    def retrieve_pair():
        nonlocal selected_records, candidate_selection
        ranked_pairs.extend(ranked_candidate_pairs(epochs, selected_by_epoch_band, max_pairs=24,
                                                   check_deadline=comparison_deadline))
        selected_records = []
        candidate_selection = {}
        attempt_counts = defaultdict(int)
        last_error = None
        def fetch_and_match(needed, round_info, window_seconds):
            nonlocal last_error
            for record in needed:
                attempt_counts[record] += 1
                if record not in selected_records:
                    selected_records.append(record)
                    candidate_selection.setdefault((record_epochs[record], record.band), []).append(record)
            round_info["requested_uris"] = [record.uri for record in needed]
            round_options = {}
            if search_end is not None:
                round_options["allow_partial"] = True
                round_options["stage_deadline_at"] = min(search_end, time.monotonic() + window_seconds)
            try:
                downloaded = client.fetch_cutouts(needed, float(ra), float(dec), download_size_deg, **round_options)
                contents.update(downloaded)
                round_info["downloaded_uris"] = [record.uri for record in needed if record in downloaded]
            except IRSAUnavailable as exc:
                round_info["downloaded_uris"] = []
                round_info["download_error"] = str(exc)
            round_info["missing_uris"] = [record.uri for record in needed if record not in contents]
            retrieval_rounds.append(round_info)
            round_info["outcome"] = "comparison_budget_reached"
            comparison_deadline()
            if not contents:
                round_info["outcome"] = "no_completed_inputs"
                return None
            try:
                result = select_pair(epochs, candidate_selection, contents, float(ra), float(dec),
                                     comparison_size_deg, comparison_deadline, usable_candidate)
                round_info["outcome"] = "matched_visual"
                return result
            except IRSANoData as exc:
                last_error = exc
                round_info["outcome"] = "no_dense_usable_match"
                return None

        # Each small round contains both epochs of each proposed pair. A slow
        # earlier semester can no longer starve all later-epoch downloads.
        for offset in range(0, len(ranked_pairs), 2):
            comparison_deadline()
            proposals = ranked_pairs[offset:offset+2]
            needed = []
            for proposal in proposals:
                pair = (proposal["first"], proposal["second"])
                if any(record not in contents and attempt_counts[record] >= 2 for record in pair):
                    continue
                for record in pair:
                    if record not in contents and record not in needed:
                        needed.append(record)
            if not needed:
                continue
            result = fetch_and_match(needed, {"phase": "ranked_search", "rank_start": offset + 1}, 18.0)
            if result is not None:
                return result

        # A small inventory can exhaust its proposals after one round, leaving
        # complementary half-pairs despite substantial time remaining. Complete
        # at most two promising pairs once; never refetch successful bytes or
        # retry a fully downloaded pair that failed the measured science gates.
        completion = []
        completion_ranks = []
        for rank, proposal in enumerate(ranked_pairs, 1):
            comparison_deadline()
            pair = (proposal["first"], proposal["second"])
            missing = [record for record in pair if record not in contents]
            if len(missing) != 1 or attempt_counts[missing[0]] != 1:
                continue
            present = next(record for record in pair if record in contents)
            if not usable_candidate(present):
                continue
            if missing[0] not in completion:
                completion.append(missing[0])
                completion_ranks.append(rank)
            if len(completion) == 2:
                break
        if completion:
            comparison_deadline()
            result = fetch_and_match(completion, {"phase": "complete_incomplete_pairs",
                                                  "pair_ranks": completion_ranks}, 30.0)
            if result is not None:
                return result
        if not contents:
            raise IRSAUnavailable("No live comparison candidates could be downloaded within the bounded search.")
        if last_error is not None:
            raise last_error
        raise IRSANoData("No comparable pair was found in the bounded candidate search.",
                        detail={"reason": "NO_COMPARABLE_EPOCHS"})

    if len(epochs) > 1:
        try:
            epochs, selected_by_epoch_band = retrieve_pair() if comparison_first else select_pair(
                epochs, selected_by_epoch_band, contents, float(ra), float(dec),
                comparison_size_deg, comparison_deadline,
                usable_candidate,
            )
            comparison_status = "matched_visual"
        except (IRSANoData, ComparisonBudgetReached) as exc:
            missing_candidates = sum(record not in contents for record in selected_records)
            if not contents:
                raise IRSAUnavailable("No live cutouts completed before the comparison budget ended.") from exc
            if not allow_single_epoch and missing_candidates:
                raise IRSAUnavailable(
                    "Some candidate cutouts could not be downloaded and no comparable pair could be verified."
                ) from exc
            if not allow_single_epoch:
                raise
            # An observed image is useful even when a temporal comparison is not.
            # Keep the most recent usable real epoch; never manufacture a partner.
            chosen_single = {}
            for epoch in reversed(epochs):
                for band in range(1, 7):
                    for candidate in sorted(candidate_selection.get((epoch.epoch_id, band), []),
                                            key=lambda item: item.mjd_mid, reverse=True):
                        if candidate in contents and usable_candidate(candidate):
                            chosen_single[(epoch.epoch_id, band)] = [candidate]
                            break
                if chosen_single:
                    epochs = [epoch]
                    break
            if not chosen_single:
                raise NoUsablePixelsError("Downloaded observations contain no usable image band") from exc
            selected_by_epoch_band = compact_selection(epochs, chosen_single)
            comparison_status = "unmatched_single_epoch"
            comparison_reason = ("COMPARISON_SEARCH_BUDGET_REACHED" if isinstance(exc, ComparisonBudgetReached) else
                                 "PARTIAL_DOWNLOAD_NO_MATCHED_PAIR" if missing_candidates
                                 else "NO_MATCHED_PAIR_IN_BOUNDED_SAMPLE")
        comparison_note = (
            "Visual comparison: wavelengths agree within one quarter of the narrower "
            "bandwidth and bandwidths within 20% across the output field. "
            "WCS-WAVE is an approximate visualization lookup; this is not calibrated variability photometry."
        ) if comparison_status == "matched_visual" else None
    else:
        selected_by_epoch_band = compact_selection(epochs, selected_by_epoch_band)

    missing_candidates = sum(record not in contents for record in selected_records)

    coadds: dict[tuple[str, int], BandCoadd] = {}
    bands_by_epoch: dict[str, set[int]] = defaultdict(set)
    for (epoch_id, band), chosen in selected_by_epoch_band.items():
        _check_deadline(started, deadline_seconds)
        available = {record: contents[record] for record in chosen if record in contents}
        if not available:
            logger.warning("No downloaded cutouts for %s D%s", epoch_id, band)
            continue
        coadd = candidate_coadds[chosen[0]] if len(chosen) == 1 and chosen[0] in candidate_coadds else _coadd_band(
            epoch_id,
            band,
            chosen,
            available,
            out_wcs,
            float(ra),
            float(dec),
            display_bad_mask=display_bad_mask,
            field_size_deg=comparison_size_deg,
        )
        if coadd is None or np.count_nonzero(np.isfinite(coadd.image_mjy_sr)) < 10:
            continue
        coadds[(epoch_id, band)] = coadd
        bands_by_epoch[epoch_id].add(band)

    if not coadds:
        raise NoUsablePixelsError("No band coadds could be built")

    processed_epochs = [epoch for epoch in epochs if bands_by_epoch.get(epoch.epoch_id)]
    if not processed_epochs:
        raise NoUsablePixelsError("No epochs have usable data")

    if len(epochs) > 1:
        common_bands = set.intersection(*(bands_by_epoch[e.epoch_id] for e in epochs))
        if not common_bands or len(processed_epochs) != len(epochs):
            raise NoUsablePixelsError("The comparable epoch pair has no common usable image bands")
        coadds = {key: value for key, value in coadds.items() if key[1] in common_bands}
        bands_by_epoch = {e.epoch_id: set(common_bands) for e in epochs}

    if processed_epochs:
        # Keep full-set IDs while describing only exposures actually used in
        # the selected live product, not every discovered release in its bin.
        processed_epochs = [replace(epoch, records=tuple(
            record for band in sorted(bands_by_epoch[epoch.epoch_id])
            for record in selected_by_epoch_band[(epoch.epoch_id, band)]
            if record in contents
        )) for epoch in processed_epochs]

    candidates = _normalization_candidates(coadds)
    normalization = _compute_normalization(candidates, processed_epochs, bands_by_epoch)
    _apply_normalization(coadds, normalization)

    asset_dir = _asset_dir(asset_key)
    _check_deadline(started, deadline_seconds)
    asset_dir.mkdir(parents=True, exist_ok=True)
    epochs_payload = _build_epoch_payloads(
        processed_epochs,
        coadds,
        bands_by_epoch,
        normalization,
        candidates,
        asset_dir,
        asset_key=asset_key,
        halo_display_mode=bool(halo_display_mode),
        check_deadline=lambda: _check_deadline(started, deadline_seconds),
    )
    if not epochs_payload:
        raise NoUsablePixelsError("No epoch frames could be rendered")
    _check_deadline(started, deadline_seconds)
    if len(epochs_payload) != len(epochs):
        raise NoUsablePixelsError("Not all selected epochs could be rendered")
    if len(epochs_payload) > 1:
        rendered_bands = [{key for key in item["frames"] if key.isdigit()} for item in epochs_payload]
        if any(bands != rendered_bands[0] for bands in rendered_bands[1:]):
            raise NoUsablePixelsError("The epoch pair could not render identical band composition")
    if comparison_note:
        for epoch_payload in epochs_payload:
            summary = epoch_payload["flag_summary"]
            summary["human_explanation"] += " " + comparison_note
    differences = _build_differences(
        processed_epochs,
        coadds,
        bands_by_epoch,
        asset_dir,
        check_deadline=lambda: _check_deadline(started, deadline_seconds),
    )
    provenance = _top_level_provenance(epochs_payload, normalization)
    provenance.update(comparison_status=comparison_status, comparison_reason=comparison_reason)
    discovery = getattr(client, "discovery_metadata", {})
    provenance.update(discovery_status=discovery.get("status", "unknown"),
                      discovery_mode=discovery_mode,
                      missing_collections=discovery.get("missing_collections", []))
    halo_gate = resolve_halo_decision({"epochs": epochs_payload})
    manifest = {
        "version": CACHE_VERSION,
        "asset_key": asset_key,
        "query": {
            "ra": float(ra),
            "dec": float(dec),
            "cutout_size_deg": float(cutout_size_deg),
            "discovery_mode": discovery_mode,
        },
        "max_visits_per_band": visits,
        "max_epochs": max_epochs,
        "halo_display_mode": bool(halo_display_mode),
        "halo_gate": halo_gate.to_dict(),
        "generated_at": _now_utc().isoformat(),
        "available_epoch_ids": [epoch["epoch_id"] for epoch in epochs_payload],
        "discovered_epoch_ids": discovered_epoch_ids,
        "comparison_selection": {
            "status": comparison_status,
            "reason": comparison_reason,
            "validated_field_size_deg": comparison_size_deg,
            "validated_output_pixels": int(np.count_nonzero(field_pixel_mask(comparison_size_deg))),
            "method": "dense_output_field_wavelength_and_bandwidth" if comparison_note else "single_archive_epoch",
            "centre_tolerance_narrower_bandwidth_fraction": .25,
            "minimum_bandwidth_ratio": .8,
            "maximum_within_epoch_span_days": 30,
            "visits_per_band_epoch": 1,
            "science_calibration": "WCS-WAVE visual approximation; CWAVE/CBAND validation separate",
        },
        "live_selection": None if not live_mode else {
            "download_size_deg": download_size_deg,
            "missing_candidate_cutouts": missing_candidates,
            "candidate_epoch_ids": candidate_epoch_ids,
            "candidate_visits_per_band": max(3, visits) if len(candidate_epoch_ids) > 1 else 1,
            "method": "spectral_wcs_dense_field_quarter_bandwidth" if comparison_note else "single_archive_epoch",
            "exhaustive_visit_search": False,
            "acquisition_policy": "comparison_first_with_bounded_completion" if comparison_first else "single_epoch_sample",
            "completion_retry_pair_limit": 2 if comparison_first else None,
            "maximum_attempts_per_candidate": 2 if comparison_first else None,
            "completion_retry_window_seconds": 30 if comparison_first else None,
            "candidate_pair_limit": 24 if comparison_first else None,
            "candidate_pair_ranks": [{"rank": index + 1, "first_uri": pair["first"].uri,
                                      "second_uri": pair["second"].uri, "ranking_method": pair["method"],
                                      "corner_chord_distance": pair["corner_chord_distance"]}
                                     for index, pair in enumerate(ranked_pairs)],
            "retrieval_rounds": retrieval_rounds,
        },
        "epochs": epochs_payload,
        "differences": differences,
        "normalization": normalization,
        "provenance": provenance,
    }
    _check_deadline(started, deadline_seconds)
    record_images(
        manifest, contents, records, candidate_selection, selected_by_epoch_band,
        processed_epochs, coadds, ra=float(ra), dec=float(dec), download_size=download_size_deg,
        field_size=comparison_size_deg, halo_display_mode=bool(halo_display_mode),
        asset_dir=asset_dir, discovery=getattr(client, "discovery_metadata", None),
        acquisition=getattr(client, "acquisition_metadata", None),
    )
    _check_deadline(started, deadline_seconds)
    _write_manifest(manifest)
    return manifest


def replay_image_record(record: dict, inputs_by_sha256: dict[str, bytes], output_dir: Path) -> dict:
    """Recompute pinned selected images offline; never rediscover or publish a cache.

    Exact scientific-plane hashes are stricter than a summary-statistic match.
    This checks numerical replay in the recorded environment, not variability.
    The public replay CLI verifies input bytes, code and environment before
    calling this internal adapter; callers must preserve that trust boundary.
    """
    from services.provenance import validate_record, ProvenanceError
    from services.recording import image_method, science_planes, json_values, product_assets, freeze_product_assets
    validate_record(record)
    identity = record["identity"]
    query = identity["query"]
    method = identity["method"]
    size = method.get("field_size_deg")
    if not isinstance(size, (int, float)) or not 0 < size <= GRID_WIDTH * CDELT_DEG + 1e-8:
        raise ProvenanceError("Invalid retained image field size")
    if method != image_method(halo_display_mode=bool(method.get("halo_display_mode")), field_size_deg=size):
        raise ProvenanceError("Image replay method differs from the pinned method")
    ra, dec = float(query["ra"]), float(query["dec"])
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        raise ProvenanceError("Invalid image query coordinates")
    epochs = []
    for item in identity["selection"].get("selected_epochs", []):
        if not is_valid_filename(item["epoch_id"]):
            raise ProvenanceError("Unsafe epoch identifier")
        epochs.append(EpochBucket(**dict(item, records=tuple(ArtifactRecord(**r) for r in item["records"]))))
    if not epochs:
        raise ProvenanceError("Image record has no selected epochs")
    contents = {}
    for exposure in identity["exposures"]:
        if exposure.get("selected"):
            if exposure["extraction"] != {"ra": ra, "dec": dec}:
                raise ProvenanceError("Image extraction centre differs from the common grid")
            contents[ArtifactRecord(**exposure["artifact"])] = inputs_by_sha256[exposure["input_sha256"]]
    coadds = {}
    bands_by_epoch = {}
    grid = output_wcs(ra, dec)
    for epoch in epochs:
        if max(r.mjd_mid for r in epoch.records) - min(r.mjd_mid for r in epoch.records) > 30:
            raise ProvenanceError("Selected epoch exceeds the pinned temporal span")
        bands_by_epoch[epoch.epoch_id] = set()
        for band in sorted({r.band for r in epoch.records}):
            chosen = [r for r in epoch.records if r.band == band]
            if len(chosen) != 1 or any(r not in contents for r in chosen):
                raise ProvenanceError("Expected one retained exposure per band/epoch")
            coadd = _coadd_band(epoch.epoch_id, band, chosen, contents, grid, ra, dec,
                                display_bad_mask=method["display_bad_mask"], field_size_deg=size)
            if coadd is None:
                raise ProvenanceError("Pinned image no longer produces a usable coadd")
            coadds[(epoch.epoch_id, band)] = coadd
            bands_by_epoch[epoch.epoch_id].add(band)
    if len(epochs) > 1:
        from services.live_selection import dense_spectral_signature, compatible
        if len(epochs) != 2 or bands_by_epoch[epochs[0].epoch_id] != bands_by_epoch[epochs[1].epoch_id]:
            raise ProvenanceError("Recorded comparison has inconsistent band composition")
        for band in bands_by_epoch[epochs[0].epoch_id]:
            signatures = [dense_spectral_signature(contents[next(r for r in epoch.records if r.band == band)], ra, dec, size)
                          for epoch in epochs]
            if not compatible(*signatures):
                raise ProvenanceError("Pinned comparison fails dense wavelength/bandwidth matching")
    candidates = _normalization_candidates(coadds)
    normalization = _compute_normalization(candidates, epochs, bands_by_epoch)
    _apply_normalization(coadds, normalization)
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = _build_epoch_payloads(epochs, coadds, bands_by_epoch, normalization, candidates,
                                    output_dir, asset_key=str(query.get("asset_key") or "replay"),
                                    halo_display_mode=method["halo_display_mode"])
    differences = _build_differences(epochs, coadds, bands_by_epoch, output_dir)
    actual_planes = science_planes(coadds)
    expected = identity["outputs"]
    # Rendering hashes are reported separately; an encoding difference is not
    # disguised as a scientific measurement difference.
    rendered = {"epochs": payloads, "differences": differences}
    freeze_product_assets(rendered, output_dir)
    assets = product_assets(rendered, output_dir)
    result = {
        "numerical_match": actual_planes == expected.get("science_planes")
            and json_values(normalization) == expected.get("normalization"),
        "science_planes": actual_planes,
        "normalization": json_values(normalization),
        "artifact_hashes_match": assets == expected.get("assets"),
        "asset_hashes": assets,
        "selection_replay": "pinned_selected_inputs; dense_gate_rechecked; archive_discovery_not_requeried",
        "validation": "numerical_replay_only_not_independent_scientific_acceptance",
    }
    (output_dir / "image-results.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def cache_entry_count() -> int:
    """Number of cached live assets, used by ``/api/v1/health``."""
    root = settings.live_cache_dir
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())
