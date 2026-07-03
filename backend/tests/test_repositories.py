import datetime as dt

import pytest

from app.db.models import OwnerRow, BuyerRow, InvoiceRow
from app.db.repositories import OwnerRepo, BuyerRepo, InvoiceRepo


@pytest.mark.db
async def test_buyer_and_invoice_lookup(session):
    session.add(OwnerRow(id="ramesh", name="Ramesh", business="SVM",
                         max_extension_days=30, min_upfront_pct=30))
    session.add(BuyerRow(id="anand", owner_id="ramesh", name="Anand Motors",
                         tier="Regular · 3 yrs", relationship_years=3.0,
                         on_time_rate=0.82, preferred_channel="WhatsApp Business"))
    session.add(InvoiceRow(id="inv1", buyer_id="anand", number="INV-2291",
                           amount_paise=240000_00, due_date=dt.date(2026, 5, 15),
                           status="overdue", days_overdue=14))
    await session.commit()

    owner = await OwnerRepo(session).get("ramesh")
    assert owner.policy.max_extension_days == 30

    buyer = await BuyerRepo(session).get("anand")
    assert buyer.on_time_rate == 0.82

    inv = await InvoiceRepo(session).latest_for_buyer("anand")
    assert inv.number == "INV-2291"
    assert inv.amount_paise == 240000_00
