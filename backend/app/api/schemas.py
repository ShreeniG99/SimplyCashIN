from pydantic import BaseModel


class BuyerOut(BaseModel):
    id: str
    name: str
    tier: str
    amount: str          # formatted ₹
    overdue: int
    status: str
    agent: str | None
    action: str
    escalated: bool


class CheckOut(BaseModel):
    label: str
    value: str
    ok: bool


class InstallmentOut(BaseModel):
    n: int
    label: str
    amount: str
    due: str


class CycleOut(BaseModel):
    decision: str
    draft: str | None
    tone: str | None
    plan: list[InstallmentOut]
    checks: list[CheckOut]
    escalation_reason: str | None
    recommendation: str | None
    escalation_id: str | None
    urgency: float
    breaching_need: str | None


class CashDayOut(BaseModel):
    date: str
    in_dots: int
    out_dots: int


class CashItemOut(BaseModel):
    id: str
    date: str
    direction: str
    label: str
    counterparty: str
    amount: str
    done: bool


class CashCalendarOut(BaseModel):
    days: list[CashDayOut]
    week: list[CashItemOut]


class ResolveIn(BaseModel):
    action: str            # "approve" | "edit" | "override"
    text: str | None = None


class ThreadTurnOut(BaseModel):
    sender: str
    agent: str | None
    text: str
    created_at: str


class InvoiceOut(BaseModel):
    number: str
    amount: str
    amount_paise: int
    overdue: int
    status: str


class BuyerDetailOut(BaseModel):
    id: str
    name: str
    tier: str
    preferred_channel: str
    on_time_rate: float
    invoice: InvoiceOut
    thread: list[ThreadTurnOut]
    best_approach: str | None
