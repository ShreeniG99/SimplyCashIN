import datetime as dt
import uuid
from typing import Protocol

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.channels.base import Channel
from app.domain.enums import Decision, Tone
from app.domain.models import (
    Buyer, CashEvent, ConversationTurn, CycleResult, DraftMessage, Escalation,
    Invoice, Owner,
)
from app.llm.base import LLMError
from app.money import format_inr
from app.obs.tracer import Tracer
from app.services.cash_calendar import CashCalendarService
from app.services.policy import PolicyEngine

_REQUEST_KEYWORDS = ("more time", "cash is tight", "pay over", "installment",
                     "few weeks", "extension", "can i pay", "part payment")


def needs_negotiation(thread: list[ConversationTurn]) -> bool:
    if not thread:
        return False
    last = thread[-1]
    if last.sender != "buyer":
        return False
    text = last.text.lower()
    return any(k in text for k in _REQUEST_KEYWORDS)


class _Memory(Protocol):
    async def record_outcome(self, *, buyer_id: str, tone: Tone, plan, timing: str,
                             paid: bool) -> None: ...


class Orchestrator:
    def __init__(self, *, context_agent: ContextAgent, conversation_agent: ConversationAgent,
                 negotiation_agent: NegotiationAgent, cash_service: CashCalendarService,
                 policy_engine: PolicyEngine, memory: _Memory, channel: Channel,
                 tracer: Tracer, cash_events: list[CashEvent], today: dt.date):
        self.context_agent = context_agent
        self.conversation_agent = conversation_agent
        self.negotiation_agent = negotiation_agent
        self.cash_service = cash_service
        self.policy_engine = policy_engine
        self.memory = memory
        self.channel = channel
        self.tracer = tracer
        self.cash_events = cash_events
        self.today = today

    async def run_cycle(self, owner: Owner, buyer: Buyer, invoice: Invoice,
                        thread: list[ConversationTurn]) -> CycleResult:
        context = await self.context_agent.build(buyer, invoice)
        urgency = self.cash_service.urgency(self.cash_events, self.today)

        try:
            draft = self.conversation_agent.draft(context, urgency, thread)
            plan = None
            checks = []
            if needs_negotiation(thread):
                plan = self.negotiation_agent.propose(
                    invoice, owner.policy, urgency, buyer_request=thread[-1].text)
                checks = self.policy_engine.evaluate(plan, owner.policy, urgency, buyer)
        except LLMError:
            return self._escalate(
                owner, buyer, invoice, context, urgency, draft=None, plan=None, checks=[],
                reason="An agent could not complete this cycle — needs your attention.",
                recommendation="Review and follow up manually.")

        decision = Decision.ACT if all(c.ok for c in checks) else Decision.ESCALATE

        if decision is Decision.ACT:
            self.channel.send(buyer_id=buyer.id, message=draft.text,
                              channel_kind=buyer.preferred_channel)
            await self.memory.record_outcome(
                buyer_id=buyer.id, tone=draft.tone, plan=plan,
                timing=f"day {invoice.days_overdue}", paid=False)
            self.tracer.trace(agent="orchestrator", model="-", prompt=buyer.id,
                              response="ACT",
                              meta={"owner_id": owner.id, "decision": "act"})
            return CycleResult(decision=decision, context=context, draft=draft, plan=plan,
                               checks=checks, escalation=None, urgency=urgency)

        failed = [c for c in checks if not c.ok]
        reason = "; ".join(f"{c.label}: {c.value}" for c in failed)
        recommendation = ("Hold firm — request more upfront and a shorter extension, "
                          "or escalate only the balance.")
        return self._escalate(owner, buyer, invoice, context, urgency, draft=draft,
                              plan=plan, checks=checks, reason=reason,
                              recommendation=recommendation)

    def _escalate(self, owner, buyer, invoice, context, urgency, *, draft: DraftMessage | None,
                  plan, checks, reason: str, recommendation: str) -> CycleResult:
        escalation = Escalation(id=str(uuid.uuid4()), buyer_id=buyer.id,
                                amount_paise=invoice.amount_paise, reason=reason,
                                checks=checks, recommendation=recommendation)
        self.tracer.trace(agent="orchestrator", model="-", prompt=buyer.id,
                          response="ESCALATE",
                          meta={"owner_id": owner.id, "decision": "escalate", "reason": reason})
        return CycleResult(decision=Decision.ESCALATE, context=context, draft=draft, plan=plan,
                           checks=checks, escalation=escalation, urgency=urgency)
