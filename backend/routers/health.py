"""GET /api/v1/health."""

from __future__ import annotations

import time

from fastapi import APIRouter, Response
from models import HealthResponse

from core.config import settings
from services.irsa_client import IrsaClient
from services.spherex_pipeline import cache_entry_count

router = APIRouter(tags=["health"])

_PROBE_TTL_SECONDS = 60.0
_probe_value: bool | None = None
_probe_checked_at = 0.0


def _irsa_reachable() -> bool:
    global _probe_value, _probe_checked_at
    now = time.monotonic()
    if _probe_value is None or (now - _probe_checked_at) > _PROBE_TTL_SECONDS:
        _probe_value = IrsaClient().check_availability()
        _probe_checked_at = now
    return bool(_probe_value)


@router.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(
        status="ok",
        version=settings.api_contract_version,
        irsa_reachable=_irsa_reachable(),
        cache_entries=cache_entry_count(),
    )
