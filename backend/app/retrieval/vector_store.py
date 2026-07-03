from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEmbeddingRow
from app.retrieval.embedder import Embedder


class PgVectorStore:
    def __init__(self, session: AsyncSession, embedder: Embedder):
        self.s = session
        self.embedder = embedder

    async def add(self, buyer_id: str, snippet: str) -> None:
        self.s.add(MemoryEmbeddingRow(buyer_id=buyer_id, snippet=snippet,
                                      embedding=self.embedder.embed(snippet)))

    async def search(self, buyer_id: str, query: str, k: int = 3) -> list[str]:
        qvec = self.embedder.embed(query)
        rows = (await self.s.execute(
            select(MemoryEmbeddingRow)
            .where(MemoryEmbeddingRow.buyer_id == buyer_id)
            .order_by(MemoryEmbeddingRow.embedding.cosine_distance(qvec))
            .limit(k))).scalars().all()
        return [r.snippet for r in rows]
