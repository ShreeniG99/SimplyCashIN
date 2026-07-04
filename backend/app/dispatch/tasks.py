import asyncio

from app.dispatch.celery_app import celery
from app.queue.redis_queue import RedisUrgencyQueue


@celery.task(name="scin.dispatch_cycle")
def dispatch_cycle(owner_id: str, buyer_id: str) -> dict:
    from app.dispatch.runner import run_buyer_cycle
    return asyncio.run(run_buyer_cycle(owner_id, buyer_id))


@celery.task(name="scin.drain_queue")
def drain_queue(owner_id: str) -> dict:
    """Pop every queued (buyer, invoice) for the owner and fan out one
    dispatch_cycle task each — highest urgency first (zpopmax order)."""
    q = RedisUrgencyQueue()
    drained = 0
    while (item := q.pop(owner_id=owner_id)) is not None:
        dispatch_cycle.delay(owner_id, item["buyer_id"])
        drained += 1
    return {"owner_id": owner_id, "drained": drained}
