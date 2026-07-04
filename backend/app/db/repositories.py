import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.domain.enums import CashEventStatus, Direction, InvoiceStatus
from app.domain.models import (
    Buyer, CashEvent, ConversationTurn, Escalation, Invoice, Owner, Policy,
)


class OwnerRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, owner_id: str) -> Owner:
        row = (await self.s.execute(
            select(m.OwnerRow).where(m.OwnerRow.id == owner_id))).scalar_one()
        return Owner(id=row.id, name=row.name, business=row.business,
                     policy=Policy(max_extension_days=row.max_extension_days,
                                   min_upfront_pct=row.min_upfront_pct))


class BuyerRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, buyer_id: str) -> Buyer:
        row = (await self.s.execute(
            select(m.BuyerRow).where(m.BuyerRow.id == buyer_id))).scalar_one()
        return self._to_domain(row)

    async def list_for_owner(self, owner_id: str) -> list[Buyer]:
        rows = (await self.s.execute(
            select(m.BuyerRow).where(m.BuyerRow.owner_id == owner_id))).scalars().all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: m.BuyerRow) -> Buyer:
        return Buyer(id=row.id, owner_id=row.owner_id, name=row.name, tier=row.tier,
                     relationship_years=row.relationship_years, on_time_rate=row.on_time_rate,
                     preferred_channel=row.preferred_channel)


class InvoiceRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, invoice_id: str, today: dt.date | None = None) -> Invoice:
        row = (await self.s.execute(
            select(m.InvoiceRow).where(m.InvoiceRow.id == invoice_id))).scalar_one()
        return self._to_domain(row, today)

    async def latest_for_buyer(self, buyer_id: str, today: dt.date | None = None) -> Invoice:
        row = (await self.s.execute(
            select(m.InvoiceRow).where(m.InvoiceRow.buyer_id == buyer_id)
            .order_by(m.InvoiceRow.due_date.desc()))).scalars().first()
        return self._to_domain(row, today)

    @staticmethod
    def _to_domain(row: m.InvoiceRow, today: dt.date | None) -> Invoice:
        # days_overdue is derived at read time so it never goes stale;
        # the stored column remains only as ingest-time metadata.
        today = today or dt.date.today()
        status = InvoiceStatus(row.status)
        days_overdue = (0 if status is InvoiceStatus.PAID
                        else max(0, (today - row.due_date).days))
        return Invoice(id=row.id, buyer_id=row.buyer_id, number=row.number,
                       amount_paise=row.amount_paise, due_date=row.due_date,
                       status=status, days_overdue=days_overdue)


class ConversationRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def thread_for_buyer(self, buyer_id: str) -> list[ConversationTurn]:
        rows = (await self.s.execute(
            select(m.ConversationTurnRow).where(m.ConversationTurnRow.buyer_id == buyer_id)
            .order_by(m.ConversationTurnRow.created_at))).scalars().all()
        return [ConversationTurn(id=r.id, buyer_id=r.buyer_id, sender=r.sender,
                                 agent=r.agent, text=r.text, created_at=r.created_at)
                for r in rows]

    async def add_turn(self, *, buyer_id: str, sender: str, text: str,
                       agent: str | None = None) -> ConversationTurn:
        row = m.ConversationTurnRow(
            id=str(uuid.uuid4()), buyer_id=buyer_id, sender=sender, agent=agent,
            text=text, created_at=dt.datetime.now(dt.UTC).replace(tzinfo=None))
        self.s.add(row)
        return ConversationTurn(id=row.id, buyer_id=row.buyer_id, sender=row.sender,
                                agent=row.agent, text=row.text, created_at=row.created_at)


class CashEventRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def for_owner(self, owner_id: str) -> list[CashEvent]:
        rows = (await self.s.execute(
            select(m.CashEventRow).where(m.CashEventRow.owner_id == owner_id)
            .order_by(m.CashEventRow.due_date))).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def toggle(self, event_id: str, owner_id: str | None = None) -> CashEvent:
        stmt = select(m.CashEventRow).where(m.CashEventRow.id == event_id)
        if owner_id is not None:
            stmt = stmt.where(m.CashEventRow.owner_id == owner_id)
        row = (await self.s.execute(stmt)).scalar_one()
        row.status = (CashEventStatus.DONE.value
                      if row.status == CashEventStatus.PENDING.value
                      else CashEventStatus.PENDING.value)
        await self.s.commit()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: m.CashEventRow) -> CashEvent:
        return CashEvent(id=row.id, owner_id=row.owner_id, direction=Direction(row.direction),
                         due_date=row.due_date, counterparty=row.counterparty,
                         amount_paise=row.amount_paise, label=row.label,
                         status=CashEventStatus(row.status))


class EscalationRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def save(self, esc: Escalation, *, draft_text: str | None,
                   channel_kind: str | None, draft_tone: str | None = None) -> None:
        self.s.add(m.EscalationRow(
            id=esc.id, buyer_id=esc.buyer_id, amount_paise=esc.amount_paise,
            reason=esc.reason, recommendation=esc.recommendation,
            draft_text=draft_text, draft_tone=draft_tone,
            channel_kind=channel_kind, resolved=False))

    async def get(self, esc_id: str) -> m.EscalationRow:
        return (await self.s.execute(
            select(m.EscalationRow).where(m.EscalationRow.id == esc_id))).scalar_one()

    async def resolve(self, esc_id: str, resolution: str) -> m.EscalationRow:
        row = await self.get(esc_id)
        row.resolved = True
        row.resolution = resolution
        await self.s.commit()
        return row
