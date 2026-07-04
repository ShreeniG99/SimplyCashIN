import datetime as dt

import pytest

from app.scheduler.daily import DailyOverdueTrigger, build_scheduler

TODAY = dt.date(2026, 5, 18)


def test_build_scheduler_registers_daily_job():
    def _factory():  # never called — job must not run here
        raise AssertionError("job ran during registration")

    scheduler = build_scheduler(_factory)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "daily-overdue-trigger"
    # cron trigger fires once a day
    assert "cron" in str(type(jobs[0].trigger)).lower()


@pytest.mark.db
@pytest.mark.redis
async def test_daily_trigger_enqueues_overdue_buyers(session, engine):
    from app.db.seed import seed
    from app.db.session import make_session_factory
    from app.queue.redis_queue import RedisUrgencyQueue

    try:
        queue = RedisUrgencyQueue()
        queue._r.ping()
    except Exception:
        pytest.skip("redis not available")

    await seed(session)
    queue.clear(owner_id="ramesh")
    try:
        trigger = DailyOverdueTrigger(make_session_factory(engine))
        result = await trigger.run(owner_id="ramesh", today=TODAY)

        # seed has two overdue invoices: anand (14d) and rajan (9d)
        assert result["processed"] == 2
        assert queue.size(owner_id="ramesh") == 2
        items = queue.peek(k=2, owner_id="ramesh")
        assert {i["buyer_id"] for i in items} == {"anand", "rajan"}
    finally:
        queue.clear(owner_id="ramesh")
