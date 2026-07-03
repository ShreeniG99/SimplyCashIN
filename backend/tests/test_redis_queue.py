import pytest

pytestmark = pytest.mark.redis

try:
    from app.queue.redis_queue import RedisUrgencyQueue
    REDIS_IMPORTED = True
except Exception:  # pragma: no cover
    REDIS_IMPORTED = False

try:
    # test if redis server is actually running
    _q = RedisUrgencyQueue()
    _q._r.ping()
    REDIS_AVAILABLE = True
except Exception:  # pragma: no cover
    REDIS_AVAILABLE = False


@pytest.fixture
def queue():
    if not REDIS_IMPORTED or not REDIS_AVAILABLE:
        pytest.skip("redis not available")
    q = RedisUrgencyQueue()
    q.clear()
    yield q
    q.clear()


@pytest.mark.redis
def test_push_and_peek(queue):
    queue.push("anand", 0.85, "inv1", "2026-05-01")
    queue.push("rajan", 0.92, "inv2", "2026-05-02")
    items = queue.peek(k=2)
    assert len(items) == 2
    assert items[0]["buyer_id"] == "rajan"  # highest urgency first
    assert items[0]["urgency_score"] == 0.92


@pytest.mark.redis
def test_pop_removes_highest(queue):
    queue.push("anand", 0.85, "inv1", "2026-05-01")
    queue.push("rajan", 0.92, "inv2", "2026-05-02")
    popped = queue.pop()
    assert popped["buyer_id"] == "rajan"
    assert queue.size() == 1


@pytest.mark.redis
def test_empty_pop(queue):
    assert queue.pop() is None


@pytest.mark.redis
def test_remove(queue):
    queue.push("anand", 0.85, "inv1", "2026-05-01")
    queue.push("rajan", 0.92, "inv2", "2026-05-02")
    queue.remove("anand")
    assert queue.size() == 1
    items = queue.peek()
    assert items[0]["buyer_id"] == "rajan"
