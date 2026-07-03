import datetime as dt

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent, NegotiationPlanOut
from app.agents.orchestrator import Orchestrator, needs_negotiation
from app.channels.simulated import SimulatedChannel
from app.domain.enums import Decision, InvoiceStatus
from app.domain.models import (
    Buyer, ConversationTurn, Invoice, Owner, Policy, CashEvent,
)
from app.domain.enums import CashEventStatus, Direction
from app.llm.stub import StubLLM
from app.obs.tracer import RecordingTracer
from app.services.cash_calendar import CashCalendarService
from app.services.policy import PolicyEngine

TODAY = dt.date(2026, 5, 18)
OWNER = Owner(id="ramesh", name="Ramesh", business="SVM",
              policy=Policy(max_extension_days=30, min_upfront_pct=30))
BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
INV = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
              due_date=dt.date(2026, 5, 4), status=InvoiceStatus.OVERDUE, days_overdue=14)


class FakeStore:
    async def search(self, buyer_id, query, k=3):
        return []


class FakeMemory:
    def __init__(self):
        self.records = []

    async def record_outcome(self, **kw):
        self.records.append(kw)


def _turn(sender, text):
    return ConversationTurn(id="t", buyer_id="anand", sender=sender, agent=None,
                            text=text, created_at=dt.datetime(2026, 5, 18, 10))


def _good_plan_llm():
    out = NegotiationPlanOut(upfront_pct=30, extension_days=30, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 80000_00, "due_offset_days": 0},
        {"seq": 2, "label": "I2", "amount_paise": 80000_00, "due_offset_days": 15},
        {"seq": 3, "label": "I3", "amount_paise": 80000_00, "due_offset_days": 30},
    ])
    return StubLLM(text_response="Namaste Anand ji.", structured_response=out)


def _bad_plan_llm():
    out = NegotiationPlanOut(upfront_pct=15, extension_days=45, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 36000_00, "due_offset_days": 0},
        {"seq": 2, "label": "I2", "amount_paise": 204000_00, "due_offset_days": 45},
    ])
    return StubLLM(text_response="Namaste Anand ji.", structured_response=out)


def _orchestrator(llm, cash_events, memory):
    return Orchestrator(
        context_agent=ContextAgent(FakeStore()),
        conversation_agent=ConversationAgent(llm),
        negotiation_agent=NegotiationAgent(llm),
        cash_service=CashCalendarService(),
        policy_engine=PolicyEngine(),
        memory=memory,
        channel=SimulatedChannel(),
        tracer=RecordingTracer(),
        cash_events=cash_events,
        today=TODAY,
    )


def test_needs_negotiation_detects_request():
    assert needs_negotiation([_turn("buyer", "cash is tight, can I pay over a few weeks?")]) is True
    assert needs_negotiation([_turn("buyer", "payment done, thanks")]) is False
    assert needs_negotiation([]) is False


async def test_compliant_plan_acts_and_dispatches():
    mem = FakeMemory()
    orch = _orchestrator(_good_plan_llm(), cash_events=[], memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ACT
    assert orch.channel.sent and "Namaste" in orch.channel.sent[0]["message"]
    assert mem.records and mem.records[0]["paid"] is False


async def test_policy_breach_escalates_without_sending():
    mem = FakeMemory()
    orch = _orchestrator(_bad_plan_llm(), cash_events=[], memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ESCALATE
    assert result.escalation is not None
    assert orch.channel.sent == []          # nothing sent on escalation


async def test_high_cash_urgency_escalates_even_with_compliant_plan():
    mem = FakeMemory()
    urgent = [CashEvent(id="ce", owner_id="ramesh", direction=Direction.OUT, due_date=TODAY,
                        counterparty="GST", amount_paise=200000_00, label="GST",
                        status=CashEventStatus.PENDING)]
    orch = _orchestrator(_good_plan_llm(), cash_events=urgent, memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ESCALATE


async def test_llm_failure_escalates():
    mem = FakeMemory()
    orch = _orchestrator(StubLLM(raise_error=True), cash_events=[], memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ESCALATE
    assert "could not complete" in result.escalation.reason.lower()
