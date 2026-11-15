"""Same-field concurrency and bounded waiting; no IRSA traffic."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
import time

import pytest

from services.irsa_client import IRSAUnavailable
from services.singleflight import run_once


def test_concurrent_same_key_shares_work_and_result():
    entered, release, follower_started = Event(), Event(), Event()
    lock = Lock()
    calls = []
    result = object()
    def work():
        with lock:
            calls.append(1)
        entered.set()
        assert release.wait(2)
        return result
    def follower():
        follower_started.set()
        return run_once(("same-field",), time.monotonic()+2, work)
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(run_once, ("same-field",), time.monotonic()+2, work)
        assert entered.wait(1)
        second = pool.submit(follower)
        assert follower_started.wait(1)
        time.sleep(.03)
        release.set()
        assert leader.result() is result
        assert second.result() is result
    assert calls == [1]


def test_waiter_deadline_does_not_cancel_leader_or_retain_failure():
    entered, release = Event(), Event()
    def work():
        entered.set()
        assert release.wait(2)
        return "complete"
    with ThreadPoolExecutor(max_workers=1) as pool:
        leader = pool.submit(run_once, ("wait-timeout",), time.monotonic()+2, work)
        assert entered.wait(1)
        try:
            with pytest.raises(IRSAUnavailable, match="Deadline"):
                run_once(("wait-timeout",), time.monotonic()+.02, lambda: "should not run")
        finally:
            release.set()
        assert leader.result() == "complete"
    assert run_once(("wait-timeout",), time.monotonic()+1, lambda: "new") == "new"


def test_failure_is_not_cached():
    def fail():
        raise IRSAUnavailable("controlled outage")
    with pytest.raises(IRSAUnavailable):
        run_once(("retry",), time.monotonic()+1, fail)
    assert run_once(("retry",), time.monotonic()+1, lambda: "retry success") == "retry success"


def test_expired_leader_does_not_start_work():
    calls = []
    with pytest.raises(IRSAUnavailable, match="Deadline|deadline"):
        run_once(("expired-leader",), time.monotonic()-1, lambda: calls.append(1))
    assert calls == []
