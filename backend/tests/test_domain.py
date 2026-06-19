import datetime as dt

from app.domain.enums import Direction, Decision, InvoiceStatus, Tone, CashEventStatus
from app.domain.models import (
    Policy, Owner, Buyer, Invoice, ConversationTurn, PaymentInstallment,
    PaymentPlan, PolicyCheck, BuyerContext, CashEvent, CashUrgency,
    DraftMessage, Escalation, MemoryRecord, CycleResult,
)


def test_payment_plan_total():
    plan = PaymentPlan(
        upfront_pct=30, extension_days=30,
        installments=[
            PaymentInstallment(seq=1, label="Upfront", amount_paise=80000_00, due_offset_days=0),
            PaymentInstallment(seq=2, label="Installment 2", amount_paise=80000_00, due_offset_days=15),
            PaymentInstallment(seq=3, label="Installment 3", amount_paise=80000_00, due_offset_days=30),
        ],
    )
    assert plan.total_paise == 240000_00


def test_cycle_result_minimal_escalation():
    buyer = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
                  relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
    inv = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
                  due_date=dt.date(2026, 5, 15), status=InvoiceStatus.OVERDUE, days_overdue=14)
    ctx = BuyerContext(buyer=buyer, invoice=inv, on_time_rate=0.82,
                       best_approach="Short extension + early-pay nudge", history_snippets=[])
    result = CycleResult(
        decision=Decision.ESCALATE, context=ctx, draft=None, plan=None,
        checks=[PolicyCheck(label="Minimum upfront (30%)", value="Buyer offered 15%", ok=False)],
        escalation=Escalation(id="e1", buyer_id="anand", amount_paise=240000_00,
                              reason="upfront too low", checks=[], recommendation="Hold firm"),
        urgency=CashUrgency(score=0.7, breaching_need="₹1,20,000 due Mon"),
    )
    assert result.decision is Decision.ESCALATE
    assert result.draft is None
