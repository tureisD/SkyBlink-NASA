"""Health contract (`/api/v1/health`)."""

from __future__ import annotations

from .common import APIModel


class HealthResponse(APIModel):
    status: str
    version: str
    irsa_reachable: bool
    cache_entries: int
