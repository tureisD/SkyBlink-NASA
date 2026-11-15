"""Runtime configuration for the SPHEREx SkyBlink backend.

Run the app from ``backend/`` (``uvicorn app.main:app``) so the canonical
imports ``models.*``, ``core.*``, ``services.*`` and ``routers.*`` resolve.

Relative paths in the environment are resolved against the repository root,
which is what ``.env.example`` assumes.  The cache directories are created on
startup; they are never committed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from models.version import API_CONTRACT_VERSION

#: ``backend/core/config.py`` -> ``backend/core`` -> ``backend`` -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    try:
        return int(value) if value and value.strip() else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    try:
        return float(value) if value and value.strip() else default
    except ValueError:
        return default


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value or not value.strip():
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.environ.get(name)
    if not value or not value.strip():
        return default
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    """Backend settings loaded from the environment with local defaults."""

    irsa_tap: str = "https://irsa.ipac.caltech.edu/TAP"
    irsa_sia2: str = "https://irsa.ipac.caltech.edu/SIA"
    irsa_base: str = "https://irsa.ipac.caltech.edu/"
    cache_dir: Path = field(default_factory=lambda: BACKEND_ROOT / ".cache")
    golden_cache_dir: Path = field(default_factory=lambda: REPO_ROOT / "golden_cache")
    max_workers: int = 8
    max_visits_per_band: int = 3
    cache_ttl_seconds: int = 24 * 3600
    # Soft process-local admission; not a hard filesystem quota or cleanup job.
    live_max_active_builds: int = 2
    runtime_storage_budget_bytes: int = 8 * 1024**3
    runtime_min_free_bytes: int = 1024**3
    live_build_reservation_bytes: int = 512 * 1024**2
    #: Offline/golden spectrum tier: up to 12 visits per band/epoch (=72
    #: channels/epoch when all six detectors are present).  The live arbitrary
    #: path stays at one visit per band.
    spectrum_max_visits_per_band: int = 12
    spectrum_live_max_visits_per_band: int = 1
    spectrum_live_timeout_seconds: float = 90.0
    live_retries: int = 3
    live_retry_backoff_seconds: float = 0.25
    #: IRSA TAP takes 35-60 s for arbitrary fields; allow a full TAP response
    #: plus cutout downloads inside a ~2 minute best-effort sky deadline.
    live_connect_timeout_seconds: float = 10.0
    live_request_timeout_seconds: float = 20.0
    live_tap_timeout_seconds: float = 60.0
    live_sky_deadline_seconds: float = 120.0
    #: Candidate epochs searched for a compatible live pair, not promised output.
    live_sky_max_epochs: int = 3
    connect_timeout_seconds: float = 10.0
    request_timeout_seconds: float = 60.0
    tap_timeout_seconds: float = 120.0
    retries: int = 4
    retry_backoff_seconds: float = 1.5
    log_level: str = "INFO"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    api_contract_version: str = API_CONTRACT_VERSION

    @property
    def cutout_cache_dir(self) -> Path:
        return self.cache_dir / "cutouts"

    @property
    def live_cache_dir(self) -> Path:
        return self.cache_dir / "live"

    def ensure_dirs(self) -> None:
        for path in (self.cache_dir, self.cutout_cache_dir, self.live_cache_dir):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            irsa_tap=_env_str("IRSA_TAP", cls.irsa_tap),
            irsa_sia2=_env_str("IRSA_SIA2", cls.irsa_sia2),
            irsa_base=_env_str("IRSA_CUTOUT_BASE", cls.irsa_base),
            cache_dir=_env_path("CACHE_DIR", BACKEND_ROOT / ".cache"),
            golden_cache_dir=_env_path("GOLDEN_CACHE_DIR", REPO_ROOT / "golden_cache"),
            max_workers=_env_int("MAX_WORKERS", cls.max_workers),
            max_visits_per_band=_env_int(
                "MAX_VISITS_PER_BAND", cls.max_visits_per_band
            ),
            cache_ttl_seconds=_env_int("CACHE_TTL_SECONDS", cls.cache_ttl_seconds),
            live_max_active_builds=_env_int("LIVE_MAX_ACTIVE_BUILDS", cls.live_max_active_builds),
            runtime_storage_budget_bytes=_env_int("RUNTIME_STORAGE_BUDGET_BYTES", cls.runtime_storage_budget_bytes),
            runtime_min_free_bytes=_env_int("RUNTIME_MIN_FREE_BYTES", cls.runtime_min_free_bytes),
            live_build_reservation_bytes=_env_int("LIVE_BUILD_RESERVATION_BYTES", cls.live_build_reservation_bytes),
            spectrum_max_visits_per_band=_env_int(
                "SPECTRUM_MAX_VISITS_PER_BAND", cls.spectrum_max_visits_per_band
            ),
            spectrum_live_max_visits_per_band=_env_int(
                "SPECTRUM_LIVE_MAX_VISITS_PER_BAND",
                cls.spectrum_live_max_visits_per_band,
            ),
            spectrum_live_timeout_seconds=_env_float(
                "SPECTRUM_LIVE_TIMEOUT_SECONDS",
                cls.spectrum_live_timeout_seconds,
            ),
            live_retries=_env_int("LIVE_RETRIES", cls.live_retries),
            live_retry_backoff_seconds=_env_float(
                "LIVE_RETRY_BACKOFF_SECONDS", cls.live_retry_backoff_seconds
            ),
            live_connect_timeout_seconds=_env_float(
                "LIVE_CONNECT_TIMEOUT_SECONDS", cls.live_connect_timeout_seconds
            ),
            live_request_timeout_seconds=_env_float(
                "LIVE_REQUEST_TIMEOUT_SECONDS", cls.live_request_timeout_seconds
            ),
            live_tap_timeout_seconds=_env_float(
                "LIVE_TAP_TIMEOUT_SECONDS", cls.live_tap_timeout_seconds
            ),
            live_sky_deadline_seconds=_env_float(
                "LIVE_SKY_DEADLINE_SECONDS", cls.live_sky_deadline_seconds
            ),
            live_sky_max_epochs=_env_int(
                "LIVE_SKY_MAX_EPOCHS", cls.live_sky_max_epochs
            ),
            request_timeout_seconds=_env_float(
                "REQUEST_TIMEOUT_SECONDS", cls.request_timeout_seconds
            ),
            tap_timeout_seconds=_env_float(
                "TAP_TIMEOUT_SECONDS", cls.tap_timeout_seconds
            ),
            retries=_env_int("IRSA_RETRIES", cls.retries),
            retry_backoff_seconds=_env_float(
                "IRSA_RETRY_BACKOFF_SECONDS", cls.retry_backoff_seconds
            ),
            log_level=_env_str("LOG_LEVEL", cls.log_level),
            cors_origins=_env_csv("CORS_ORIGINS", cls.cors_origins),
            api_contract_version=API_CONTRACT_VERSION,
        )


settings = Settings.from_env()

__all__ = [
    "API_CONTRACT_VERSION",
    "BACKEND_ROOT",
    "REPO_ROOT",
    "Settings",
    "settings",
]
