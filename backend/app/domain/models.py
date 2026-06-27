import datetime as dt
from typing import Literal

from pydantic import BaseModel

from app.domain.enums import (
    CashEventStatus, Decision, Direction, InvoiceStatus, JobStatus, IngestionSource, Tone,
)


class Policy(BaseModel):
    max_extension_days: int
    min_upfront_pct: int


class Owner(BaseModel):
    id: str
    name: str
    business: str
    policy: Policy


class Buyer(BaseModel):
    id: str
    owner_id: str
    name: str
    tier: str
    relationship_years: float
    on_time_rate: float
    preferred_channel: str


class Invoice(BaseModel):
    id: str
    buyer_id: str
    number: str
    amount_paise: int
    due_date: dt.date
    status: InvoiceStatus
    days_overdue: int


class ConversationTurn(BaseModel):
    id: str
    buyer_id: str
    sender: Literal["agent", "buyer"]
    agent: str | None = None
    text: str
    created_at: dt.datetime


class PaymentInstallment(BaseModel):
    seq: int
    label: str
    amount_paise: int
    due_offset_days: int


class PaymentPlan(BaseModel):
    upfront_pct: int
    extension_days: int
    installments: list[PaymentInstallment]

    @property
    def total_paise(self) -> int:
        return sum(i.amount_paise for i in self.installments)


class PolicyCheck(BaseModel):
    label: str
    value: str
    ok: bool


class BuyerContext(BaseModel):
    buyer: Buyer
    invoice: Invoice
    on_time_rate: float
    best_approach: str | None
    history_snippets: list[str]


class CashEvent(BaseModel):
    id: str
    owner_id: str
    direction: Direction
    due_date: dt.date
    counterparty: str
    amount_paise: int
    label: str
    status: CashEventStatus


class CashUrgency(BaseModel):
    score: float
    breaching_need: str | None


class DraftMessage(BaseModel):
    text: str
    tone: Tone


class Escalation(BaseModel):
    id: str
    buyer_id: str
    amount_paise: int
    reason: str
    checks: list[PolicyCheck]
    recommendation: str


class MemoryRecord(BaseModel):
    buyer_id: str
    tone: Tone
    plan: PaymentPlan | None
    timing: str
    paid: bool


class CycleResult(BaseModel):
    decision: Decision
    context: BuyerContext
    draft: DraftMessage | None
    plan: PaymentPlan | None
    checks: list[PolicyCheck]
    escalation: Escalation | None
    urgency: CashUrgency


class IngestionJob(BaseModel):
    id: str
    owner_id: str
    source: IngestionSource
    status: JobStatus
    total_rows: int | None = None
    imported_rows: int | None = None
    error_message: str | None = None
    created_at: dt.datetime
    completed_at: dt.datetime | None = None


class QueuedItem(BaseModel):
    buyer_id: str
    invoice_id: str
    urgency_score: float
    due_date: dt.date
