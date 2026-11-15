"""Isolated resource-admission tests; byte sentinels are not observation data."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.errors import register_error_handlers
from core.config import Settings
from services import build_limits
from services.singleflight import run_once


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(build_limits, "_active", 0)
    monkeypatch.setattr(build_limits.shutil, "disk_usage", lambda _: SimpleNamespace(free=10_000))
    return replace(Settings(), cache_dir=tmp_path, live_max_active_builds=1,
                   runtime_storage_budget_bytes=1000, runtime_min_free_bytes=100,
                   live_build_reservation_bytes=100)


def test_same_query_shares_one_slot_distinct_query_is_refused(config):
    entered, release, follower_started = Event(), Event(), Event()
    calls = []
    def work():
        calls.append(1)
        entered.set()
        assert release.wait(2)
        return "completed isolated work"
    admission = lambda: build_limits.live_build_slot(config)
    def follower():
        follower_started.set()
        return run_once(("admission-shared",), time.monotonic()+2, work, admission=admission)
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(run_once, ("admission-shared",), time.monotonic()+2, work, admission=admission)
        assert entered.wait(1)
        second = pool.submit(follower)
        assert follower_started.wait(1)
        time.sleep(.02)
        try:
            with pytest.raises(build_limits.BuildAdmissionError) as failure:
                run_once(("admission-other",), time.monotonic()+1, work, admission=admission)
            assert failure.value.reason == "SERVER_BUSY"
        finally:
            release.set()
        assert leader.result() == second.result() == "completed isolated work"
    assert calls == [1]
    assert build_limits._active == 0


def test_failure_releases_admission_and_allows_retry(config):
    def fail():
        raise ValueError("isolated processing failure")
    admission = lambda: build_limits.live_build_slot(config)
    with pytest.raises(ValueError):
        run_once(("admission-failure",), None, fail, admission=admission)
    assert build_limits._active == 0
    assert run_once(("admission-failure",), None, lambda: 7, admission=admission) == 7


@pytest.mark.parametrize("free", [0, 199])
def test_low_disk_preflight_prevents_work_without_deleting(config, monkeypatch, free):
    retained = config.cache_dir / "analysis-inputs" / "sentinel"
    retained.parent.mkdir(); retained.write_bytes(b"isolated retention sentinel")
    monkeypatch.setattr(build_limits.shutil, "disk_usage", lambda _: SimpleNamespace(free=free))
    calls = []
    with pytest.raises(build_limits.BuildAdmissionError) as failure:
        run_once(("low-disk",), None, lambda: calls.append(1),
                 admission=lambda: build_limits.live_build_slot(config))
    assert failure.value.reason == "STORAGE_BUDGET_EXCEEDED"
    assert calls == [] and build_limits._active == 0
    assert retained.read_bytes() == b"isolated retention sentinel"


def test_usage_counts_runtime_only_and_reserves_active_leaders(config):
    for name in build_limits.RUNTIME_DIRS:
        folder = config.cache_dir / name; folder.mkdir()
        (folder / "sentinel").write_bytes(b"x" * 200)
    research = config.cache_dir / "phase6"; research.mkdir()
    (research / "sentinel").write_bytes(b"x" * 2000)
    assert build_limits.runtime_storage_bytes(config.cache_dir) == 800
    config = replace(config, live_max_active_builds=3)
    with build_limits.live_build_slot(config):
        with build_limits.live_build_slot(config):
            with pytest.raises(build_limits.BuildAdmissionError, match="storage headroom"):
                with build_limits.live_build_slot(config):
                    pytest.fail("Third reservation exceeds budget")


def test_unreadable_storage_fails_closed(config, monkeypatch):
    def fail(_):
        raise PermissionError("isolated permissions failure")
    monkeypatch.setattr(build_limits, "runtime_storage_bytes", fail)
    with pytest.raises(build_limits.BuildAdmissionError) as failure:
        with build_limits.live_build_slot(config):
            pytest.fail("Work must not start")
    assert failure.value.reason == "STORAGE_UNAVAILABLE"
    assert build_limits._active == 0


def test_busy_has_typed_reason_retry_header_and_no_store():
    app = FastAPI(); register_error_handlers(app)
    @app.get("/busy")
    def busy():
        raise build_limits.BuildAdmissionError("Retry shortly.", "SERVER_BUSY", retry_after=5)
    response = TestClient(app).get("/busy")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["error"]["detail"]["reason"] == "SERVER_BUSY"


def test_settings_read_resource_limits(monkeypatch):
    for key, value in {"LIVE_MAX_ACTIVE_BUILDS": 3, "RUNTIME_STORAGE_BUDGET_BYTES": 10000,
                       "RUNTIME_MIN_FREE_BYTES": 500, "LIVE_BUILD_RESERVATION_BYTES": 250}.items():
        monkeypatch.setenv(key, str(value))
    actual = Settings.from_env()
    assert (actual.live_max_active_builds, actual.runtime_storage_budget_bytes,
            actual.runtime_min_free_bytes, actual.live_build_reservation_bytes) == (3, 10000, 500, 250)
