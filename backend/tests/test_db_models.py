import datetime as dt

import pytest
from sqlalchemy import select

from app.db.models import OwnerRow, BuyerRow, MemoryEmbeddingRow, EMBED_DIM


@pytest.mark.db
async def test_owner_roundtrip(session):
    session.add(OwnerRow(id="ramesh", name="Ramesh Iyer", business="Sri Vinayaga Motors",
                         max_extension_days=30, min_upfront_pct=30))
    await session.commit()
    row = (await session.execute(select(OwnerRow).where(OwnerRow.id == "ramesh"))).scalar_one()
    assert row.business == "Sri Vinayaga Motors"


@pytest.mark.db
async def test_embedding_roundtrip(session):
    session.add(OwnerRow(id="ramesh", name="R", business="B", max_extension_days=30, min_upfront_pct=30))
    session.add(BuyerRow(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular",
                         relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp"))
    session.add(MemoryEmbeddingRow(buyer_id="anand", snippet="paid after short extension",
                                   embedding=[0.1] * EMBED_DIM))
    await session.commit()
    row = (await session.execute(select(MemoryEmbeddingRow))).scalar_one()
    assert len(row.embedding) == EMBED_DIM
