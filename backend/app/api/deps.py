import datetime as dt

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.agents.orchestrator import Orchestrator
from app.channels.factory import get_channel
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

DEV_OWNER_ID = "ramesh"


def owner_from_token(token: str | None) -> str:
    """Resolve owner identity from a Supabase-issued HS256 JWT (`sub` claim).
    With SUPABASE_JWT_SECRET unset (dev/tests/demo), everything resolves to
    the seeded owner so M1–M3 flows run unchanged."""
    if not settings.supabase_jwt_secret:
        return DEV_OWNER_ID
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    import jwt
    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret,
                             algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")
    owner_id = payload.get("sub")
    if not owner_id:
        raise HTTPException(status_code=401, detail="token missing sub claim")
    return owner_id


async def get_owner_id(authorization: str | None = Header(default=None)) -> str:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    return owner_from_token(token)


def get_llm() -> LLM:
    if settings.use_stub_llm or not settings.anthropic_api_key:
        # Deterministic demo persona (no API key): a warm draft plus a structured
        # plan that BREACHES policy (15% upfront, 45-day extension) so the
        # Orchestrator runs real policy checks and escalates — the wireframe's
        # hero HITL scenario. Add ANTHROPIC_API_KEY for genuine agent proposals.
        from app.agents.negotiation import NegotiationPlanOut
        demo_plan = NegotiationPlanOut(
            upfront_pct=15, extension_days=45,
            installments=[
                {"seq": 1, "label": "Upfront on confirm", "amount_paise": 36000_00, "due_offset_days": 0},
                {"seq": 2, "label": "Installment 2", "amount_paise": 102000_00, "due_offset_days": 21},
                {"seq": 3, "label": "Installment 3", "amount_paise": 102000_00, "due_offset_days": 45},
            ],
        )
        return StubLLM(
            text_response=(
                "Namaste Anand ji, hope business is good. I understand this month is "
                "tight — let's find a way that works for both of us. Could we confirm a "
                "part-payment now and split the balance over a few weeks?"),
            structured_response=demo_plan)
    from app.llm.anthropic_client import AnthropicClient
    return AnthropicClient()


async def get_orchestrator(
    session: AsyncSession = Depends(get_session),
    llm: LLM = Depends(get_llm),
    owner_id: str = Depends(get_owner_id),
) -> Orchestrator:
    store = PgVectorStore(session, StubEmbedder(), owner_id=owner_id)
    cash_events = await CashEventRepo(session).for_owner(owner_id)
    return Orchestrator(
        context_agent=ContextAgent(store),
        conversation_agent=ConversationAgent(llm),
        negotiation_agent=NegotiationAgent(llm),
        cash_service=CashCalendarService(),
        policy_engine=PolicyEngine(),
        memory=MemoryService(session, store),
        channel=get_channel(),
        tracer=default_tracer(),
        cash_events=cash_events,
        today=dt.date(2026, 5, 18),
    )
