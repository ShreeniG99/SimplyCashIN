import datetime as dt

from app.domain.enums import CashEventStatus, Direction
from app.domain.models import CashEvent, CashUrgency
from app.money import format_inr

WEEK_DAYS = 7
PROXIMITY_DAYS = 2
PROXIMITY_BOOST = 0.2


class CashCalendarService:
    def urgency(self, events: list[CashEvent], today: dt.date) -> CashUrgency:
        week_end = today + dt.timedelta(days=WEEK_DAYS)

        def in_week(e: CashEvent) -> bool:
            return (e.status == CashEventStatus.PENDING
                    and today <= e.due_date <= week_end)

        outs = [e for e in events if e.direction == Direction.OUT and in_week(e)]
        ins = [e for e in events if e.direction == Direction.IN and in_week(e)]

        out_total = sum(e.amount_paise for e in outs)
        in_total = sum(e.amount_paise for e in ins)

        if out_total == 0:
            return CashUrgency(score=0.0, breaching_need=None)

        coverage_gap = max(0, out_total - in_total)
        base = coverage_gap / out_total
        soon = any(e.due_date <= today + dt.timedelta(days=PROXIMITY_DAYS) for e in outs)
        boost = PROXIMITY_BOOST if (soon and base > 0) else 0.0
        score = min(1.0, base + boost)

        nearest = min(outs, key=lambda e: (e.due_date, -e.amount_paise))
        need = f"{format_inr(nearest.amount_paise)} to {nearest.counterparty} due {nearest.due_date:%a}"
        return CashUrgency(score=score, breaching_need=need)
