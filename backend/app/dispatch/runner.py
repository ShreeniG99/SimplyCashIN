import datetime as dt

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.agents.orchestrator import Orchestrator
from app.channels.factory import get_channel
from app.channels.retry import RetryingChannel
from app.db.repositories import (
    BuyerRepo, CashEventRepo, ConversationRepo, EscalationRepo, InvoiceRepo, OwnerRepo,
)
from app.obs.tracer import default_tracer
from app.retrieval.embedder import StubEmbedder
from app.retrieval.vector_store import PgVectorStore
from app.services.cash_calendar import CashCalendarService
from app.services.memory import MemoryService
from app.services.policy import PolicyEngine

DEMO_TODAY = dt.date(2026, 5, 18)


async def run_buyer_cycle(owner_id: str, buyer_id: str, *, session_factory=None,
                          llm=None, channel=None, today: dt.date = DEMO_TODAY) -> dict:
    """Run one collection cycle outside the API process (Celery worker).

    Mirrors POST /buyers/{id}/run-cycle persistence; the channel is wrapped in
    RetryingChannel so transient send failures retry with backoff and exhaustion
    lands as an escalation via the Orchestrator's existing dispatch-failure path.
    """
    if session_factory is None:
        from app.db.session import SessionFactory
        session_factory = SessionFactory
    if llm is None:
        from app.api.deps import get_llm
        llm = get_llm()

    async with session_factory() as session:
        owner = await OwnerRepo(session).get(owner_id)
        buyer = await BuyerRepo(session).get(buyer_id)
        invoice = await InvoiceRepo(session).latest_for_buyer(buyer_id, today=today)
        thread = await ConversationRepo(session).thread_for_buyer(buyer_id)
        store = PgVectorStore(session, StubEmbedder())
        cash_events = await CashEventRepo(session).for_owner(owner_id)

        orchestrator = Orchestrator(
            context_agent=ContextAgent(store),
            conversation_agent=ConversationAgent(llm),
            negotiation_agent=NegotiationAgent(llm),
            cash_service=CashCalendarService(),
            policy_engine=PolicyEngine(),
            memory=MemoryService(session, store),
            channel=RetryingChannel(channel or get_channel()),
            tracer=default_tracer(),
            cash_events=cash_events,
            today=today,
        )
        result = await orchestrator.run_cycle(owner, buyer, invoice, thread)
        await session.commit()

        if result.escalation:
            await EscalationRepo(session).save(
                result.escalation,
                draft_text=result.draft.text if result.draft else None,
                draft_tone=result.draft.tone.value if result.draft else None,
                channel_kind=buyer.preferred_channel)
            await session.commit()

        return {"owner_id": owner_id, "buyer_id": buyer_id,
                "decision": result.decision.value,
                "escalation_id": result.escalation.id if result.escalation else None}
