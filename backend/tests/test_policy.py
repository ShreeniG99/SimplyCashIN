from app.domain.models import (
    Policy, PaymentPlan, PaymentInstallment, CashUrgency, Buyer,
)
from app.services.policy import PolicyEngine

POLICY = Policy(max_extension_days=30, min_upfront_pct=30)
BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")


def _plan(upfront_pct, extension_days):
    return PaymentPlan(upfront_pct=upfront_pct, extension_days=extension_days,
                       installments=[PaymentInstallment(seq=1, label="Upfront",
                                                         amount_paise=80000_00, due_offset_days=0)])


def test_compliant_plan_all_ok():
    checks = PolicyEngine().evaluate(_plan(30, 30), POLICY, CashUrgency(score=0.2, breaching_need=None), BUYER)
    assert all(c.ok for c in checks)


def test_extension_breach_flags_not_ok():
    checks = PolicyEngine().evaluate(_plan(30, 45), POLICY, CashUrgency(score=0.2, breaching_need=None), BUYER)
    ext = next(c for c in checks if "extension" in c.label.lower())
    assert ext.ok is False


def test_upfront_breach_flags_not_ok():
    checks = PolicyEngine().evaluate(_plan(15, 30), POLICY, CashUrgency(score=0.2, breaching_need=None), BUYER)
    up = next(c for c in checks if "upfront" in c.label.lower())
    assert up.ok is False


def test_high_cash_urgency_flags_not_ok():
    checks = PolicyEngine().evaluate(_plan(30, 30), POLICY,
                                     CashUrgency(score=0.8, breaching_need="₹1,20,000 due Mon"), BUYER)
    cash = next(c for c in checks if "cash" in c.label.lower())
    assert cash.ok is False
    assert "1,20,000" in cash.value
