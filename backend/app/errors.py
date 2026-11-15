"""API error envelope and exception handlers (``AGENTS.md`` §3.7)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from models import ErrorDetail, ErrorResponse
from services.provenance import RuntimeSourceChanged
from services.build_limits import BuildAdmissionError

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised by routers to return the contract error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        self.detail = dict(detail or {})


def _envelope(status_code: int, code: str, message: str, detail: dict | None = None) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, detail=dict(detail or {}))
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _is_coordinate_error(errors: list[dict]) -> bool:
    """True when every validation failure is an RA/Dec query field."""
    if not errors:
        return False
    for error in errors:
        location = list(error.get("loc", ()))
        if len(location) < 2 or location[0] != "query" or location[1] not in {"ra", "dec"}:
            return False
    return True


def register_error_handlers(app: FastAPI) -> None:
    """Install handlers so every API failure uses the §3.7 envelope."""

    @app.exception_handler(BuildAdmissionError)
    async def _build_admission(_: Request, exc: BuildAdmissionError) -> JSONResponse:
        result = _envelope(503, "UPSTREAM_UNAVAILABLE", str(exc), {"reason": exc.reason})
        result.headers["Cache-Control"] = "no-store"
        if exc.retry_after is not None:
            result.headers["Retry-After"] = str(exc.retry_after)
        return result

    @app.exception_handler(RuntimeSourceChanged)
    async def _source_changed(_: Request, exc: RuntimeSourceChanged) -> JSONResponse:
        return _envelope(503, "UPSTREAM_UNAVAILABLE", str(exc), {"reason": "PROCESSING_SOURCE_CHANGED"})

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = jsonable_encoder(exc.errors())
        if _is_coordinate_error(errors):
            return _envelope(
                400,
                "INVALID_COORDINATES",
                "RA/Dec are out of range or unparsable.",
                {"errors": errors},
            )
        return _envelope(
            422,
            "VALIDATION_ERROR",
            "Invalid query parameters.",
            {"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = int(exc.status_code)
        if status == 404:
            code = "NO_DATA"
            message = "Resource not found."
        elif status == 503:
            code = "UPSTREAM_UNAVAILABLE"
            message = "An upstream service is unavailable."
        elif status == 400:
            code = "INVALID_COORDINATES"
            message = "Invalid coordinates or query parameters."
        elif status == 422:
            code = "VALIDATION_ERROR"
            message = "Invalid query parameters."
        else:
            code = "INTERNAL_ERROR" if status >= 500 else "VALIDATION_ERROR"
            message = str(exc.detail) if exc.detail else "Request failed."
        return _envelope(status, code, message, {})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error", exc_info=exc)
        return _envelope(
            500,
            "INTERNAL_ERROR",
            "Unexpected server error.",
            {},
        )
