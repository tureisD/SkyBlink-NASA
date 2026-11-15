"""Fresh archive spectrum by default; saved and known-index modes are explicit.

Known discovery yields sparse samples from newly downloaded indexed exposures,
not a complete current archive spectrum. No failure automatically changes mode.
Extraction uses unnormalized, ZODI/background-subtracted native pixels.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Response
from typing import Annotated
from models import (
    Confidence,
    MolecularFeature,
    SpectrumChannel,
    SpectrumEpoch,
    SpectrumProvenance,
    SpectrumQuery,
    SpectrumResponse,
)

from app.errors import ApiError
from core.config import settings
from core.source_policy import source_target
from core.targets import TargetRecord, angular_separation_arcsec, get_target
from services.golden_cache import load_golden_spectrum
from services.product_metadata import creation_time, measurement_availability
from services.irsa_client import IRSANoData, IRSAError, IRSAUnavailable
from services.spectrophotometry import (
    APERTURE_RADIUS_ARCSEC,
    MOLECULAR_FEATURES,
    WAVELENGTH_CALIBRATION,
    build_spectrum,
    spectrum_asset_key,
)
from services.spherex_pipeline import NoUsablePixelsError, PipelineError

router = APIRouter(tags=["spectrum"])

logger = logging.getLogger(__name__)

TARGET_MATCH_TOLERANCE_ARCSEC = 1.0


def _resolve_query(
    query: SpectrumQuery,
) -> tuple[float, float, str, Confidence, int, float | None, TargetRecord | None]:
    """Return (center_ra, center_dec, asset_key, confidence, visits, deadline)."""
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
            Confidence.HIGH,
            settings.spectrum_max_visits_per_band,
            None,
            target,
        )

    return (
        query.ra,
        query.dec,
        spectrum_asset_key(query.ra, query.dec),
        Confidence.LOW,
        settings.spectrum_live_max_visits_per_band,
        settings.spectrum_live_timeout_seconds,
        None,
    )


def _build_spectrum_response(
    query: SpectrumQuery,
    spectrum: dict,
    center_ra: float,
    center_dec: float,
    fallback_confidence: Confidence,
) -> SpectrumResponse:
    available_epochs = [str(epoch_id) for epoch_id in spectrum["available_epoch_ids"]]
    discovered_epochs = [
        str(epoch_id)
        for epoch_id in (
            spectrum.get("discovered_epoch_ids") or spectrum["available_epoch_ids"]
        )
    ]
    if query.epoch_id is not None:
        if query.epoch_id not in discovered_epochs:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Unknown epoch id for this position.",
                {
                    "unknown_epochs": [query.epoch_id],
                    "available_epochs": available_epochs,
                },
            )
        epoch_payloads = [
            epoch
            for epoch in spectrum["epochs"]
            if str(epoch["epoch_id"]) == query.epoch_id
        ]
    else:
        epoch_payloads = list(spectrum["epochs"])

    epochs: list[SpectrumEpoch] = []
    for epoch_payload in epoch_payloads:
        epochs.append(
            SpectrumEpoch(
                epoch_id=str(epoch_payload["epoch_id"]),
                label=str(epoch_payload["label"]),
                collection=str(epoch_payload["collection"]),
                release=str(epoch_payload["release"]),
                channels=[
                    SpectrumChannel(**channel)
                    for channel in epoch_payload.get("channels", [])
                ],
                observation_range=epoch_payload.get("observation_range"),
                measurement_availability=measurement_availability(epoch_payload.get("channels", [])),
            )
        )

    provenance_payload = spectrum["provenance"]
    provenance = SpectrumProvenance(
        source=str(provenance_payload["source"]),
        collection=str(provenance_payload["collection"]),
        release=str(provenance_payload["release"]),
        zodi_subtracted=bool(provenance_payload["zodi_subtracted"]),
        background_subtracted=bool(provenance_payload["background_subtracted"]),
        is_simulated_fallback=bool(provenance_payload["is_simulated_fallback"]),
        generated_at=creation_time(spectrum),
        citation=str(provenance_payload["citation"]),
        analysis_id=provenance_payload.get("analysis_id"),
        analysis_record_url=provenance_payload.get("analysis_record_url"),
        processing_version=provenance_payload.get("processing_version"),
        data_access=query.source,
        discovery_mode=query.discovery if query.source == "archive" else None,
        discovery_status=provenance_payload.get("discovery_status", "unknown"),
        missing_collections=provenance_payload.get("missing_collections", []),
    )

    response_confidence = Confidence(
        str(spectrum.get("confidence", fallback_confidence.value))
    )

    return SpectrumResponse(
        target_id=query.target_id,
        ra=center_ra,
        dec=center_dec,
        aperture_radius_arcsec=APERTURE_RADIUS_ARCSEC,
        wavelength_calibration=WAVELENGTH_CALIBRATION,
        confidence=response_confidence,
        epochs=epochs,
        molecular_features=[
            MolecularFeature(**feature) for feature in MOLECULAR_FEATURES
        ],
        provenance=provenance,
    )


@router.get("/spectrum", response_model=SpectrumResponse)
def get_spectrum(response: Response, query: Annotated[SpectrumQuery, Query()]) -> SpectrumResponse:
    response.headers["Cache-Control"] = "no-store"

    (
        center_ra,
        center_dec,
        asset_key,
        confidence,
        max_visits,
        deadline,
        target_record,
    ) = _resolve_query(query)

    if query.source == "saved":
        if target_record is None:
            raise ApiError(422, "VALIDATION_ERROR", "Saved mode requires a catalog target_id.", {})
        saved = load_golden_spectrum(target_record)
        if saved is None:
            raise ApiError(404, "NO_DATA", "The requested saved spectrum is unavailable; choose archive mode to query IRSA.", {})
        return _build_spectrum_response(query, saved, center_ra, center_dec, confidence)

    from services.provenance import assert_application_source_current
    assert_application_source_current()
    live_confidence = Confidence.LOW
    live_asset_key = spectrum_asset_key(center_ra, center_dec, target_id=query.target_id,
                                      discovery_mode=query.discovery)
    try:
        spectrum = build_spectrum(
            live_asset_key,
            center_ra,
            center_dec,
            confidence=live_confidence.value,
            max_visits_per_band=settings.spectrum_live_max_visits_per_band,
            max_epochs=settings.live_sky_max_epochs,
            target_record=target_record,
            live_mode=True,
            deadline_seconds=settings.live_sky_deadline_seconds,
            force_refresh=True,
            discovery_mode=query.discovery,
        )
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

    return _build_spectrum_response(
        query,
        spectrum,
        center_ra,
        center_dec,
        live_confidence,
    )
