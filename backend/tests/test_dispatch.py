import pytest

from app.channels.base import DispatchResult
from app.channels.simulated import SimulatedChannel
from app.db.seed import seed
from app.db.session import make_session_factory
from app.dispatch.runner import run_buyer_cycle
from app.llm.stub import StubLLM


@pytest.mark.db
async def test_runner_acts_for_rajan(session, engine):
    await seed(session)
    ch = SimulatedChannel()
    out = await run_buyer_cycle(
        "ramesh", "rajan", session_factory=make_session_factory(engine),
        llm=StubLLM(text_response="Gentle reminder about INV-2297."), channel=ch)
    assert out["decision"] == "act"
    assert ch.sent and ch.sent[0]["buyer_id"] == "rajan"


@pytest.mark.db
async def test_runner_escalates_and_persists_for_anand(session, engine):
    # anand's thread asks for time; StubLLM has no structured plan -> LLMError -> escalate
    await seed(session)
    out = await run_buyer_cycle(
        "ramesh", "anand", session_factory=make_session_factory(engine),
        llm=StubLLM(text_response="Namaste Anand ji."), channel=SimulatedChannel())
    assert out["decision"] == "escalate"
    assert out["escalation_id"]

    from sqlalchemy import select
    from app.db.models import EscalationRow
    row = (await session.execute(select(EscalationRow).where(
        EscalationRow.id == out["escalation_id"]))).scalar_one()
    assert row.buyer_id == "anand"


class _AlwaysDown:
    def __init__(self):
        self.calls = 0

    def send(self, **kw):
        self.calls += 1
        return DispatchResult(ok=False, detail="503 from provider", transient=True)


@pytest.mark.db
async def test_runner_escalates_after_retry_exhaustion(session, engine):
    await seed(session)
    down = _AlwaysDown()
    out = await run_buyer_cycle(
        "ramesh", "rajan", session_factory=make_session_factory(engine),
        llm=StubLLM(text_response="Reminder."), channel=down)
    assert down.calls == 3  # max retries before giving up
    assert out["decision"] == "escalate"
    assert out["escalation_id"]


@pytest.mark.redis
def test_drain_queue_fans_out_by_urgency(monkeypatch):
    from app.dispatch import tasks
    from app.queue.redis_queue import RedisUrgencyQueue

    try:
        q = RedisUrgencyQueue()
        q._r.ping()
    except Exception:
        pytest.skip("redis not available")

    q.clear(owner_id="t-dispatch")
    q.push("anand", 0.9, "inv-anand", "2026-05-04", owner_id="t-dispatch")
    q.push("rajan", 0.8, "inv-rajan", "2026-05-09", owner_id="t-dispatch")
    calls = []
    monkeypatch.setattr(tasks.dispatch_cycle, "delay", lambda *a: calls.append(a))

    out = tasks.drain_queue("t-dispatch")

    assert out["drained"] == 2
    assert [c[1] for c in calls] == ["anand", "rajan"]  # highest urgency first
    assert q.size(owner_id="t-dispatch") == 0


@pytest.mark.db
@pytest.mark.redis
async def test_scheduler_hands_off_to_celery_once(session, engine, monkeypatch):
    import datetime as dt

    from app.config import settings
    from app.dispatch import tasks
    from app.queue.redis_queue import RedisUrgencyQueue
    from app.scheduler.daily import DailyOverdueTrigger

    try:
        queue = RedisUrgencyQueue()
        queue._r.ping()
    except Exception:
        pytest.skip("redis not available")

    await seed(session)
    queue.clear(owner_id="ramesh")
    drains = []
    monkeypatch.setattr(settings, "enable_celery_dispatch", True)
    monkeypatch.setattr(tasks.drain_queue, "delay", lambda *a: drains.append(a))
    try:
        result = await DailyOverdueTrigger(make_session_factory(engine)).run(
            owner_id="ramesh", today=dt.date(2026, 5, 18))
        assert result["dispatched_via"] == "celery"
        assert drains == [("ramesh",)]  # exactly one hand-off, not one per invoice
    finally:
        queue.clear(owner_id="ramesh")
