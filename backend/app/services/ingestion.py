import datetime as dt
import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.domain.enums import IngestionSource, JobStatus
from app.domain.models import Buyer, Invoice


class Connector(Protocol):
    def parse(self, raw: bytes, owner_id: str) -> list[tuple[Buyer, Invoice]]: ...


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def ingest(self, raw: bytes, owner_id: str, connector: Connector,
                     source: IngestionSource) -> str:
        from app.ingestion.base import Connector as _Connector
        from sqlalchemy import select

        job_id = str(uuid.uuid4())
        created_at = dt.datetime.now(dt.timezone.utc)

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
                if not existing:
                    self.s.add(m.BuyerRow(
                        id=buyer.id, owner_id=buyer.owner_id, name=buyer.name,
                        tier=buyer.tier, relationship_years=buyer.relationship_years,
                        on_time_rate=buyer.on_time_rate,
                        preferred_channel=buyer.preferred_channel))
                    self.s.add(m.InvoiceRow(
                        id=invoice.id, buyer_id=invoice.buyer_id,
                        number=invoice.number, amount_paise=invoice.amount_paise,
                        due_date=invoice.due_date, status=invoice.status.value,
                        days_overdue=invoice.days_overdue))
                    imported += 1

            job.status = JobStatus.DONE.value
            job.total_rows = total
            job.imported_rows = imported
            job.completed_at = dt.datetime.now(dt.timezone.utc)
            await self.s.commit()
        except Exception as exc:
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            job.completed_at = dt.datetime.now(dt.timezone.utc)
            await self.s.commit()
            raise

        return job_id
