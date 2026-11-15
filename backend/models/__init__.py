"""SPHEREx SkyBlink API contract models.

Canonical import path when running from ``backend/``:

    from models import SkyResponse, SpectrumResponse

Keep this package in sync with ``AGENTS.md`` §3 and
``docs/decisions/o1-contract-decisions.md``. The Orchestrator owns this package.
"""

from .common import APIModel, Confidence, FlagStatus, TargetId
from .errors import ErrorDetail, ErrorResponse
from .health import HealthResponse
from .sky import (
    DetectedCandidate,
    Epoch,
    FlagSummary,
    FluxNormalization,
    LVFGeometry,
    SkyProvenance,
    SkyQuery,
    SkyQueryInfo,
    SkyResponse,
    TelemetryAsset,
    WCS,
)
from .spectrum import (
    MolecularFeature,
    SpectrumChannel,
    SpectrumEpoch,
    SpectrumProvenance,
    SpectrumQuery,
    SpectrumResponse,
)
from .targets import Target, TargetListResponse
from .version import API_CONTRACT_VERSION

__all__ = [
    "APIModel",
    "API_CONTRACT_VERSION",
    "Confidence",
    "DetectedCandidate",
    "Epoch",
    "ErrorDetail",
    "ErrorResponse",
    "FlagStatus",
    "FlagSummary",
    "FluxNormalization",
    "HealthResponse",
    "LVFGeometry",
    "MolecularFeature",
    "SkyProvenance",
    "SkyQuery",
    "SkyQueryInfo",
    "SkyResponse",
    "SpectrumChannel",
    "SpectrumEpoch",
    "SpectrumProvenance",
    "SpectrumQuery",
    "SpectrumResponse",
    "Target",
    "TargetId",
    "TargetListResponse",
    "TelemetryAsset",
    "WCS",
]
