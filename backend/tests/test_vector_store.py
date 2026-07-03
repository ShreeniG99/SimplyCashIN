import pytest

from app.db.models import OwnerRow, BuyerRow
from app.retrieval.embedder import StubEmbedder
from app.retrieval.vector_store import PgVectorStore


@pytest.mark.db
async def test_similarity_search_returns_closest(session):
    session.add(OwnerRow(id="ramesh", name="R", business="B", max_extension_days=30, min_upfront_pct=30))
    session.add(BuyerRow(id="anand", owner_id="ramesh", name="Anand", tier="Regular",
                         relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp"))
    await session.commit()

    store = PgVectorStore(session, StubEmbedder())
    await store.add("anand", "Buyer paid after a short extension and an early-pay nudge")
    await store.add("anand", "Buyer ignores SMS but replies on WhatsApp")
    await session.commit()

    hits = await store.search("anand", "what worked: extension", k=1)
    assert len(hits) == 1
    assert "extension" in hits[0]
