import datetime as dt
import uuid

from sqlalchemy import select

from app.db import models as m
from app.db.repositories import CashEventRepo
from app.domain.enums import InvoiceStatus
from app.queue.redis_queue import RedisUrgencyQueue
from app.services.cash_calendar import CashCalendarService


class DailyOverdueTrigger:
    """APScheduler job that runs daily, finds overdue invoices,
    computes urgency, and pushes to Redis sorted-set."""

    def __init__(self, session_factory, redis_client=None) -> None:
        self._sf = session_factory
        self._cash = CashCalendarService()
        self._queue = RedisUrgencyQueue(redis_client)

    async def run(self, owner_id: str = "ramesh", today: dt.date | None = None) -> dict:
        today = today or dt.date.today()
        run_id = str(uuid.uuid4())

        async with self._sf() as session:
            # Fetch overdue invoices with buyer
            rows = await session.execute(
                select(m.InvoiceRow, m.BuyerRow)
                .join(m.BuyerRow, m.InvoiceRow.buyer_id == m.BuyerRow.id)
                .where(m.InvoiceRow.status == InvoiceStatus.OVERDUE.value))

            # Compute urgency from owner's cash events
            repo = CashEventRepo(session)
            events = await repo.for_owner(owner_id)
            urgency = self._cash.urgency(events, today)

            processed = 0
            for inv_row, buyer_row in rows.all():
                self._queue.push(
                    buyer_id=buyer_row.id,
                    urgency_score=urgency.score,
                    invoice_id=inv_row.id,
                    due_date=inv_row.due_date.isoformat(),
                )
                processed += 1

        return {
            "run_id": run_id,
            "owner_id": owner_id,
            "date": today.isoformat(),
            "processed": processed,
            "urgency_score": urgency.score,
        }
