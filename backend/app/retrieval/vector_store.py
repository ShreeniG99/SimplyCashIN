from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEmbeddingRow
from app.retrieval.embedder import Embedder


class PgVectorStore:
    """pgvector wrapper. `owner_id` is the M4 tenancy namespace: set, it is
    stamped on every write and filters every search alongside buyer_id."""

    def __init__(self, session: AsyncSession, embedder: Embedder,
                 owner_id: str | None = None):
        self.s = session
        self.embedder = embedder
        self.owner_id = owner_id

    async def add(self, buyer_id: str, snippet: str) -> None:
        self.s.add(MemoryEmbeddingRow(buyer_id=buyer_id, owner_id=self.owner_id,
                                      snippet=snippet,
                                      embedding=self.embedder.embed(snippet)))

    async def search(self, buyer_id: str, query: str, k: int = 3) -> list[str]:
        qvec = self.embedder.embed(query)
        stmt = select(MemoryEmbeddingRow).where(MemoryEmbeddingRow.buyer_id == buyer_id)
        if self.owner_id is not None:
            stmt = stmt.where(MemoryEmbeddingRow.owner_id == self.owner_id)
        rows = (await self.s.execute(
            stmt.order_by(MemoryEmbeddingRow.embedding.cosine_distance(qvec))
            .limit(k))).scalars().all()
        return [r.snippet for r in rows]
