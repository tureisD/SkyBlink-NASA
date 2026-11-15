"""Spectrum contract (`/api/v1/spectrum`)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from .common import APIModel, Confidence, EPOCH_ID_PATTERN, TargetId
from .sky import ObservationRange


def _serialize_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SpectrumQuery(APIModel):
    """Validated `/api/v1/spectrum` query parameters."""

    ra: float = Field(..., ge=0.0, lt=360.0, description="ICRS degrees")
    dec: float = Field(..., ge=-90.0, le=90.0, description="ICRS degrees")
    target_id: TargetId | None = None
    epoch_id: str | None = None
    source: Literal["archive", "saved"] = "archive"
    discovery: Literal["live", "known"] = "live"

    @model_validator(mode="after")
    def _validate_discovery_scope(self) -> "SpectrumQuery":
        if self.discovery == "known" and (self.source != "archive" or self.target_id is None):
            raise ValueError("known discovery requires source=archive and a catalog target_id")
        return self

    @field_validator("epoch_id")
    @classmethod
    def _validate_epoch_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(EPOCH_ID_PATTERN, value):
            raise ValueError(f"invalid epoch id: {value!r}")
        return value


class SpectrumChannel(APIModel):
    detector: int = Field(..., ge=1, le=6)
    wavelength_um: float = Field(..., gt=0.0)
    bandwidth_um: float = Field(..., gt=0.0)
    flux_ujy: float | None = Field(None, description="Clean-pixel aperture flux; null without usable pixels or supported background.")
    flux_err_ujy: float | None = Field(None, description="Approximate uncertainty including median-background estimation; null when flux is unavailable.")
    flags: int = Field(..., ge=0)
    is_flagged_bad: bool
    clean_fraction: float = Field(..., ge=0.0, le=1.0)
    is_used_in_photometry: bool = Field(..., description="Archive 1.5.0: full clean aperture inside image, >=10 clean local-annulus pixels, supported field background, and no hard-bad centre. Necessary screening, not calibrated accuracy. Saved products retain historical eligibility.")
    photometry_method: Literal["aperture_12.3", "crowded_diff_6.8"] = "aperture_12.3"
    aperture_mode: Literal["standard_12.3", "crowded_diff_6.8"] = "standard_12.3"
    aperture_radius_arcsec: float = Field(12.3, gt=0.0, allow_inf_nan=False)
    input_id: str | None = None
    extraction_ra: float | None = Field(None, ge=0.0, lt=360.0, allow_inf_nan=False)
    extraction_dec: float | None = Field(None, ge=-90.0, le=90.0, allow_inf_nan=False)
    measurement_reasons: list[str] = Field(default_factory=list)


class MeasurementAvailability(APIModel):
    total_channels: int = Field(..., ge=0)
    finite_channels: int = Field(..., ge=0)
    usable_channels: int = Field(..., ge=0)
    reasons: list[str] = Field(default_factory=list)


class SpectrumEpoch(APIModel):
    epoch_id: str
    label: str
    collection: str
    release: str
    channels: list[SpectrumChannel]
    observation_range: ObservationRange | None = None
    measurement_availability: MeasurementAvailability | None = None


class MolecularFeature(APIModel):
    label: str
    wavelength_um: float = Field(..., gt=0.0)
    band: int = Field(..., ge=1, le=6)


class SpectrumProvenance(APIModel):
    source: str
    collection: str
    release: str
    zodi_subtracted: bool
    background_subtracted: bool
    is_simulated_fallback: bool
    generated_at: datetime
    citation: str
    analysis_id: str | None = None
    analysis_record_url: str | None = None
    processing_version: str | None = None
    data_access: Literal["archive", "saved"] | None = None
    discovery_mode: Literal["live", "known"] | None = None
    discovery_status: Literal["complete", "partial", "unknown"] = "unknown"
    missing_collections: list[str] = Field(default_factory=list)

    @field_serializer("generated_at")
    def _serialize_generated_at(self, value: datetime) -> str:
        return _serialize_utc(value)


class SpectrumResponse(APIModel):
    target_id: TargetId | None
    ra: float
    dec: float
    aperture_radius_arcsec: float = 12.3
    wavelength_calibration: str
    confidence: Confidence
    epochs: list[SpectrumEpoch]
    molecular_features: list[MolecularFeature]
    provenance: SpectrumProvenance
