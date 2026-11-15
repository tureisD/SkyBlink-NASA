"""Share concurrent work for one cache key without retaining failed results."""
from concurrent.futures import Future, TimeoutError
from contextlib import nullcontext
from threading import Lock
import time
from typing import Callable, ContextManager, TypeVar

from services.irsa_client import IRSAUnavailable

T = TypeVar("T")
_lock = Lock()
_pending: dict[tuple, Future] = {}


def run_once(key: tuple, deadline_at: float | None, work: Callable[[], T], *,
             admission: Callable[[], ContextManager] | None = None) -> T:
    if deadline_at is not None and time.monotonic() >= deadline_at:
        raise IRSAUnavailable("Request deadline expired before work could start.")
    with _lock:
        future = _pending.get(key)
        leader = future is None
        if leader:
            future = Future()
            _pending[key] = future
    if not leader:
        remaining = None if deadline_at is None else max(0.0, deadline_at - time.monotonic())
        try:
            return future.result(timeout=remaining)
        except TimeoutError as exc:
            raise IRSAUnavailable("Deadline exceeded waiting for this field's active request.") from exc
    try:
        # Only the leader consumes admission. Same-query followers still share
        # work even when all distinct-build slots are occupied.
        with admission() if admission is not None else nullcontext():
            if deadline_at is not None and time.monotonic() >= deadline_at:
                raise IRSAUnavailable("Request deadline expired before work could start.")
            result = work()
        future.set_result(result)
        return result
    except BaseException as exc:
        future.set_exception(exc)
        raise
    finally:
        with _lock:
            if _pending.get(key) is future:
                del _pending[key]
