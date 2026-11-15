"""Process-local live-build admission and conservative storage headroom checks.

This is soft admission, not a filesystem quota: other processes and an unusually
large active response can consume space after preflight. Nothing is deleted.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from threading import Lock

from core.config import Settings

RUNTIME_DIRS = ("cutouts", "live", "analysis-inputs", "discovery-responses")
_lock = Lock()
_active = 0


class BuildAdmissionError(Exception):
    def __init__(self, message: str, reason: str, *, retry_after: int | None = None):
        super().__init__(message)
        self.reason = reason
        self.retry_after = retry_after


def runtime_storage_bytes(cache_dir: Path) -> int:
    """Count only managed runtime files; never follow directory/file symlinks."""
    total = 0
    def fail(error: OSError) -> None:
        raise error
    for name in RUNTIME_DIRS:
        root = cache_dir / name
        if root.is_symlink():
            raise OSError("Runtime storage cannot be a symbolic link")
        if not root.exists():
            continue
        for directory, folders, files in os.walk(root, followlinks=False, onerror=fail):
            for name in folders + files:
                if (Path(directory) / name).is_symlink():
                    raise OSError("Runtime storage cannot contain symbolic links")
            for name in files:
                try:
                    total += (Path(directory) / name).stat().st_size
                except FileNotFoundError:
                    # Another admitted build may atomically rename its temporary.
                    continue
    return total


def _storage_preflight(config: Settings, active: int) -> None:
    reserve = (active + 1) * max(0, config.live_build_reservation_bytes)
    try:
        usage = runtime_storage_bytes(config.cache_dir)
        existing = config.cache_dir
        while not existing.exists():
            existing = existing.parent
        free = shutil.disk_usage(existing).free
    except OSError as exc:
        raise BuildAdmissionError(
            "Runtime storage could not be checked. The server operator must inspect storage before retrying.",
            "STORAGE_UNAVAILABLE",
        ) from exc
    if (usage + reserve > config.runtime_storage_budget_bytes or
            free < config.runtime_min_free_bytes + reserve):
        raise BuildAdmissionError(
            "The server has insufficient storage headroom for another archive build. "
            "Existing analysis records are preserved; the server operator must review storage.",
            "STORAGE_BUDGET_EXCEEDED",
        )


@contextmanager
def live_build_slot(config: Settings):
    """Admit a distinct build immediately or refuse it before archive I/O."""
    global _active
    with _lock:
        if _active >= max(1, config.live_max_active_builds):
            raise BuildAdmissionError(
                "The server is processing other archive requests. Retry shortly.",
                "SERVER_BUSY", retry_after=5,
            )
        _storage_preflight(config, _active)
        _active += 1
    try:
        yield
    finally:
        with _lock:
            _active -= 1
