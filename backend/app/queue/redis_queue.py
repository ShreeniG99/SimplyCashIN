import json
from typing import Protocol

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.config import settings


class UrgencyQueue(Protocol):
    """Protocol for a priority queue sorted by urgency score."""

    def push(self, buyer_id: str, urgency_score: float, invoice_id: str, due_date: str) -> None: ...

    def pop(self) -> dict | None: ...

    def peek(self, k: int = 5) -> list[dict]: ...

    def remove(self, buyer_id: str) -> None: ...

    def size(self) -> int: ...


class RedisUrgencyQueue:
    """Redis sorted-set (zadd/zpopmax) backed urgency queue, namespaced per owner."""

    KEY = "scin:urgency:{owner_id}"

    def __init__(self, client: redis.Redis | None = None) -> None:
        # Bounded timeouts + retry with backoff: a wedged connection must not
        # hang a request, and transient blips must not fail a daily run.
        # Idempotency note: members are keyed by (buyer, invoice, due_date),
        # so zadd makes re-running the trigger a no-op, not a duplicate.
        self._r = client or redis.from_url(
            settings.redis_url or "redis://localhost:6379/0",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry=Retry(ExponentialBackoff(cap=2, base=0.1), retries=3),
            retry_on_error=[redis.exceptions.ConnectionError,
                            redis.exceptions.TimeoutError],
        )

    def _key(self, owner_id: str = "default") -> str:
        return self.KEY.format(owner_id=owner_id)

    def push(self, buyer_id: str, urgency_score: float, invoice_id: str, due_date: str,
             *, owner_id: str = "default") -> None:
        item = json.dumps({"buyer_id": buyer_id, "invoice_id": invoice_id, "due_date": due_date})
        self._r.zadd(self._key(owner_id), {item: urgency_score})

    def pop(self, *, owner_id: str = "default") -> dict | None:
        result = self._r.zpopmax(self._key(owner_id), 1)
        if not result:
            return None
        item, score = result[0]
        data = json.loads(item)
        data["urgency_score"] = float(score)
        return data

    def peek(self, k: int = 5, *, owner_id: str = "default") -> list[dict]:
        items = self._r.zrevrange(self._key(owner_id), 0, k - 1, withscores=True)
        out: list[dict] = []
        for item, score in items:
            data = json.loads(item)
            data["urgency_score"] = float(score)
            out.append(data)
        return out

    def remove(self, buyer_id: str, *, owner_id: str = "default") -> None:
        for member, score in self._r.zscan_iter(self._key(owner_id)):
            data = json.loads(member)
            if data.get("buyer_id") == buyer_id:
                self._r.zrem(self._key(owner_id), member)
                break

    def size(self, *, owner_id: str = "default") -> int:
        return int(self._r.zcard(self._key(owner_id)))

    def clear(self, *, owner_id: str = "default") -> None:
        self._r.delete(self._key(owner_id))
