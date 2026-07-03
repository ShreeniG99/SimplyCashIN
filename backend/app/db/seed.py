import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m

OWNER_ID = "ramesh"
_TODAY = dt.date(2026, 5, 18)


async def seed(session: AsyncSession) -> None:
    session.add(m.OwnerRow(id=OWNER_ID, name="Ramesh Iyer", business="Sri Vinayaga Motors",
                           max_extension_days=30, min_upfront_pct=30))

    buyers = [
        ("anand", "Anand Motors", "Regular · 3 yrs", 3.0, 0.82, "WhatsApp Business", "overdue", 14, 240000_00, "INV-2291"),
        ("kpauto", "KP Auto Spares", "New · 2 mo", 0.2, 0.50, "SMS", "due", 6, 85000_00, "INV-2304"),
        ("sri", "Sri Lakshmi Traders", "Premium · 6 yrs", 6.0, 0.95, "WhatsApp Business", "due", 2, 110000_00, "INV-2310"),
        ("metro", "Metro Electricals", "Regular · 4 yrs", 4.0, 0.90, "Email", "paid", 0, 320000_00, "INV-2288"),
        ("rajan", "Rajan & Sons", "Regular · 5 yrs", 5.0, 0.78, "WhatsApp Business", "overdue", 9, 55000_00, "INV-2297"),
    ]
    for bid, name, tier, yrs, otr, ch, status, overdue, amt, num in buyers:
        session.add(m.BuyerRow(id=bid, owner_id=OWNER_ID, name=name, tier=tier,
                               relationship_years=yrs, on_time_rate=otr, preferred_channel=ch))
        session.add(m.InvoiceRow(id=f"inv-{bid}", buyer_id=bid, number=num, amount_paise=amt,
                                 due_date=_TODAY - dt.timedelta(days=overdue), status=status,
                                 days_overdue=overdue))

    # Anand thread (from WFDATA.thread)
    base = dt.datetime(2026, 5, 18, 10, 0)
    thread = [
        ("agent", "context", "Retrieved buyer history: 3 yrs, usually pays in 10–12 days. Last delay settled with a short extension."),
        ("agent", "conversation", "Namaste Anand ji, hope business is good. A gentle reminder that invoice #INV-2291 for ₹2,40,000 is now past due. Could you share when we can expect it?"),
        ("buyer", None, "Sorry Ramesh, cash is tight this month. Can I pay over a few weeks?"),
    ]
    for i, (sender, agent, txt) in enumerate(thread):
        session.add(m.ConversationTurnRow(id=f"t-anand-{i}", buyer_id="anand", sender=sender,
                                          agent=agent, text=txt,
                                          created_at=base + dt.timedelta(hours=i)))

    # Cash calendar (from WFDATA.cashCalendar) — direction in/out
    cash = [
        ("ce1", "in", _TODAY, "Anand Motors", 40000_00, "Expected from Anand", "pending"),
        ("ce2", "out", _TODAY, "GST + supplier", 120000_00, "GST + supplier payment", "pending"),
        ("ce3", "in", _TODAY + dt.timedelta(days=1), "KP Auto", 90000_00, "Expected from KP Auto", "pending"),
        ("ce4", "in", _TODAY + dt.timedelta(days=2), "Sri Lakshmi", 150000_00, "Expected from Sri Lakshmi", "pending"),
        ("ce5", "out", _TODAY + dt.timedelta(days=3), "Wages", 80000_00, "Staff wages", "pending"),
        ("ce6", "in", _TODAY + dt.timedelta(days=4), "Rajan & Sons", 120000_00, "Expected from Rajan", "pending"),
    ]
    for cid, direction, due, cp, amt, label, status in cash:
        session.add(m.CashEventRow(id=cid, owner_id=OWNER_ID, direction=direction, due_date=due,
                                   counterparty=cp, amount_paise=amt, label=label, status=status))

    await session.commit()
