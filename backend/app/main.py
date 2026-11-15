"""FastAPI application factory for the SPHEREx SkyBlink API."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models.version import API_CONTRACT_VERSION

from app.errors import ApiError, register_error_handlers
from core.config import settings
from routers import assets, health, sky, spectrum, targets
from services.spherex_pipeline import CACHE_VERSION as IMAGE_METHOD_VERSION
from services.provenance import bind_application_source


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings.ensure_dirs()
    bind_application_source()
    logging.getLogger(__name__).info(
        "SkyBlink runtime loaded: pid=%s api=%s image_method=matched_image_comparison/%s",
        os.getpid(), API_CONTRACT_VERSION, IMAGE_METHOD_VERSION,
    )

    app = FastAPI(
        title="SPHEREx SkyBlink API",
        description=(
            "Contract for the SPHEREx SkyBlink public web tool. "
            "Schemas are defined in backend/models and AGENTS.md §3."
        ),
        version=API_CONTRACT_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(targets.router, prefix="/api/v1")
    app.include_router(sky.router, prefix="/api/v1")
    app.include_router(spectrum.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")

    # Register before the production static mount. Stale frontend volumes
    # must not make retired development observations publicly reachable.
    @app.api_route("/mock", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/mock/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def retired_fixture(path: str = "") -> None:
        raise ApiError(404, "NO_DATA", "Asset not found.", {})

    register_error_handlers(app)
    return app


app = create_app()
