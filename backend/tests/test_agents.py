import datetime as dt

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent, NegotiationPlanOut
from app.domain.enums import InvoiceStatus, Tone
from app.domain.models import (
    Buyer, BuyerContext, Invoice, Policy, CashUrgency,
)
from app.llm.stub import StubLLM

BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
INV = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
              due_date=dt.date(2026, 5, 15), status=InvoiceStatus.OVERDUE, days_overdue=14)


class FakeStore:
    async def search(self, buyer_id, query, k=3):
        return ["gentle message at day 7 — paid"]


async def test_context_agent_builds_context():
    ctx = await ContextAgent(FakeStore()).build(BUYER, INV)
    assert ctx.on_time_rate == 0.82
    assert ctx.history_snippets == ["gentle message at day 7 — paid"]


def test_conversation_agent_returns_draft():
    llm = StubLLM(text_response="Namaste Anand ji, hope business is good.")
    ctx = BuyerContext(buyer=BUYER, invoice=INV, on_time_rate=0.82,
                       best_approach=None, history_snippets=[])
    draft = ConversationAgent(llm).draft(ctx, CashUrgency(score=0.2, breaching_need=None), thread=[])
    assert "Namaste" in draft.text
    assert draft.tone in (Tone.GENTLE, Tone.FIRM)
    # system prompt must carry the brand voice
    assert "never" in llm.calls[0][1].lower()


def test_negotiation_agent_returns_plan():
    out = NegotiationPlanOut(upfront_pct=30, extension_days=30, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 80000_00, "due_offset_days": 0},
        {"seq": 2, "label": "Installment 2", "amount_paise": 80000_00, "due_offset_days": 15},
        {"seq": 3, "label": "Installment 3", "amount_paise": 80000_00, "due_offset_days": 30},
    ])
    llm = StubLLM(structured_response=out)
    plan = NegotiationAgent(llm).propose(
        INV, Policy(max_extension_days=30, min_upfront_pct=30),
        CashUrgency(score=0.2, breaching_need=None), buyer_request="can I pay over a few weeks")
    assert plan.upfront_pct == 30
    assert plan.total_paise == 240000_00
