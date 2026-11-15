"""GET /api/v1/targets."""

from __future__ import annotations

from fastapi import APIRouter, Response
from models import TargetListResponse

from typing import Literal
from core.source_policy import source_targets

router = APIRouter(tags=["targets"])


@router.get("/targets", response_model=TargetListResponse)
def list_targets(response: Response, source: Literal["archive", "saved"] = "archive") -> TargetListResponse:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return TargetListResponse(targets=[target.to_contract() for target in source_targets(source)])
