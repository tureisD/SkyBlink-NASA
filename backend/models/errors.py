"""Error envelope contract (`AGENTS.md` §3.7)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import APIModel


class ErrorDetail(APIModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(APIModel):
    error: ErrorDetail
