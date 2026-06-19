import datetime as dt
import os

import pytest

from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.domain.enums import InvoiceStatus
from app.domain.models import Buyer, BuyerContext, Invoice, Policy, CashUrgency
from app.llm.anthropic_client import AnthropicClient

pytestmark = pytest.mark.integration

BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
INV = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
              due_date=dt.date(2026, 5, 4), status=InvoiceStatus.OVERDUE, days_overdue=14)


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no API key")
def test_conversation_draft_is_warm_and_named():
    llm = AnthropicClient()
    ctx = BuyerContext(buyer=BUYER, invoice=INV, on_time_rate=0.82,
                       best_approach=None, history_snippets=[])
    draft = ConversationAgent(llm).draft(ctx, CashUrgency(score=0.3, breaching_need=None), thread=[])
    assert "Anand" in draft.text
    assert len(draft.text) > 20


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no API key")
def test_negotiation_plan_sums_to_invoice():
    llm = AnthropicClient()
    plan = NegotiationAgent(llm).propose(
        INV, Policy(max_extension_days=30, min_upfront_pct=30),
        CashUrgency(score=0.3, breaching_need=None),
        buyer_request="cash is tight, can I pay over a few weeks?")
    assert plan.total_paise == 240000_00
    assert plan.upfront_pct >= 30
    assert plan.extension_days <= 30
