from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryRecordRow
from app.domain.enums import Tone
from app.domain.models import PaymentPlan
from app.retrieval.vector_store import PgVectorStore


class MemoryService:
    def __init__(self, session: AsyncSession, store: PgVectorStore):
        self.s = session
        self.store = store

    async def record_outcome(self, *, buyer_id: str, tone: Tone, plan: PaymentPlan | None,
                             timing: str, paid: bool) -> None:
        self.s.add(MemoryRecordRow(buyer_id=buyer_id, tone=tone.value, timing=timing, paid=paid))
        outcome = "paid" if paid else "sent, awaiting reply"
        plan_note = f" with a {len(plan.installments)}-part plan" if plan else ""
        snippet = f"{tone.value} message at {timing}{plan_note} — {outcome}"
        await self.store.add(buyer_id, snippet)

    async def best_approach(self, buyer_id: str, query: str = "what worked best") -> list[str]:
        return await self.store.search(buyer_id, query, k=3)
