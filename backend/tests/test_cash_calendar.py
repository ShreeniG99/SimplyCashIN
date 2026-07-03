import datetime as dt

from app.domain.enums import CashEventStatus, Direction
from app.domain.models import CashEvent
from app.services.cash_calendar import CashCalendarService

TODAY = dt.date(2026, 5, 18)


def _evt(direction, days, amt, status=CashEventStatus.PENDING, cp="x"):
    return CashEvent(id=f"{direction}-{days}-{amt}", owner_id="ramesh",
                     direction=direction, due_date=TODAY + dt.timedelta(days=days),
                     counterparty=cp, amount_paise=amt, label=cp, status=status)


def test_no_outgoing_means_zero_urgency():
    events = [_evt(Direction.IN, 1, 90000_00)]
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score == 0.0
    assert u.breaching_need is None


def test_uncovered_outgoing_drives_high_urgency():
    events = [_evt(Direction.OUT, 0, 120000_00, cp="GST")]  # due today, no incoming
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score >= 0.8           # fully uncovered + due-today proximity boost
    assert "GST" in u.breaching_need


def test_incoming_covers_outgoing_lowers_urgency():
    events = [_evt(Direction.OUT, 5, 100000_00, cp="Wages"),
              _evt(Direction.IN, 1, 150000_00)]
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score == 0.0           # incoming fully covers, no proximity (5 days out)


def test_done_events_ignored():
    events = [_evt(Direction.OUT, 0, 120000_00, status=CashEventStatus.DONE, cp="GST")]
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score == 0.0
