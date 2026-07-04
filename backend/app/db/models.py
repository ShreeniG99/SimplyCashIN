import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBED_DIM = 384


class OwnerRow(Base):
    __tablename__ = "owner"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    business: Mapped[str] = mapped_column(String)
    max_extension_days: Mapped[int] = mapped_column(Integer)
    min_upfront_pct: Mapped[int] = mapped_column(Integer)


class BuyerRow(Base):
    __tablename__ = "buyer"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id", deferrable=True, initially="DEFERRED"))
    name: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String)
    relationship_years: Mapped[float] = mapped_column(Float)
    on_time_rate: Mapped[float] = mapped_column(Float)
    preferred_channel: Mapped[str] = mapped_column(String)


class InvoiceRow(Base):
    __tablename__ = "invoice"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id", deferrable=True, initially="DEFERRED"))
    number: Mapped[str] = mapped_column(String)
    amount_paise: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    days_overdue: Mapped[int] = mapped_column(Integer)


class ConversationTurnRow(Base):
    __tablename__ = "conversation_turn"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id", deferrable=True, initially="DEFERRED"))
    sender: Mapped[str] = mapped_column(String)
    agent: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)


class CashEventRow(Base):
    __tablename__ = "cash_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id", deferrable=True, initially="DEFERRED"))
    direction: Mapped[str] = mapped_column(String)
    due_date: Mapped[dt.date] = mapped_column(Date)
    counterparty: Mapped[str] = mapped_column(String)
    amount_paise: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class EscalationRow(Base):
    __tablename__ = "escalation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id", deferrable=True, initially="DEFERRED"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    draft_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_tone: Mapped[str | None] = mapped_column(String, nullable=True)
    channel_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)


class MemoryRecordRow(Base):
    __tablename__ = "memory_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id", deferrable=True, initially="DEFERRED"))
    tone: Mapped[str] = mapped_column(String)
    timing: Mapped[str] = mapped_column(String)
    paid: Mapped[bool] = mapped_column(Boolean)


class MemoryEmbeddingRow(Base):
    __tablename__ = "memory_embedding"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id", deferrable=True, initially="DEFERRED"))
    # M4 tenancy namespace; nullable so pre-M4 writers keep working, always
    # stamped by PgVectorStore when constructed with an owner.
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("owner.id", deferrable=True, initially="DEFERRED"), nullable=True)
    snippet: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))


class IngestionJobRow(Base):
    __tablename__ = "ingestion_job"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id", deferrable=True, initially="DEFERRED"))
    source: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
