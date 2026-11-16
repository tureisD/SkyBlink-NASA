"""Sky manifest contract (`/api/v1/sky`)."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from .common import APIModel, EPOCH_ID_PATTERN, FlagStatus, TargetId
from .targets import Target


def _serialize_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SkyQuery(APIModel):
    """Validated `/api/v1/sky` query parameters."""

    ra: float = Field(..., ge=0.0, lt=360.0, description="ICRS degrees")
    dec: float = Field(..., ge=-90.0, le=90.0, description="ICRS degrees")
    size: float = Field(0.2, description="Cutout/crop size in degrees; clamped to 0.05-0.2")
    target_id: TargetId | None = None
    epochs: str = "all"
    bands: str = "all"
    include_diff: bool = True
    source: Literal["archive", "saved"] = "archive"
    discovery: Literal["live", "known", "indexed"] = "live"

    @model_validator(mode="after")
    def _validate_discovery_scope(self) -> "SkyQuery":
        if self.discovery == "known" and (self.source != "archive" or self.target_id is None):
            raise ValueError("known discovery requires source=archive and a catalog target_id")
        if self.discovery == "indexed" and self.source != "archive":
            raise ValueError("indexed discovery requires source=archive")
        return self

    @field_validator("size", mode="before")
    @classmethod
    def _clamp_size(cls, value: float) -> float:
        try:
            size = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("size must be a number") from exc
        if not math.isfinite(size):
            raise ValueError("size must be finite")
        return min(0.2, max(0.05, size))

    @field_validator("epochs")
    @classmethod
    def _validate_epochs(cls, value: str) -> str:
        value = value.strip()
        if not value or value.lower() == "all":
            return "all"
        ids = [part.strip() for part in value.split(",") if part.strip()]
        if not ids:
            raise ValueError("epochs must be 'all' or a comma-separated list")
        for epoch_id in ids:
            if not re.fullmatch(EPOCH_ID_PATTERN, epoch_id):
                raise ValueError(f"invalid epoch id: {epoch_id!r}")
        return ",".join(sorted(set(ids)))

    @field_validator("bands")
    @classmethod
    def _validate_bands(cls, value: str) -> str:
        value = value.strip()
        if not value or value.lower() == "all":
            return "all"
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("bands must be 'all' or a comma-separated list of 1..6")
        bands: list[int] = []
        for part in parts:
            if not part.isdigit() or not 1 <= int(part) <= 6:
                raise ValueError(f"invalid band: {part!r}")
            bands.append(int(part))
        return ",".join(str(band) for band in sorted(set(bands)))


class SkyQueryInfo(APIModel):
    ra: float
    dec: float
    size_deg: float
    target_id: TargetId | None


class WCS(APIModel):
    crval1: float
    crval2: float
    crpix1: float
    crpix2: float
    cdelt1: float
    cdelt2: float
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    pixel_scale_arcsec: float
    native_pixel_scale_arcsec: float


class FlagSummary(APIModel):
    status: FlagStatus
    source_bit_set: bool
    artifact_pixel_fraction: float = Field(..., ge=0.0, le=1.0)
    active_warning_flags: list[str]
    human_explanation: str


class TelemetryAsset(APIModel):
    """Optional per-epoch float16 + uint32 telemetry sidecar (contract 1.1.0)."""

    url: str
    format: Literal["float16_uint32_le_gzip"]
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    byte_size: int = Field(..., ge=0)
    flux_band: Literal["thermal", "all"] = "all"
    quantity: Literal["normalized_display_intensity"] | None = None
    normalization_applied: bool | None = None


class LVFGeometry(APIModel):
    """Per-detector LVF dispersion geometry (contract 1.1.0)."""

    detector: int = Field(..., ge=1, le=6)
    pa_deg: float = Field(..., allow_inf_nan=False)
    grad_um_per_arcsec: float = Field(..., allow_inf_nan=False)


class DetectedCandidate(APIModel):
    """Objective difference-frame candidate; no confidence score (contract 1.1.0)."""

    id: str
    ra: float = Field(..., ge=0.0, lt=360.0, allow_inf_nan=False)
    dec: float = Field(..., ge=-90.0, le=90.0, allow_inf_nan=False)
    x_px: float = Field(..., allow_inf_nan=False)
    y_px: float = Field(..., allow_inf_nan=False)
    kind: Literal["dipole", "variable"]
    snr: float = Field(..., allow_inf_nan=False)
    delta_flux_mjy_sr: float | None = Field(None, allow_inf_nan=False)
    is_artifact_clean: bool = True
    label: str


class ObservationRange(APIModel):
    mjd_min: float = Field(..., allow_inf_nan=False)
    mjd_max: float = Field(..., allow_inf_nan=False)
    date_start_iso: date
    date_end_iso: date
    time_scale: Literal["utc"] = "utc"


class Epoch(APIModel):
    epoch_id: str
    label: str
    collection: str
    release: str
    mjd_mean: float
    date_iso: date
    frames: dict[str, str]
    flag_summary: FlagSummary
    telemetry: TelemetryAsset | None = None
    lvf_geometry: list[LVFGeometry] | None = None
    candidates: list[DetectedCandidate] | None = None
    core_inpainted: bool = False
    observation_range: ObservationRange | None = None


class FluxNormalization(APIModel):
    method: str
    scope: str
    reference_epoch: str | None = None
    applied: bool
    status: str
    clamped: bool = False
    raw_stats_location: str = "server_only"


class SkyProvenance(APIModel):
    source: str
    collection: str
    release: str
    zodi_subtracted: bool
    background_subtracted: bool
    flux_normalization: FluxNormalization
    is_simulated_fallback: bool
    generated_at: datetime
    citation: str
    analysis_id: str | None = None
    analysis_record_url: str | None = None
    processing_version: str | None = None
    data_access: Literal["archive", "saved"] | None = None
    discovery_mode: Literal["live", "known", "indexed"] | None = None
    comparison_status: Literal["matched_visual", "single_epoch", "unmatched_single_epoch", "legacy_unvalidated"] | None = None
    comparison_reason: str | None = None
    discovery_status: Literal["complete", "partial", "unknown"] = "unknown"
    missing_collections: list[str] = Field(default_factory=list)

    @field_serializer("generated_at")
    def _serialize_generated_at(self, value: datetime) -> str:
        return _serialize_utc(value)


class SkyResponse(APIModel):
    query: SkyQueryInfo
    target: Target | None
    wcs: WCS
    epochs: list[Epoch]
    differences: dict[str, dict[str, str]] = Field(default_factory=dict)
    reference_overlays: dict[str, str] = Field(default_factory=dict)
    provenance: SkyProvenance
