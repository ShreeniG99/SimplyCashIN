from typing import Protocol

from app.domain.models import Buyer, BuyerContext, Invoice


class _Store(Protocol):
    async def search(self, buyer_id: str, query: str, k: int = 3) -> list[str]: ...


class ContextAgent:
    """Hybrid retrieval: structured invoice/buyer facts + pgvector history snippets."""

    def __init__(self, store: _Store):
        self.store = store

    async def build(self, buyer: Buyer, invoice: Invoice) -> BuyerContext:
        snippets = await self.store.search(
            buyer.id, f"overdue {invoice.days_overdue} days what worked")
        best = snippets[0] if snippets else None
        return BuyerContext(buyer=buyer, invoice=invoice, on_time_rate=buyer.on_time_rate,
                            best_approach=best, history_snippets=snippets)
