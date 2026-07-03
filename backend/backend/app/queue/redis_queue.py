import json
from typing import Protocol

import redis

from app.config import settings


class UrgencyQueue(Protocol):
    """Protocol for a priority queue sorted by urgency score."""

    def push(self, buyer_id: str, urgency_score: float, invoice_id: str, due_date: str) -> None: ...

    def pop(self) -> dict | None: ...

    def peek(self, k: int = 5) -> list[dict]: ...

    def remove(self, buyer_id: str) -> None: ...

    def size(self) -> int: ...


class RedisUrgencyQueue:
    """Redis sorted-set (zadd/zpopmax) backed urgency queue."""

    def __init__(self, client: redis.Redis | None = None) -> None:
        self._r = client or redis.from_url(
            settings.redis_url or "redis://localhost:6379/0", decode_responses=True
        )

    def push(self, buyer_id: str, urgency_score: float, invoice_id: str, due_date: str) -> None:
        item = json.dumps({"buyer_id": buyer_id, "invoice_id": invoice_id, "due_date": due_date})
        self._r.zadd("scin:urgency", {item: urgency_score})

    def pop(self) -> dict | None:
        result = self._r.zpopmax("scin:urgency", 1)
        if not result:
            return None
        item, score = result[0]
        data = json.loads(item)
        data["urgency_score"] = float(score)
        return data

    def peek(self, k: int = 5) -> list[dict]:
        items = self._r.zrevrange("scin:urgency", 0, k - 1, withscores=True)
        out: list[dict] = []
        for item, score in items:
            data = json.loads(item)
            data["urgency_score"] = float(score)
            out.append(data)
        return out

    def remove(self, buyer_id: str) -> None:
        # Scan and remove by buyer_id (inefficient on large sets but OK for M2)
        for member, score in self._r.zscan_iter("scin:urgency"):
            data = json.loads(member)
            if data.get("buyer_id") == buyer_id:
                self._r.zrem("scin:urgency", member)
                break

    def size(self) -> int:
        return int(self._r.zcard("scin:urgency"))

    def clear(self) -> None:
        self._r.delete("scin:urgency")
