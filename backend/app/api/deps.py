import datetime as dt

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.agents.orchestrator import Orchestrator
from app.channels.simulated import SimulatedChannel
from app.config import settings
from app.db.repositories import CashEventRepo
from app.db.session import get_session
from app.llm.base import LLM
from app.llm.stub import StubLLM
from app.obs.tracer import default_tracer
from app.retrieval.embedder import StubEmbedder
from app.retrieval.vector_store import PgVectorStore
from app.services.cash_calendar import CashCalendarService
from app.services.memory import MemoryService
from app.services.policy import PolicyEngine

OWNER_ID = "ramesh"


def get_llm() -> LLM:
    if settings.use_stub_llm or not settings.anthropic_api_key:
        return StubLLM(text_response="Namaste ji, a gentle reminder about your invoice.")
    from app.llm.anthropic_client import AnthropicClient
    return AnthropicClient()


async def get_orchestrator(
    session: AsyncSession = Depends(get_session),
    llm: LLM = Depends(get_llm),
) -> Orchestrator:
    store = PgVectorStore(session, StubEmbedder())
    cash_events = await CashEventRepo(session).for_owner(OWNER_ID)
    return Orchestrator(
        context_agent=ContextAgent(store),
        conversation_agent=ConversationAgent(llm),
        negotiation_agent=NegotiationAgent(llm),
        cash_service=CashCalendarService(),
        policy_engine=PolicyEngine(),
        memory=MemoryService(session, store),
        channel=SimulatedChannel(),
        tracer=default_tracer(),
        cash_events=cash_events,
        today=dt.date(2026, 5, 18),
    )
