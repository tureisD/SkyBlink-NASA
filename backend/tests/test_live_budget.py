"""Live arbitrary-coordinate budget regression tests.

IRSA TAP takes 35-60 s for a random field, so the live path must allow a full
60 s TAP response plus cutout downloads inside a ~2 minute best-effort sky
deadline.  The catalog/golden path keeps its original, much larger retry and
timeout budget and must not change with the live tiers.
"""

from __future__ import annotations

import pytest

from core.config import BACKEND_ROOT, REPO_ROOT, Settings


def test_live_arbitrary_coordinate_defaults_tolerate_irsa_latency() -> None:
    """Pin the latency-tolerant live defaults (measured slow IRSA TAP)."""
    settings = Settings()

    assert settings.live_connect_timeout_seconds == 10.0
    assert settings.live_request_timeout_seconds == 20.0
    assert settings.live_tap_timeout_seconds == 60.0
    assert settings.live_sky_deadline_seconds == 120.0

    # Phase 4 archive access: transient 502/503 retries share the same deadline.
    assert settings.live_retries == 3
    assert settings.live_retry_backoff_seconds == 0.25
    assert settings.live_sky_max_epochs == 3


def test_live_budget_covers_full_tap_response_and_cutouts() -> None:
    """The sky deadline must outlast one TAP response plus cutout downloads."""
    settings = Settings()

    assert settings.live_tap_timeout_seconds >= 60.0
    assert (
        settings.live_sky_deadline_seconds
        >= settings.live_tap_timeout_seconds + settings.live_request_timeout_seconds
    )


def test_catalog_and_golden_defaults_are_unchanged() -> None:
    """The five catalog targets keep the full/golden configuration."""
    settings = Settings()

    assert settings.connect_timeout_seconds == 10.0
    assert settings.request_timeout_seconds == 60.0
    assert settings.tap_timeout_seconds == 120.0
    assert settings.retries == 4
    assert settings.retry_backoff_seconds == 1.5
    assert settings.max_workers == 8
    assert settings.max_visits_per_band == 3
    assert settings.cache_ttl_seconds == 24 * 3600
    assert settings.spectrum_max_visits_per_band == 12
    assert settings.spectrum_live_max_visits_per_band == 1
    assert settings.spectrum_live_timeout_seconds == 90.0
    assert settings.golden_cache_dir == REPO_ROOT / "golden_cache"
    assert settings.cache_dir == BACKEND_ROOT / ".cache"


def test_live_budget_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Settings.from_env`` wires the documented live environment names."""
    monkeypatch.setenv("LIVE_CONNECT_TIMEOUT_SECONDS", "11.0")
    monkeypatch.setenv("LIVE_REQUEST_TIMEOUT_SECONDS", "21.0")
    monkeypatch.setenv("LIVE_TAP_TIMEOUT_SECONDS", "61.0")
    monkeypatch.setenv("LIVE_SKY_DEADLINE_SECONDS", "121.0")

    settings = Settings.from_env()

    assert settings.live_connect_timeout_seconds == 11.0
    assert settings.live_request_timeout_seconds == 21.0
    assert settings.live_tap_timeout_seconds == 61.0
    assert settings.live_sky_deadline_seconds == 121.0
