"""GET /api/v1/sky: fresh archive by default, explicit saved or known-index modes.

Known discovery uses a bounded historical catalog exposure list and newly
downloaded FITS. It never activates automatically after a live search failure.
Saved mode alone serves historical golden products with their recorded HALO policy.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Query, Response
from typing import Annotated
from models import (
    Epoch,
    FlagStatus,
    FlagSummary,
    FluxNormalization,
    LVFGeometry,
    SkyProvenance,
    SkyQuery,
    SkyQueryInfo,
    SkyResponse,
    TelemetryAsset,
)
from models.sky import WCS as SkyWCS

from app.errors import ApiError
from core.source_policy import source_target
from core.cachekeys import is_valid_filename, live_asset_key
from core.config import settings
from core.targets import TargetRecord, angular_separation_arcsec, get_target
from services.golden_cache import REFERENCE_OVERLAY_METADATA_KEYS, load_golden_manifest
from services.halo import HaloDecision, apply_halo_to_summary, resolve_halo_decision
from services.product_metadata import creation_time
from services.irsa_client import IRSANoData, IRSAError, IRSAUnavailable
from services.spherex_pipeline import (
    CDELT_DEG,
    GRID_HEIGHT,
    GRID_WIDTH,
    NATIVE_PIXEL_SCALE_ARCSEC,
    PIXEL_SCALE_ARCSEC,
    NoUsablePixelsError,
    PipelineError,
    build_manifest,
    load_cached_manifest_any_mode,
)

router = APIRouter(tags=["sky"])

logger = logging.getLogger(__name__)

TARGET_MATCH_TOLERANCE_ARCSEC = 1.0
CATALOG_CUTOUT_SIZE_DEG = 0.2


def _resolve_query(
    query: SkyQuery,
) -> tuple[float, float, str, float, int, TargetRecord | None]:
    """Return (center_ra, center_dec, asset_key, cutout_size, visits, target)."""
    if query.target_id is not None:
        target = source_target(query.target_id, query.source)
        if target is None:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                f"Unknown target id {query.target_id!r}.",
                {"target_id": query.target_id},
            )
        separation = angular_separation_arcsec(
            query.ra,
            query.dec,
            target.ra_epoch2025,
            target.dec_epoch2025,
        )
        if separation > TARGET_MATCH_TOLERANCE_ARCSEC:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "ra/dec must be within 1.0 arcsec of the target's 2025.8 position.",
                {
                    "target_id": query.target_id,
                    "separation_arcsec": separation,
                    "ra_epoch2025": target.ra_epoch2025,
                    "dec_epoch2025": target.dec_epoch2025,
                },
            )
        return (
            target.ra_epoch2025,
            target.dec_epoch2025,
            target.id,
            CATALOG_CUTOUT_SIZE_DEG,
            settings.max_visits_per_band,
            target,
        )

    asset_key = live_asset_key(
        query.ra,
        query.dec,
        query.size,
        bands=query.bands,
        epochs=query.epochs,
        include_diff=query.include_diff,
    )
    return query.ra, query.dec, asset_key, query.size, 1, None


def _filter_bands(frames: dict[str, str], bands: str) -> dict[str, str]:
    """Filter only numeric band keys; keep all/thermal/flag_overlay."""
    if bands == "all":
        return dict(frames)
    requested = {int(part) for part in bands.split(",") if part.strip()}
    return {
        key: value
        for key, value in frames.items()
        if not key.isdigit() or int(key) in requested
    }


def _asset_url(asset_key: str, filename: str) -> str:
    if filename.startswith(("http://", "https://", "/")):
        return filename
    return f"/api/v1/assets/{asset_key}/{filename}"


def _telemetry_path(asset_key: str, filename: str, byte_size: int):
    """Resolve the sidecar that ``/assets`` will actually serve.

    The assets route serves the golden cache first, so a same-named golden file
    must match the manifest exactly; only when it is absent is the live cache
    considered.
    """
    golden = settings.golden_cache_dir / asset_key / filename
    if golden.is_file():
        if golden.stat().st_size == int(byte_size):
            return golden
        return None
    live = settings.live_cache_dir / asset_key / filename
    if live.is_file() and live.stat().st_size == int(byte_size):
        return live
    return None


def _telemetry_asset(asset_key: str, payload: object) -> TelemetryAsset | None:
    """Validate a manifest ``epochs[].telemetry`` block and build the contract.

    Old 1.0.0 manifests have no block and keep ``telemetry=None``.  A block
    that references a missing or wrong-sized sidecar is dropped (and logged)
    rather than served as a broken URL.
    """
    if not isinstance(payload, dict):
        return None
    filename = payload.get("url")
    if not isinstance(filename, str) or not filename:
        logger.warning("Ignoring telemetry block without a URL for %s", asset_key)
        return None
    if filename.startswith(("http://", "https://", "/")):
        url = filename
    else:
        if not is_valid_filename(filename):
            logger.warning("Ignoring unsafe telemetry filename %r", filename)
            return None
        try:
            declared = int(payload["byte_size"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Telemetry block for %s has no valid byte_size", filename)
            return None
        path = _telemetry_path(asset_key, filename, declared)
        if path is None:
            logger.warning(
                "Telemetry sidecar %s/%s is missing or not %d bytes",
                asset_key,
                filename,
                declared,
            )
            return None
        url = _asset_url(asset_key, filename)
    try:
        return TelemetryAsset(
            url=url,
            format=str(payload["format"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
            byte_size=int(payload["byte_size"]),
            flux_band=str(payload.get("flux_band", "all")),
            quantity=payload.get("quantity"),
            normalization_applied=payload.get("normalization_applied"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Ignoring invalid telemetry block for %s: %s", asset_key, exc)
        return None


def _lvf_geometry(payload: object) -> list[LVFGeometry] | None:
    """Validate the optional per-detector LVF geometry; omit bad entries."""
    if not isinstance(payload, list):
        return None
    geometry: list[LVFGeometry] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        try:
            item = LVFGeometry(
                detector=int(entry["detector"]),
                pa_deg=float(entry["pa_deg"]),
                grad_um_per_arcsec=float(entry["grad_um_per_arcsec"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        geometry.append(item)
    return geometry or None


def _selected_epoch_ids(query: SkyQuery, manifest: dict) -> list[str] | None:
    built = [str(epoch_id) for epoch_id in manifest.get("available_epoch_ids", [])]
    discovered = [
        str(epoch_id)
        for epoch_id in (
            manifest.get("discovered_epoch_ids")
            or manifest.get("available_epoch_ids", [])
        )
    ]
    if query.epochs == "all":
        return None
    requested = [part for part in query.epochs.split(",") if part]
    unknown = sorted(set(requested) - set(discovered))
    if unknown:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Unknown epoch id(s) for this position.",
            {"unknown_epochs": unknown, "available_epochs": built},
        )
    requested_set = set(requested)
    return [epoch_id for epoch_id in built if epoch_id in requested_set]


def _build_response(
    query: SkyQuery,
    manifest: dict,
    center_ra: float,
    center_dec: float,
    asset_key: str,
    halo_decision: HaloDecision | None = None,
) -> SkyResponse:
    target = source_target(query.target_id, query.source) if query.target_id is not None else None
    selected_epochs = _selected_epoch_ids(query, manifest)

    epochs: list[Epoch] = []
    included_epoch_ids: set[str] = set()
    for epoch_payload in manifest.get("epochs", []):
        epoch_id = str(epoch_payload["epoch_id"])
        if selected_epochs is not None and epoch_id not in selected_epochs:
            continue
        included_epoch_ids.add(epoch_id)
        frames = {
            key: _asset_url(asset_key, str(filename))
            for key, filename in epoch_payload.get("frames", {}).items()
        }
        frames = _filter_bands(frames, query.bands)
        summary = apply_halo_to_summary(
            epoch_payload["flag_summary"],
            halo_decision,
        )
        epochs.append(
            Epoch(
                epoch_id=epoch_id,
                label=str(epoch_payload["label"]),
                collection=str(epoch_payload["collection"]),
                release=str(epoch_payload["release"]),
                mjd_mean=float(epoch_payload["mjd_mean"]),
                date_iso=date.fromisoformat(str(epoch_payload["date_iso"])),
                frames=frames,
                flag_summary=FlagSummary(
                    status=FlagStatus(str(summary["status"])),
                    source_bit_set=bool(summary["source_bit_set"]),
                    artifact_pixel_fraction=float(
                        summary["artifact_pixel_fraction"]
                    ),
                    active_warning_flags=list(summary["active_warning_flags"]),
                    human_explanation=str(summary["human_explanation"]) + (
                        " Saved visual comparison predates the Phase 3 wavelength, background and measurement-mask audit; astrophysical variability is not validated."
                        if not manifest.get("comparison_selection") else ""
                    ),
                ),
                telemetry=_telemetry_asset(
                    asset_key, epoch_payload.get("telemetry")
                ),
                lvf_geometry=_lvf_geometry(epoch_payload.get("lvf_geometry")),
                observation_range=epoch_payload.get("observation_range"),
            )
        )

    differences: dict[str, dict[str, str]] = {}
    if query.include_diff and len(included_epoch_ids) >= 2:
        for pair_key, pair in manifest.get("differences", {}).items():
            try:
                later_id, earlier_id = str(pair_key).split("_minus_", 1)
            except ValueError:
                continue
            if later_id not in included_epoch_ids or earlier_id not in included_epoch_ids:
                continue
            frames = {
                key: _asset_url(asset_key, str(filename))
                for key, filename in pair.get("frames", {}).items()
            }
            filtered = _filter_bands(frames, query.bands)
            if filtered:
                differences[str(pair_key)] = filtered

    reference_overlays: dict[str, str] = {}
    for key, filename in (manifest.get("reference_overlays") or {}).items():
        if not isinstance(filename, str) or not filename:
            continue
        if str(key) in REFERENCE_OVERLAY_METADATA_KEYS:
            # Human-readable metadata (the attribution prose), not an asset
            # URL.  Preserve the string exactly as stored; it may legitimately
            # start with "/" or be clean prose.
            reference_overlays[str(key)] = filename
            continue
        reference_overlays[str(key)] = _asset_url(asset_key, filename)

    provenance_payload = manifest["provenance"]
    normalization_payload = provenance_payload["flux_normalization"]
    provenance = SkyProvenance(
        source=str(provenance_payload["source"]),
        collection=str(provenance_payload["collection"]),
        release=str(provenance_payload["release"]),
        zodi_subtracted=bool(provenance_payload["zodi_subtracted"]),
        background_subtracted=bool(provenance_payload["background_subtracted"]),
        flux_normalization=FluxNormalization(**normalization_payload),
        is_simulated_fallback=bool(provenance_payload["is_simulated_fallback"]),
        generated_at=creation_time(manifest),
        citation=str(provenance_payload["citation"]),
        analysis_id=provenance_payload.get("analysis_id"),
        analysis_record_url=provenance_payload.get("analysis_record_url"),
        processing_version=provenance_payload.get("processing_version"),
        data_access=query.source,
        discovery_mode=query.discovery if query.source == "archive" else None,
        comparison_status=("legacy_unvalidated" if query.source == "saved" else provenance_payload.get("comparison_status")),
        comparison_reason=provenance_payload.get("comparison_reason"),
        discovery_status=provenance_payload.get("discovery_status", "unknown"),
        missing_collections=provenance_payload.get("missing_collections", []),
    )

    wcs = SkyWCS(
        crval1=center_ra,
        crval2=center_dec,
        crpix1=(GRID_WIDTH + 1) / 2.0,
        crpix2=(GRID_HEIGHT + 1) / 2.0,
        cdelt1=-CDELT_DEG,
        cdelt2=CDELT_DEG,
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        pixel_scale_arcsec=PIXEL_SCALE_ARCSEC,
        native_pixel_scale_arcsec=NATIVE_PIXEL_SCALE_ARCSEC,
    )

    return SkyResponse(
        query=SkyQueryInfo(
            ra=center_ra,
            dec=center_dec,
            size_deg=query.size,
            target_id=query.target_id,
        ),
        target=target.to_contract() if target is not None else None,
        wcs=wcs,
        epochs=epochs,
        differences=differences,
        reference_overlays=reference_overlays,
        provenance=provenance,
    )


def _live_manifest(
    asset_key: str,
    center_ra: float,
    center_dec: float,
    cutout_size: float,
    max_visits: int,
    target_record: TargetRecord | None,
    *,
    max_epochs: int | None,
    deadline_seconds: float | None,
    live_mode: bool,
) -> tuple[dict, HaloDecision]:
    """Build the live manifest and apply the catalog HALO gate if needed."""
    if target_record is not None:
        # Reuse an existing live cache regardless of its HALO mode so a HALO-
        # display build is not re-done as hard-masked on every request.
        cached = load_cached_manifest_any_mode(
            asset_key,
            center_ra,
            center_dec,
            cutout_size,
            max_visits,
            max_epochs,
        )
        if cached is not None:
            if bool(cached.get("halo_display_mode")):
                return cached, resolve_halo_decision(cached)
            gate_decision = resolve_halo_decision(
                {"epochs": cached.get("epochs", [])}
            )
            if gate_decision.triggered:
                manifest = build_manifest(
                    asset_key,
                    center_ra,
                    center_dec,
                    cutout_size_deg=cutout_size,
                    max_visits_per_band=max_visits,
                    max_epochs=max_epochs,
                    halo_display_mode=True,
                    live_mode=live_mode,
                    deadline_seconds=deadline_seconds,
                    force_refresh=True,
                )
                return manifest, resolve_halo_decision(manifest)
            return cached, resolve_halo_decision(cached)

    manifest = build_manifest(
        asset_key,
        center_ra,
        center_dec,
        cutout_size_deg=cutout_size,
        max_visits_per_band=max_visits,
        max_epochs=max_epochs,
        live_mode=live_mode,
        deadline_seconds=deadline_seconds,
    )
    if target_record is None:
        # Arbitrary positions have no per-target display-only decision.
        decision = resolve_halo_decision(manifest, evaluate_gate=False)
        return manifest, decision

    # Evaluate the O1 gate from the epoch statistics, not from the manifest's
    # explicit build flag (a live fallback was initially built with HALO hard).
    gate_decision = resolve_halo_decision({"epochs": manifest.get("epochs", [])})
    if gate_decision.triggered and not bool(manifest.get("halo_display_mode")):
        # The live build used the hard mask; rebuild with HALO displayed.
        manifest = build_manifest(
            asset_key,
            center_ra,
            center_dec,
            cutout_size_deg=cutout_size,
            max_visits_per_band=max_visits,
            max_epochs=max_epochs,
            halo_display_mode=True,
            live_mode=live_mode,
            deadline_seconds=deadline_seconds,
            force_refresh=True,
        )
    return manifest, resolve_halo_decision(manifest)


@router.get("/sky", response_model=SkyResponse)
def get_sky(response: Response, query: Annotated[SkyQuery, Query()]) -> SkyResponse:
    response.headers["Cache-Control"] = "no-store"

    (
        center_ra,
        center_dec,
        asset_key,
        cutout_size,
        max_visits,
        target_record,
    ) = _resolve_query(query)

    if query.source == "saved":
        if target_record is None:
            raise ApiError(422, "VALIDATION_ERROR", "Saved mode requires a catalog target_id.", {})
        golden = load_golden_manifest(target_record)
        if golden is None:
            raise ApiError(404, "NO_DATA", "The requested saved observation is unavailable; choose archive mode to query IRSA.", {})
        return _build_response(query, golden.manifest, center_ra, center_dec, asset_key, golden.halo)

    from services.provenance import assert_application_source_current
    assert_application_source_current()
    # Online targets and arbitrary coordinates use the same fresh archive path.
    # Never reuse a catalog namespace: its old assets describe different astrometry.
    asset_key = live_asset_key(center_ra, center_dec, query.size, discovery_mode=query.discovery)
    try:
        manifest = build_manifest(
            asset_key, center_ra, center_dec, cutout_size_deg=query.size,
            max_visits_per_band=settings.max_visits_per_band,
            max_epochs=settings.live_sky_max_epochs, live_mode=True,
            deadline_seconds=settings.live_sky_deadline_seconds, force_refresh=True,
            allow_single_epoch=True,
            discovery_mode=query.discovery, target_id=query.target_id,
        )
        halo_decision = resolve_halo_decision(manifest, evaluate_gate=False)
    except IRSANoData as exc:
        detail = dict(exc.detail)
        detail["collections_tried"] = exc.collections_tried
        raise ApiError(404, "NO_DATA", str(exc), detail) from exc
    except NoUsablePixelsError as exc:
        raise ApiError(
            404,
            "NO_DATA",
            "No usable SPHEREx pixels cover this position.",
            {"ra": center_ra, "dec": center_dec, "reason": str(exc)},
        ) from exc
    except IRSAUnavailable as exc:
        raise ApiError(503, "UPSTREAM_UNAVAILABLE", str(exc), {}) from exc
    except PipelineError as exc:
        raise ApiError(
            503,
            "UPSTREAM_UNAVAILABLE",
            "The SPHEREx cutout could not be processed.",
            {"reason": str(exc)},
        ) from exc
    except IRSAError as exc:
        raise ApiError(503, "UPSTREAM_UNAVAILABLE", str(exc), {}) from exc

    return _build_response(
        query,
        manifest,
        center_ra,
        center_dec,
        asset_key,
        halo_decision,
    )
