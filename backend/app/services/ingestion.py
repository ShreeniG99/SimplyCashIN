import datetime as dt
import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.domain.enums import IngestionSource, JobStatus
from app.domain.models import Buyer, Invoice
from app.money import format_inr
from app.retrieval.embedder import StubEmbedder
from app.retrieval.vector_store import PgVectorStore


class Connector(Protocol):
    def parse(self, raw: bytes, owner_id: str) -> list[tuple[Buyer, Invoice]]: ...


def _utcnow() -> dt.datetime:
    # Naive UTC — the DateTime columns are TIMESTAMP WITHOUT TIME ZONE and
    # asyncpg rejects tz-aware values for them.
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class IngestionService:
    def __init__(self, session: AsyncSession, store: PgVectorStore | None = None) -> None:
        self.s = session
        self.store = store or PgVectorStore(session, StubEmbedder())

    async def ingest(self, raw: bytes, owner_id: str, connector: Connector,
                     source: IngestionSource) -> str:
        from sqlalchemy import select

        job_id = str(uuid.uuid4())
        created_at = _utcnow()

        job = m.IngestionJobRow(
            id=job_id, owner_id=owner_id, source=source.value,
            status=JobStatus.PENDING.value, created_at=created_at)
        self.s.add(job)
        await self.s.flush()

        try:
            job.status = JobStatus.PROCESSING.value
            await self.s.flush()

            pairs = connector.parse(raw, owner_id)
            total = len(pairs)
            imported = 0
            for buyer, invoice in pairs:
                # upsert buyer by name for owner
                row = await self.s.execute(
                    select(m.BuyerRow).where(
                        m.BuyerRow.owner_id == owner_id,
                        m.BuyerRow.name == buyer.name))
                existing = row.scalar_one_or_none()
                buyer_id = existing.id if existing else buyer.id
                if not existing:
                    self.s.add(m.BuyerRow(
                        id=buyer.id, owner_id=buyer.owner_id, name=buyer.name,
                        tier=buyer.tier, relationship_years=buyer.relationship_years,
                        on_time_rate=buyer.on_time_rate,
                        preferred_channel=buyer.preferred_channel))

                # Always add the invoice (linked to this buyer)
                self.s.add(m.InvoiceRow(
                    id=invoice.id, buyer_id=buyer_id,
                    number=invoice.number, amount_paise=invoice.amount_paise,
                    due_date=invoice.due_date, status=invoice.status.value,
                    days_overdue=invoice.days_overdue))

                # M2 vectorization pipeline: embed a snippet so the
                # ContextAgent can retrieve ingested history.
                snippet = (
                    f"Ingested invoice {invoice.number} for {buyer.name}: "
                    f"{format_inr(invoice.amount_paise)}, due {invoice.due_date.isoformat()}, "
                    f"{invoice.days_overdue} days overdue ({source.value} import)")
                await self.store.add(buyer_id, snippet)
                imported += 1

            job.status = JobStatus.DONE.value
            job.total_rows = total
            job.imported_rows = imported
            job.completed_at = _utcnow()
            await self.s.commit()
        except Exception as exc:
            # The session may hold a failed transaction — roll back, then
            # re-insert the job row as FAILED so the failure is visible.
            await self.s.rollback()
            try:
                self.s.add(m.IngestionJobRow(
                    id=job_id, owner_id=owner_id, source=source.value,
                    status=JobStatus.FAILED.value, created_at=created_at,
                    error_message=str(exc)[:500], completed_at=_utcnow()))
                await self.s.commit()
            except Exception:  # noqa: BLE001 — original exc is what matters
                pass
            raise

        return job_id
