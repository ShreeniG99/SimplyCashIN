import pytest

from app.db.models import OwnerRow, BuyerRow
from app.domain.enums import Tone
from app.retrieval.embedder import StubEmbedder
from app.retrieval.vector_store import PgVectorStore
from app.services.memory import MemoryService


@pytest.mark.db
async def test_record_outcome_then_best_approach(session):
    session.add(OwnerRow(id="ramesh", name="R", business="B", max_extension_days=30, min_upfront_pct=30))
    session.add(BuyerRow(id="anand", owner_id="ramesh", name="Anand", tier="Regular",
                         relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp"))
    await session.commit()

    store = PgVectorStore(session, StubEmbedder())
    mem = MemoryService(session, store)
    await mem.record_outcome(buyer_id="anand", tone=Tone.GENTLE, plan=None,
                             timing="day 7", paid=True)
    await session.commit()

    snippets = await mem.best_approach("anand")
    assert any("gentle" in s.lower() for s in snippets)
