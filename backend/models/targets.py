"""Target metadata contract (`/api/v1/targets`)."""

from __future__ import annotations

from pydantic import Field, field_validator

from .common import APIModel, TargetId


class Target(APIModel):
    id: TargetId
    name: str
    category: str
    ra_ref: float = Field(..., ge=0.0, lt=360.0)
    dec_ref: float = Field(..., ge=-90.0, le=90.0)
    ref_epoch: str
    ra_epoch2025: float = Field(..., ge=0.0, lt=360.0)
    dec_epoch2025: float = Field(..., ge=-90.0, le=90.0)
    pm_ra_mas_yr: float
    pm_dec_mas_yr: float
    recommended_bands: list[int] = Field(..., min_length=1)
    story_headline: str
    story_body: str

    @field_validator("recommended_bands")
    @classmethod
    def _validate_bands(cls, value: list[int]) -> list[int]:
        if any(band < 1 or band > 6 for band in value):
            raise ValueError("recommended_bands must be in 1..6")
        return sorted(set(value))


class TargetListResponse(APIModel):
    targets: list[Target]
