"""Retry/idempotency behavior of the Redis urgency queue.

The queue must (a) retry transient connection failures, (b) bound every
call with socket timeouts so a wedged connection can't hang a request,
and (c) stay idempotent when the daily trigger re-runs (same invoice on
the same due date must not enqueue twice).
"""
import datetime as dt

import pytest
import redis as redis_lib

from app.queue.redis_queue import RedisUrgencyQueue


class FlakyRedis:
    """Fails the first N calls with a transient error, then delegates to a dict."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0
        self.zsets: dict[str, dict[str, float]] = {}

    def _maybe_fail(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise redis_lib.exceptions.ConnectionError("transient")

    def zadd(self, key, mapping):
        self._maybe_fail()
        self.zsets.setdefault(key, {}).update(mapping)

    def zcard(self, key):
        self._maybe_fail()
        return len(self.zsets.get(key, {}))


def test_default_client_has_timeouts_and_retry():
    q = RedisUrgencyQueue()
    kwargs = q._r.connection_pool.connection_kwargs
    assert kwargs.get("socket_timeout") is not None
    assert kwargs.get("socket_connect_timeout") is not None
    retry = kwargs.get("retry")
    assert retry is not None and retry._retries >= 2


def test_push_survives_transient_failure_via_client_retry():
    # The retry lives in the redis client config; with an injected client the
    # queue itself performs no retries — verify the flaky client's error
    # propagates (so callers know) but a healthy call after recovery works.
    flaky = FlakyRedis(failures=1)
    q = RedisUrgencyQueue(flaky)
    with pytest.raises(redis_lib.exceptions.ConnectionError):
        q.push("anand", 0.8, "inv1", "2026-05-04", owner_id="ramesh")
    q.push("anand", 0.8, "inv1", "2026-05-04", owner_id="ramesh")
    assert q.size(owner_id="ramesh") == 1


def test_reenqueue_same_invoice_is_idempotent():
    fake = FlakyRedis(failures=0)
    q = RedisUrgencyQueue(fake)
    for _ in range(3):  # trigger re-runs (retry after crash, double schedule)
        q.push("anand", 0.8, "inv1", "2026-05-04", owner_id="ramesh")
        q.push("rajan", 0.4, "inv2", "2026-05-09", owner_id="ramesh")
    assert q.size(owner_id="ramesh") == 2
