"""GET /api/v1/assets/{target_id}/{filename} — golden cache or live cache.

Path traversal is rejected; catalog assets are served from ``golden_cache/``
when present and live B1 assets from the backend cache.  Missing files use the
contract ``NO_DATA`` envelope.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.errors import ApiError
from core.cachekeys import is_live_asset_key, is_valid_asset_key, is_valid_filename
from core.config import settings
from core.targets import get_target
from services.telemetry import GZIP_MAGIC, is_telemetry_filename

router = APIRouter(tags=["assets"])

_MEDIA_TYPES = {
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".json": "application/json",
    ".fits": "application/fits",
    ".gz": "application/gzip",
}


def _resolve_within(base: Path, *parts: str) -> Path | None:
    """Resolve a child path, returning ``None`` if it escapes ``base``."""
    base_resolved = base.resolve()
    candidate = (base_resolved / Path(*parts)).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        return None
    return candidate


@router.get("/assets/{target_id}/{filename}")
def get_asset(target_id: str, filename: str):
    if not is_valid_asset_key(target_id) or not is_valid_filename(filename):
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Invalid asset path.",
            {"target_id": target_id, "filename": filename},
        )

    # Only catalog observations and canonical live query keys are public.
    # Reject retired fixtures even if an old volume still contains them.
    if get_target(target_id) is not None:
        sources = (
            (settings.golden_cache_dir, "public, max-age=3600"),
            (settings.live_cache_dir, "no-store"),
        )
    elif is_live_asset_key(target_id):
        sources = ((settings.live_cache_dir, "no-store"),)
    else:
        raise ApiError(
            404,
            "NO_DATA",
            "Asset not found.",
            {"target_id": target_id, "filename": filename},
        )
    for base, cache_control in sources:
        candidate = _resolve_within(base, target_id, filename)
        if candidate is None or not candidate.is_file():
            continue
        if is_telemetry_filename(candidate.name):
            with candidate.open("rb") as handle:
                if handle.read(2) != GZIP_MAGIC:
                    raise ApiError(
                        500,
                        "INTERNAL_ERROR",
                        "Telemetry sidecar is corrupt.",
                        {"target_id": target_id, "filename": filename},
                    )
        suffix = candidate.suffix.lower()
        return FileResponse(
            candidate,
            media_type=_MEDIA_TYPES.get(suffix, "application/octet-stream"),
            headers={"Cache-Control": cache_control},
        )

    raise ApiError(
        404,
        "NO_DATA",
        "Asset not found.",
        {"target_id": target_id, "filename": filename},
    )
