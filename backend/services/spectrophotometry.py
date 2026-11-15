"""Spectrophotometry for ``GET /api/v1/spectrum`` (B3).

Each selected SPHEREx visit contributes one spectral channel at the target's
extraction center.  The linear-variable filter makes the wavelength at a fixed
sky position change between visits/pointings, so a multi-visit epoch samples a
range of wavelengths.

Extraction follows ``AGENTS.md`` §3.5/§4.8 and ``docs/decisions/o1-contract-decisions.md``
§1:

* un-normalized, ZODI + local-background-subtracted frames;
* fixed 12.3\" (2.0 native-pixel) aperture, 3.0-5.0 native-pixel background
  annulus;
* ``WCS-WAVE`` (``key="W"``, ``sip=None``) at the extraction center;
* ``flags`` at the center, hard-bad only for ``is_flagged_bad``;
* clean-pixel flux and variance, ``clean_fraction`` and
  ``is_used_in_photometry``;
* ``null`` flux/error when no clean aperture pixels remain.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import replace, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from astropy.time import Time

from core import flags as flag_policy
from core.config import settings
from core.targets import TargetRecord, propagated_coordinates
from services.irsa_client import (
    DEFAULT_SIA_COLLECTIONS,
    ArtifactRecord,
    IRSANoData,
    IRSAUnavailable,
    IrsaClient,
)
from services.spherex_pipeline import (
    EpochBucket,
    NoUsablePixelsError,
    _select_visits,
    epoch_collection_release,
    group_epochs,
    mixed_release_label,
    parse_cutout,
    source_label,
)
from services.singleflight import run_once
from services.build_limits import live_build_slot
from services.product_metadata import observation_range, observation_label, measurement_availability
from services.recording import discovery_identity, retain_inputs, unique_inputs, publish_record, json_values
from services import provenance as lineage

APERTURE_RADIUS_ARCSEC = 12.3
ANNULUS_INNER_PIXELS = 3.0
ANNULUS_OUTER_PIXELS = 5.0
WAVELENGTH_CALIBRATION = "WCS-WAVE (sip=None; approximate visualization lookup, not CWAVE/CBAND science calibration)"
SPECTRUM_CACHE_VERSION = 6
SPECTRUM_CUTOUT_SIZE_DEG = 0.2

ARCSEC_TO_RAD = math.pi / (180.0 * 3600.0)

MOLECULAR_FEATURES: tuple[dict[str, Any], ...] = (
    {"label": "H2O", "wavelength_um": 1.40, "band": 2},
    {"label": "CH4", "wavelength_um": 1.65, "band": 3},
    {"label": "H2O / CO", "wavelength_um": 2.35, "band": 3},
    {"label": "H2O Ice", "wavelength_um": 3.08, "band": 4},
    {"label": "CH4 Fundamental", "wavelength_um": 3.32, "band": 4},
    {"label": "CO2 Ice", "wavelength_um": 4.27, "band": 5},
    {"label": "CO Fundamental", "wavelength_um": 4.67, "band": 6},
)


def spectrum_asset_key(ra: float, dec: float, *, target_id: str | None = None,
                       discovery_mode: str = "live") -> str:
    """Stable server-side cache key for an arbitrary-coordinate spectrum."""
    if discovery_mode not in {"live", "known"}:
        raise ValueError("Unknown discovery mode")
    query = f"native_spectrum|{target_id}|{float(ra):.10f}_{float(dec):.10f}"
    if discovery_mode == "known":
        query += "|discovery_known"
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    return f"live_{digest[:16]}"


def _spectrum_path(asset_key: str) -> Path:
    return settings.live_cache_dir / asset_key / "spectrum.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _check_deadline(started: float, deadline_seconds: float | None) -> None:
    if deadline_seconds is None:
        return
    if (time.monotonic() - started) > float(deadline_seconds):
        raise IRSAUnavailable(
            "Live spectrum build exceeded the server time budget; "
            "try a precomputed target or retry."
        )


def extract_channel(parsed, detector: int, *, diagnostics: dict | None = None) -> dict[str, Any] | None:
    """Extract one spectral channel from a prepared cutout.

    The extraction center is the native pixel at the target coordinate in this
    exposure; the wavelength/bandwidth come from the WCS-WAVE lookup at that
    center.  The flux is the sum of clean aperture pixels after subtracting
    the median of the 3-5 native-pixel background annulus.
    """
    def omitted(reason: str) -> None:
        # An absent channel is different from a present channel with null flux.
        # Retain the reason internally even though no public channel is emitted.
        if diagnostics is not None:
            diagnostics["omission_reason"] = reason
        return None

    wavelength = parsed.spectral_wavelength_um
    bandwidth = parsed.spectral_bandwidth_um
    if wavelength is None or bandwidth is None:
        return omitted("MISSING_SPECTRAL_COORDINATES")
    if not (math.isfinite(float(wavelength)) and float(wavelength) > 0.0):
        return omitted("INVALID_WAVELENGTH")
    if not (math.isfinite(float(bandwidth)) and float(bandwidth) > 0.0):
        return omitted("INVALID_BANDWIDTH")

    flags = parsed.flags
    ny, nx = flags.shape
    center_x = int(round(parsed.target_x))
    center_y = int(round(parsed.target_y))
    if not (0 <= center_x < nx and 0 <= center_y < ny):
        return omitted("EXTRACTION_CENTRE_OUTSIDE_NATIVE_IMAGE")
    center_flags = int(flags[center_y, center_x])

    yy, xx = np.indices(flags.shape)
    radius_pixels = APERTURE_RADIUS_ARCSEC / max(
        parsed.native_pixel_scale_arcsec, 1e-6
    )
    distance = np.hypot(xx - parsed.target_x, yy - parsed.target_y)
    aperture = distance <= radius_pixels
    aperture_count = int(np.count_nonzero(aperture))
    if aperture_count == 0:
        return omitted("NO_NATIVE_APERTURE_PIXELS")

    excluded = (flags & flag_policy.PHOTOMETRY_EXCLUDE_MASK) != 0
    finite = (
        np.isfinite(parsed.image_mjy_sr)
        & np.isfinite(parsed.variance_mjy_sr2)
        & (parsed.variance_mjy_sr2 > 0)
    )
    clean = aperture & ~excluded & finite
    background_metadata = getattr(parsed, "background_metadata", None)
    background_ok = background_metadata is None or background_metadata.get("subtracted", False)
    clean_count = int(np.count_nonzero(clean))
    clean_fraction = clean_count / aperture_count
    aperture_inside = (
        parsed.target_x - radius_pixels >= -0.5
        and parsed.target_x + radius_pixels <= nx - 0.5
        and parsed.target_y - radius_pixels >= -0.5
        and parsed.target_y + radius_pixels <= ny - 0.5
    )

    flux_ujy: float | None = None
    flux_err_ujy: float | None = None
    annulus_count = 0
    background_variance = None
    annulus_background = None
    if clean_count > 0 and background_ok:
        annulus = (distance >= ANNULUS_INNER_PIXELS) & (
            distance <= ANNULUS_OUTER_PIXELS
        )
        annulus_clean = (
            annulus
            & ~excluded
            & ((flags & flag_policy.BIT_SOURCE) == 0)
            & finite
        )
        annulus_count = int(np.count_nonzero(annulus_clean))
        if annulus_count >= 10:
            annulus_background = float(
                np.nanmedian(parsed.image_mjy_sr[annulus_clean])
            )
            scatter = 1.4826 * float(np.median(np.abs(parsed.image_mjy_sr[annulus_clean] - annulus_background)))
            background_variance = max(
                (math.pi / 2) * float(np.mean(parsed.variance_mjy_sr2[annulus_clean])) / annulus_count,
                1.2533**2 * scatter**2 / annulus_count,
            )
        else:
            # The pipeline already subtracted a cutout-wide local background.
            annulus_background = 0.0
            metadata = background_metadata or {}
            background_variance = (
                1.2533**2 * float(metadata.get("robust_scatter_mjy_sr", 0.0))**2
                / max(1, int(metadata.get("clean_pixels", 1)))
            )
        omega_sr = (
            parsed.native_pixel_scale_arcsec * ARCSEC_TO_RAD
        ) ** 2
        flux_ujy = float(
            np.nansum(parsed.image_mjy_sr[clean] - annulus_background)
            * omega_sr
            * 1e12
        )
        variance_sum = float(np.nansum(parsed.variance_mjy_sr2[clean]))
        # The shared median-background error affects every aperture pixel.
        # Correlated detector noise / fitted-plane covariance remain approximate.
        variance_sum += clean_count**2 * background_variance
        flux_err_ujy = float(math.sqrt(max(variance_sum, 0.0)) * omega_sr * 1e12)

    is_flagged_bad = bool(center_flags & flag_policy.HARD_BAD_MASK)
    # A finite partial sum is useful for inspection, but is not a supported
    # full-aperture measurement. Never rescale missing area into invented flux.
    is_used = bool(clean_count == aperture_count and aperture_inside
                   and annulus_count >= 10 and not is_flagged_bad and background_ok)
    reasons = []
    if not aperture_inside:
        reasons.append("APERTURE_OUTSIDE_NATIVE_IMAGE")
    if not background_ok:
        reasons.append("UNSUPPORTED_BACKGROUND")
    if clean_count == 0:
        reasons.append("NO_CLEAN_APERTURE_PIXELS")
    elif clean_fraction < 0.5:
        reasons.append("INSUFFICIENT_CLEAN_APERTURE")
    elif clean_fraction < 1:
        reasons.append("PARTIAL_CLEAN_APERTURE")
    if is_flagged_bad:
        reasons.append("HARD_BAD_EXTRACTION_CENTRE")
    if clean_count > 0 and background_ok and annulus_count < 10:
        reasons.append("FIELD_BACKGROUND_FALLBACK")
    if diagnostics is not None:
        diagnostics.update({
            "aperture_pixels": aperture_count, "clean_pixels": clean_count,
            "annulus_clean_pixels": annulus_count,
            "annulus_evaluated": bool(clean_count > 0 and background_ok),
            "aperture_inside_native_image": bool(aperture_inside),
            "annulus_background_mjy_sr": annulus_background,
            "background_variance_mjy_sr2": background_variance,
            "background": background_metadata,
            "native_pixel_scale_arcsec": parsed.native_pixel_scale_arcsec,
            "target_x": parsed.target_x, "target_y": parsed.target_y,
            "aperture_method": "centre_pixel_12.3_arcsec",
        })

    return {
        "detector": int(detector),
        "wavelength_um": float(wavelength),
        "bandwidth_um": float(bandwidth),
        "flux_ujy": flux_ujy,
        "flux_err_ujy": flux_err_ujy,
        "flags": int(center_flags),
        "is_flagged_bad": is_flagged_bad,
        "clean_fraction": float(min(1.0, max(0.0, clean_fraction))),
        "is_used_in_photometry": is_used,
        "measurement_reasons": reasons,
    }


def _spectrum_provenance(epochs: list[EpochBucket]) -> dict[str, Any]:
    releases = {
        epoch_collection_release(epoch)[1]
        for epoch in epochs
        if epoch_collection_release(epoch)[1] != "unknown"
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
        "background_subtracted": True,
        "is_simulated_fallback": False,
        "citation": "SPHEREx Quick Release (JPL/Caltech/IRSA)",
    }


def _load_cached_spectrum(
    asset_key: str,
    ra: float,
    dec: float,
    max_visits_per_band: int,
    confidence: str,
    max_epochs: int | None = None,
) -> dict[str, Any] | None:
    path = _spectrum_path(asset_key)
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
    if payload.get("version") != SPECTRUM_CACHE_VERSION:
        return None
    query = payload.get("query") or {}
    if abs(float(query.get("ra", -999.0)) - float(ra)) > 1e-6:
        return None
    if abs(float(query.get("dec", -999.0)) - float(dec)) > 1e-6:
        return None
    if int(payload.get("max_visits_per_band", -1)) != int(max_visits_per_band):
        return None
    if payload.get("max_epochs") != max_epochs:
        return None
    if str(payload.get("confidence", "")) != str(confidence):
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
    return payload


def _write_spectrum(asset_key: str, payload: dict[str, Any]) -> None:
    path = _spectrum_path(asset_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build_spectrum(
    asset_key: str,
    ra: float,
    dec: float,
    *,
    confidence: str,
    max_visits_per_band: int,
    max_epochs: int | None = None,
    target_record: TargetRecord | None = None,
    live_mode: bool = False,
    deadline_seconds: float | None = None,
    force_refresh: bool = False,
    discovery_mode: str = "live",
) -> dict[str, Any]:
    """Share concurrent extraction for the same field and extraction profile."""
    deadline_at = None if deadline_seconds is None else time.monotonic() + deadline_seconds
    if live_mode:
        max_epochs = max(2, int(max_epochs or settings.live_sky_max_epochs))
    key = ("spectrum", asset_key, ra, dec, confidence, max_visits_per_band,
           max_epochs, repr(target_record), live_mode, force_refresh, discovery_mode)
    return run_once(key, deadline_at, lambda: _build_spectrum(
        asset_key, ra, dec, confidence=confidence,
        max_visits_per_band=max_visits_per_band, max_epochs=max_epochs,
        target_record=target_record, live_mode=live_mode,
        deadline_seconds=None if deadline_at is None else max(0.0, deadline_at - time.monotonic()),
        force_refresh=force_refresh,
        discovery_mode=discovery_mode,
    ), admission=(lambda: live_build_slot(settings)) if live_mode else None)


def _build_spectrum(
    asset_key: str, ra: float, dec: float, *, confidence: str,
    max_visits_per_band: int, max_epochs: int | None = None,
    target_record: TargetRecord | None = None, live_mode: bool = False,
    deadline_seconds: float | None = None, force_refresh: bool = False,
    archive_client: IrsaClient | None = None,
    discovery_mode: str = "live",
) -> dict[str, Any]:
    """Build (or load) the multi-epoch spectrum cache for a position.

    For catalog targets the extraction center in each visit is the propagated
    target coordinate at that visit's MJD (O1 §1); the cutout itself remains
    centered on the 2025.8 query position per LAW 5.

    Live discovery, fallback, downloads and extraction share one deadline;
    ``max_epochs`` limits the build to the latest N full-set epochs.
    """
    if discovery_mode not in {"live", "known"}:
        raise ValueError("Unknown discovery mode")
    if discovery_mode == "known":
        if not live_mode or target_record is None:
            raise ValueError("Known discovery requires an explicit live catalog request")
        force_refresh = True
    visits = max(1, int(max_visits_per_band))
    if not force_refresh:
        cached = _load_cached_spectrum(
            asset_key,
            float(ra),
            float(dec),
            visits,
            confidence,
            max_epochs,
        )
        if cached is not None:
            return cached

    started = time.monotonic()
    deadline_at = None if deadline_seconds is None else started + deadline_seconds
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
        client = KnownExposureClient(client.settings, target_id=target_record.id, deadline_at=deadline_at)
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
    _check_deadline(started, deadline_seconds)

    selected_by_epoch_band: dict[tuple[str, int], list[ArtifactRecord]] = {}
    selected_records: list[ArtifactRecord] = []
    for epoch in epochs:
        for band in range(1, 7):
            band_records = [record for record in epoch.records if record.band == band]
            if not band_records:
                continue
            chosen = _select_visits(band_records, visits)
            selected_by_epoch_band[(epoch.epoch_id, band)] = chosen
            selected_records.extend(chosen)

    if not selected_records:
        raise IRSANoData(
            "No SPHEREx science artifacts matched the requested bands.",
            collections_tried=sorted({record.collection for record in records}),
            detail={"ra": float(ra), "dec": float(dec)},
        )

    download_options = {}
    if live_mode and deadline_at is not None:
        download_options = {"stage_deadline_at": time.monotonic() + .65 * max(0., deadline_at-time.monotonic()),
                            "allow_partial": True}
    contents = client.fetch_cutouts(
        selected_records,
        float(ra),
        float(dec),
        SPECTRUM_CUTOUT_SIZE_DEG,
        **download_options,
    )
    _check_deadline(started, deadline_seconds)
    if not contents:
        if live_mode:
            raise IRSAUnavailable("No live spectrum cutouts could be downloaded.")
        raise NoUsablePixelsError("No cutouts could be downloaded for the spectrum")

    epoch_payloads: list[dict[str, Any]] = []
    descriptors = retain_inputs(contents, float(ra), float(dec), SPECTRUM_CUTOUT_SIZE_DEG,
                                acquisition=getattr(client, "acquisition_metadata", None))
    exposure_lineage = []
    contributing_epochs: list[EpochBucket] = []
    background_estimates = []
    for epoch in epochs:
        channels: list[dict[str, Any]] = []
        contributing_records: list[ArtifactRecord] = []
        for band in range(1, 7):
            for record in selected_by_epoch_band.get((epoch.epoch_id, band), []):
                _check_deadline(started, deadline_seconds)
                content = contents.get(record)
                if content is None:
                    continue
                visit_ra, visit_dec = float(ra), float(dec)
                if target_record is not None:
                    visit_coord = propagated_coordinates(
                        target_record, obstime=Time(record.mjd_mid, format="mjd", scale="utc")
                    )
                    visit_ra = float(visit_coord.ra.deg)
                    visit_dec = float(visit_coord.dec.deg)
                parsed = parse_cutout(content, visit_ra, visit_dec)
                diagnostics = {}
                channel = extract_channel(parsed, band, diagnostics=diagnostics)
                exposure_lineage.append({
                    "input_sha256": descriptors[record]["sha256"],
                    "epoch_id": epoch.epoch_id, "detector": band,
                    "artifact": asdict(record), "extraction": {"ra": visit_ra, "dec": visit_dec},
                    "expected_channel": dict(channel) if channel is not None else None,
                    "diagnostics": json_values(diagnostics),
                })
                if channel is not None:
                    channel.update({"input_id": descriptors[record]["sha256"],
                                    "extraction_ra": visit_ra, "extraction_dec": visit_dec})
                    channels.append(channel)
                    contributing_records.append(record)
                    background_estimates.append(parsed.background_metadata or {"subtracted": False})
        if not channels:
            continue
        channels.sort(key=lambda item: (item["wavelength_um"], item["detector"]))
        contributing_epoch = replace(epoch, records=tuple(contributing_records))
        contributing_epochs.append(contributing_epoch)
        collection, release = epoch_collection_release(contributing_epoch)
        epoch_payloads.append(
            {
                "epoch_id": epoch.epoch_id,
                "label": observation_label(observation_range(contributing_records), epoch.label),
                "observation_range": observation_range(contributing_records),
                "measurement_availability": measurement_availability(channels),
                "collection": collection,
                "release": release,
                "channels": channels,
            }
        )

    _check_deadline(started, deadline_seconds)
    if not epoch_payloads:
        raise NoUsablePixelsError(
            "No spectral channels could be extracted for this position"
        )

    payload = {
        "version": SPECTRUM_CACHE_VERSION,
        "asset_key": asset_key,
        "query": {"ra": float(ra), "dec": float(dec)},
        "max_visits_per_band": visits,
        "max_epochs": max_epochs,
        "confidence": str(confidence),
        "generated_at": _now_utc().isoformat(),
        "available_epoch_ids": [epoch["epoch_id"] for epoch in epoch_payloads],
        "discovered_epoch_ids": discovered_epoch_ids,
        "epochs": epoch_payloads,
        "provenance": _spectrum_provenance(contributing_epochs),
        "background_estimates": background_estimates,
        "uncertainty_method": "native_pixel_variance_plus_approximate_median_background; covariance_not_calibrated",
    }
    payload["provenance"]["background_subtracted"] = all(item.get("subtracted", False) for item in background_estimates)
    discovery = getattr(client, "discovery_metadata", {})
    payload["provenance"].update(discovery_status=discovery.get("status", "unknown"),
                                 discovery_mode=discovery_mode,
                                 missing_collections=discovery.get("missing_collections", []))
    payload["query"]["discovery_mode"] = discovery_mode
    record = lineage.make_record(
        kind="spectrum", query=dict(payload["query"]), inputs=unique_inputs(descriptors),
        exposures=exposure_lineage, method=lineage.native_method(),
        selection=json_values({
            "scope": discovery_identity(
                getattr(client, "discovery_metadata", {"source": "query_artifacts_returned_records", "raw_query_response_retained": False})),
            "discovered_records": [asdict(item) for item in records],
            "selected_records": [asdict(item) for item in selected_records],
            "missing_downloads": [asdict(item) for item in selected_records if item not in contents],
            "target_astrometry": asdict(target_record) if target_record is not None else None,
            "max_visits_per_band": visits, "max_epochs": max_epochs,
            "observation_mjd_scale": "utc", "image_pair_relationship": "independent_native_visit_selection",
        }),
        outputs={"epochs": json_values(epoch_payloads)}, created_at=payload["generated_at"],
        acquisition=json_values({"discovery": getattr(client, "discovery_metadata", None),
                                 "cutouts": getattr(client, "acquisition_metadata", None)}),
    )
    publish_record(_spectrum_path(asset_key).parent, payload, record, "spectrum_analysis.json")
    _write_spectrum(asset_key, payload)
    return payload
