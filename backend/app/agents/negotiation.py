from pydantic import BaseModel

from app.domain.models import (
    CashUrgency, Invoice, PaymentInstallment, PaymentPlan, Policy,
)
from app.llm.base import LLM
from app.money import format_inr


class _InstallmentOut(BaseModel):
    seq: int
    label: str
    amount_paise: int
    due_offset_days: int


class NegotiationPlanOut(BaseModel):
    upfront_pct: int
    extension_days: int
    installments: list[_InstallmentOut]


_SYSTEM = """You are SimplyCashIN's Negotiation agent. Propose a payment plan for an \
overdue invoice. Respect the owner's policy (minimum upfront %, maximum extension days) \
AND the owner's cash urgency: when urgency is high, demand more upfront and a shorter \
extension. Installment amounts must sum to the full invoice amount (in paise). Return \
ONLY the structured plan."""


class NegotiationAgent:
    def __init__(self, llm: LLM):
        self.llm = llm

    def propose(self, invoice: Invoice, policy: Policy, urgency: CashUrgency,
                buyer_request: str) -> PaymentPlan:
        user = (
            f"Invoice {invoice.number}: {format_inr(invoice.amount_paise)} "
            f"({invoice.amount_paise} paise), {invoice.days_overdue} days overdue.\n"
            f"Owner policy: min upfront {policy.min_upfront_pct}%, "
            f"max extension {policy.max_extension_days} days.\n"
            f"Owner cash urgency: {urgency.score:.2f}.\n"
            f"Buyer request: {buyer_request!r}.\n"
            f"Propose a plan whose installments sum to {invoice.amount_paise} paise."
        )
        out = self.llm.complete_structured(_SYSTEM, user, NegotiationPlanOut)
        return PaymentPlan(
            upfront_pct=out.upfront_pct,
            extension_days=out.extension_days,
            installments=[PaymentInstallment(seq=i.seq, label=i.label,
                                             amount_paise=i.amount_paise,
                                             due_offset_days=i.due_offset_days)
                          for i in out.installments],
        )
