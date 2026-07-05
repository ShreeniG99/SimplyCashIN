# SimplyCashIN M1 Vertical Slice — Implementation Plan

> **STATUS: ✅ SHIPPED.** Every task below is implemented, tested, and merged (the checkboxes were used for in-session tracking and left unticked). M2–M5 followed on top of this slice — see the repo root README for the full feature list.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable, end-to-end collections decision loop for one overdue invoice — Context → Conversation → Negotiation → Orchestrator (ACT/ESCALATE) → simulated dispatch → Memory — behind a thin FastAPI surface, backed by Postgres+pgvector.

**Architecture:** A hand-rolled Orchestrator composes four units. Two agents (Conversation, Negotiation) call Claude `claude-opus-4-8` through a single `LLM` seam (real `AnthropicClient` / deterministic `StubLLM`). Context retrieval, cash-calendar urgency, and policy guardrails are pure Python — the ACT-vs-ESCALATE branch is deterministic and auditable, never an LLM call. External channels, embeddings, and tracing are behind protocols with stub/null defaults so the slice runs without external services.

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy 2.0 + asyncpg, Alembic, pgvector, Pydantic v2 + pydantic-settings, `anthropic` SDK, `posthog`, pytest + pytest-asyncio, Docker Compose (pgvector/pgvector image).

**Conventions:**
- Money is stored and computed as **integer paise**; formatted to `₹` (Indian grouping) only at the API edge.
- All money fields end in `_paise`.
- Tests requiring a live database are marked `@pytest.mark.db`; tests hitting real Claude are marked `@pytest.mark.integration`. Default `pytest` runs neither unless selected, except `db` tests run when Postgres is up (see Task 2 conftest).
- Run all commands from `backend/`.

---

## File structure

```
backend/
  pyproject.toml                 # deps + pytest config
  docker-compose.yml             # postgres + pgvector (single service)
  .env.example
  alembic.ini
  README.md
  app/
    __init__.py
    config.py                    # Settings (env)
    money.py                     # format_inr(paise)
    domain/
      __init__.py
      enums.py                   # Direction, CashEventStatus, InvoiceStatus, Decision, Tone
      models.py                  # all Pydantic domain models
    db/
      __init__.py
      base.py                    # DeclarativeBase
      session.py                 # async engine + session factory
      models.py                  # ORM models (incl. MemoryEmbedding w/ pgvector)
      repositories.py            # OwnerRepo, BuyerRepo, InvoiceRepo, ConversationRepo,
                                 #   CashEventRepo, EscalationRepo, MemoryRepo
      seed.py                    # loads the Ramesh Iyer fixture
    llm/
      __init__.py
      base.py                    # LLM protocol + errors
      stub.py                    # StubLLM
      anthropic_client.py        # AnthropicClient (claude-opus-4-8)
    retrieval/
      __init__.py
      embedder.py                # Embedder protocol + StubEmbedder
      vector_store.py            # PgVectorStore (embed + cosine search)
    obs/
      __init__.py
      tracer.py                  # Tracer protocol + NullTracer + PostHogTracer
    services/
      __init__.py
      cash_calendar.py           # CashCalendarService.urgency()
      policy.py                  # PolicyEngine.evaluate()
      memory.py                  # MemoryService
    channels/
      __init__.py
      base.py                    # Channel protocol + DispatchResult
      simulated.py               # SimulatedChannel
    agents/
      __init__.py
      context.py                 # ContextAgent
      conversation.py            # ConversationAgent
      negotiation.py             # NegotiationAgent
      orchestrator.py            # Orchestrator + needs_negotiation()
    api/
      __init__.py
      app.py                     # create_app()
      deps.py                    # dependency providers
      schemas.py                 # WFDATA-shaped response models
      routes.py                  # endpoints
  tests/
    __init__.py
    conftest.py
    ...
```

---

## Task 0: Project scaffold

**Files:**
- Create: `backend/pyproject.toml`, `backend/docker-compose.yml`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/README.md`, `backend/tests/__init__.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "simplycashin"
version = "0.1.0"
description = "SimplyCashIN — agentic receivables for Indian MSME owners"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pgvector>=0.3",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "anthropic>=0.69",
    "posthog>=3.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "db: requires a running Postgres (docker-compose up)",
    "integration: hits the real Anthropic API",
]
addopts = "-m 'not integration'"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

- [ ] **Step 2: Create `backend/docker-compose.yml`**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: scin
      POSTGRES_PASSWORD: scin
      POSTGRES_DB: scin
    ports:
      - "5432:5432"
    volumes:
      - scin_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scin"]
      interval: 5s
      timeout: 3s
      retries: 10
volumes:
  scin_pgdata:
```

- [ ] **Step 3: Create `backend/.env.example`**

```bash
ANTHROPIC_API_KEY=sk-ant-...
USE_STUB_LLM=0
DATABASE_URL=postgresql+asyncpg://scin:scin@localhost:5432/scin
TEST_DATABASE_URL=postgresql+asyncpg://scin:scin@localhost:5432/scin_test
POSTHOG_API_KEY=
POSTHOG_HOST=https://us.i.posthog.com
```

- [ ] **Step 4: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    use_stub_llm: bool = False
    database_url: str = "postgresql+asyncpg://scin:scin@localhost:5432/scin"
    test_database_url: str = "postgresql+asyncpg://scin:scin@localhost:5432/scin_test"
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"


settings = Settings()
```

- [ ] **Step 5: Create empty `backend/app/__init__.py` and `backend/tests/__init__.py`; create `backend/README.md`**

`backend/README.md`:
```markdown
# SimplyCashIN backend (M1)

    python -m venv .venv && . .venv/Scripts/activate   # Windows
    pip install -e ".[dev]"
    docker compose up -d
    createdb / auto: tests create scin_test schema
    cp .env.example .env   # set ANTHROPIC_API_KEY
    uvicorn app.api.app:app --reload

Run tests: `python -m pytest`
```

- [ ] **Step 6: Verify install and DB come up**

Run: `cd backend && pip install -e ".[dev]" && docker compose up -d`
Expected: dependencies install; `docker compose ps` shows `db` healthy.

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/docker-compose.yml backend/.env.example backend/app/__init__.py backend/app/config.py backend/README.md backend/tests/__init__.py
git commit -m "chore: scaffold SimplyCashIN backend (deps, compose, config)"
```

---

## Task 1: Money helper

**Files:**
- Create: `backend/app/money.py`, `backend/tests/test_money.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_money.py`

```python
from app.money import format_inr


def test_format_inr_lakhs():
    assert format_inr(240000_00) == "₹2,40,000"   # 2.4 lakh rupees in paise


def test_format_inr_thousands():
    assert format_inr(85000_00) == "₹85,000"


def test_format_inr_small():
    assert format_inr(500_00) == "₹500"


def test_format_inr_zero():
    assert format_inr(0) == "₹0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_money.py -v`
Expected: FAIL — `ModuleNotFoundError: app.money`.

- [ ] **Step 3: Write minimal implementation** — `backend/app/money.py`

```python
def format_inr(paise: int) -> str:
    """Format integer paise as Indian-grouped rupees, e.g. 24000000 -> '₹2,40,000'."""
    rupees = paise // 100
    s = str(rupees)
    if len(s) <= 3:
        grouped = s
    else:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join(parts) + "," + tail
    return f"₹{grouped}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_money.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/money.py tests/test_money.py
git commit -m "feat: INR paise formatting helper"
```

---

## Task 2: Enums + domain models

**Files:**
- Create: `backend/app/domain/__init__.py`, `backend/app/domain/enums.py`, `backend/app/domain/models.py`, `backend/tests/test_domain.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_domain.py`

```python
import datetime as dt

from app.domain.enums import Direction, Decision, InvoiceStatus, Tone, CashEventStatus
from app.domain.models import (
    Policy, Owner, Buyer, Invoice, ConversationTurn, PaymentInstallment,
    PaymentPlan, PolicyCheck, BuyerContext, CashEvent, CashUrgency,
    DraftMessage, Escalation, MemoryRecord, CycleResult,
)


def test_payment_plan_total():
    plan = PaymentPlan(
        upfront_pct=30, extension_days=30,
        installments=[
            PaymentInstallment(seq=1, label="Upfront", amount_paise=80000_00, due_offset_days=0),
            PaymentInstallment(seq=2, label="Installment 2", amount_paise=80000_00, due_offset_days=15),
            PaymentInstallment(seq=3, label="Installment 3", amount_paise=80000_00, due_offset_days=30),
        ],
    )
    assert plan.total_paise == 240000_00


def test_cycle_result_minimal_escalation():
    buyer = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
                  relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
    inv = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
                  due_date=dt.date(2026, 5, 15), status=InvoiceStatus.OVERDUE, days_overdue=14)
    ctx = BuyerContext(buyer=buyer, invoice=inv, on_time_rate=0.82,
                       best_approach="Short extension + early-pay nudge", history_snippets=[])
    result = CycleResult(
        decision=Decision.ESCALATE, context=ctx, draft=None, plan=None,
        checks=[PolicyCheck(label="Minimum upfront (30%)", value="Buyer offered 15%", ok=False)],
        escalation=Escalation(id="e1", buyer_id="anand", amount_paise=240000_00,
                              reason="upfront too low", checks=[], recommendation="Hold firm"),
        urgency=CashUrgency(score=0.7, breaching_need="₹1,20,000 due Mon"),
    )
    assert result.decision is Decision.ESCALATE
    assert result.draft is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_domain.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/domain/enums.py`**

```python
from enum import Enum


class Direction(str, Enum):
    IN = "in"
    OUT = "out"


class CashEventStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"


class InvoiceStatus(str, Enum):
    PAID = "paid"
    DUE = "due"
    OVERDUE = "overdue"


class Decision(str, Enum):
    ACT = "act"
    ESCALATE = "escalate"


class Tone(str, Enum):
    GENTLE = "gentle"
    FIRM = "firm"
```

- [ ] **Step 4: Implement `backend/app/domain/models.py`**

```python
import datetime as dt
from typing import Literal

from pydantic import BaseModel

from app.domain.enums import (
    CashEventStatus, Decision, Direction, InvoiceStatus, Tone,
)


class Policy(BaseModel):
    max_extension_days: int
    min_upfront_pct: int


class Owner(BaseModel):
    id: str
    name: str
    business: str
    policy: Policy


class Buyer(BaseModel):
    id: str
    owner_id: str
    name: str
    tier: str
    relationship_years: float
    on_time_rate: float
    preferred_channel: str


class Invoice(BaseModel):
    id: str
    buyer_id: str
    number: str
    amount_paise: int
    due_date: dt.date
    status: InvoiceStatus
    days_overdue: int


class ConversationTurn(BaseModel):
    id: str
    buyer_id: str
    sender: Literal["agent", "buyer"]
    agent: str | None = None
    text: str
    created_at: dt.datetime


class PaymentInstallment(BaseModel):
    seq: int
    label: str
    amount_paise: int
    due_offset_days: int


class PaymentPlan(BaseModel):
    upfront_pct: int
    extension_days: int
    installments: list[PaymentInstallment]

    @property
    def total_paise(self) -> int:
        return sum(i.amount_paise for i in self.installments)


class PolicyCheck(BaseModel):
    label: str
    value: str
    ok: bool


class BuyerContext(BaseModel):
    buyer: Buyer
    invoice: Invoice
    on_time_rate: float
    best_approach: str | None
    history_snippets: list[str]


class CashEvent(BaseModel):
    id: str
    owner_id: str
    direction: Direction
    due_date: dt.date
    counterparty: str
    amount_paise: int
    label: str
    status: CashEventStatus


class CashUrgency(BaseModel):
    score: float
    breaching_need: str | None


class DraftMessage(BaseModel):
    text: str
    tone: Tone


class Escalation(BaseModel):
    id: str
    buyer_id: str
    amount_paise: int
    reason: str
    checks: list[PolicyCheck]
    recommendation: str


class MemoryRecord(BaseModel):
    buyer_id: str
    tone: Tone
    plan: PaymentPlan | None
    timing: str
    paid: bool


class CycleResult(BaseModel):
    decision: Decision
    context: BuyerContext
    draft: DraftMessage | None
    plan: PaymentPlan | None
    checks: list[PolicyCheck]
    escalation: Escalation | None
    urgency: CashUrgency
```

- [ ] **Step 5: Create empty `backend/app/domain/__init__.py`; run tests**

Run: `python -m pytest tests/test_domain.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/domain tests/test_domain.py
git commit -m "feat: domain enums and Pydantic models"
```

---

## Task 3: Database layer (engine, ORM models, schema)

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/db/models.py`, `backend/tests/conftest.py`, `backend/tests/test_db_models.py`

- [ ] **Step 1: Create `backend/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Create `backend/app/db/session.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)

from app.config import settings


def make_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(url or settings.database_url, future=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


_engine = make_engine()
SessionFactory = make_session_factory(_engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
```

- [ ] **Step 3: Create `backend/app/db/models.py`** (ORM; mirrors domain, plus the pgvector embedding table)

```python
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
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"))
    name: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String)
    relationship_years: Mapped[float] = mapped_column(Float)
    on_time_rate: Mapped[float] = mapped_column(Float)
    preferred_channel: Mapped[str] = mapped_column(String)


class InvoiceRow(Base):
    __tablename__ = "invoice"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"))
    number: Mapped[str] = mapped_column(String)
    amount_paise: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    days_overdue: Mapped[int] = mapped_column(Integer)


class ConversationTurnRow(Base):
    __tablename__ = "conversation_turn"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"))
    sender: Mapped[str] = mapped_column(String)
    agent: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)


class CashEventRow(Base):
    __tablename__ = "cash_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owner.id"))
    direction: Mapped[str] = mapped_column(String)
    due_date: Mapped[dt.date] = mapped_column(Date)
    counterparty: Mapped[str] = mapped_column(String)
    amount_paise: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class EscalationRow(Base):
    __tablename__ = "escalation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class MemoryRecordRow(Base):
    __tablename__ = "memory_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"))
    tone: Mapped[str] = mapped_column(String)
    timing: Mapped[str] = mapped_column(String)
    paid: Mapped[bool] = mapped_column(Boolean)


class MemoryEmbeddingRow(Base):
    __tablename__ = "memory_embedding"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"))
    snippet: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
```

- [ ] **Step 4: Create `backend/tests/conftest.py`** (test DB: creates `scin_test`, enables vector, builds schema per session)

```python
import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (register tables)
from app.db.session import make_engine, make_session_factory


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = make_engine(settings.test_database_url)
    try:
        async with eng.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres+pgvector not available: {exc}")
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = make_session_factory(engine)
    async with factory() as s:
        # clean tables between tests
        for table in reversed(Base.metadata.sorted_tables):
            await s.execute(text(f"TRUNCATE {table.name} CASCADE"))
        await s.commit()
        yield s
```

> Note: create the `scin_test` database once manually: `docker compose exec db createdb -U scin scin_test` (or `psql -U scin -c "CREATE DATABASE scin_test"`). If the DB is missing the `engine` fixture skips db-marked tests rather than erroring.

- [ ] **Step 5: Write the failing test** — `backend/tests/test_db_models.py`

```python
import pytest
from sqlalchemy import select

from app.db.models import OwnerRow, MemoryEmbeddingRow, EMBED_DIM


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
    session.add(MemoryEmbeddingRow(buyer_id=None) if False else
                MemoryEmbeddingRow(buyer_id="ramesh", snippet="hi", embedding=[0.0] * EMBED_DIM))
    # buyer_id FK references buyer; use an owner-less standalone insert is invalid, so skip FK here:
```

> Replace the second test with the simpler version below (FK to `buyer` requires a buyer row); keep only the owner roundtrip plus an embedding test that first inserts a buyer.

Final `test_db_models.py`:
```python
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
```

- [ ] **Step 6: Run tests**

Run: `docker compose exec db createdb -U scin scin_test ; python -m pytest tests/test_db_models.py -v -m db`
Expected: PASS (2 passed). (If Postgres is down, tests skip.)

- [ ] **Step 7: Commit**

```bash
git add app/db tests/conftest.py tests/test_db_models.py
git commit -m "feat: async SQLAlchemy models + pgvector embedding table + test DB fixtures"
```

---

## Task 4: Repositories

**Files:**
- Create: `backend/app/db/repositories.py`, `backend/tests/test_repositories.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_repositories.py`

```python
import datetime as dt

import pytest

from app.db.models import OwnerRow, BuyerRow, InvoiceRow
from app.db.repositories import OwnerRepo, BuyerRepo, InvoiceRepo


@pytest.mark.db
async def test_buyer_and_invoice_lookup(session):
    session.add(OwnerRow(id="ramesh", name="Ramesh", business="SVM",
                         max_extension_days=30, min_upfront_pct=30))
    session.add(BuyerRow(id="anand", owner_id="ramesh", name="Anand Motors",
                         tier="Regular · 3 yrs", relationship_years=3.0,
                         on_time_rate=0.82, preferred_channel="WhatsApp Business"))
    session.add(InvoiceRow(id="inv1", buyer_id="anand", number="INV-2291",
                           amount_paise=240000_00, due_date=dt.date(2026, 5, 15),
                           status="overdue", days_overdue=14))
    await session.commit()

    owner = await OwnerRepo(session).get("ramesh")
    assert owner.policy.max_extension_days == 30

    buyer = await BuyerRepo(session).get("anand")
    assert buyer.on_time_rate == 0.82

    inv = await InvoiceRepo(session).latest_for_buyer("anand")
    assert inv.number == "INV-2291"
    assert inv.amount_paise == 240000_00
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repositories.py -v -m db`
Expected: FAIL — `app.db.repositories` not found.

- [ ] **Step 3: Implement `backend/app/db/repositories.py`**

```python
import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m
from app.domain.enums import CashEventStatus, Direction, InvoiceStatus
from app.domain.models import (
    Buyer, CashEvent, ConversationTurn, Invoice, Owner, Policy,
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

    async def latest_for_buyer(self, buyer_id: str) -> Invoice:
        row = (await self.s.execute(
            select(m.InvoiceRow).where(m.InvoiceRow.buyer_id == buyer_id)
            .order_by(m.InvoiceRow.due_date.desc()))).scalars().first()
        return Invoice(id=row.id, buyer_id=row.buyer_id, number=row.number,
                       amount_paise=row.amount_paise, due_date=row.due_date,
                       status=InvoiceStatus(row.status), days_overdue=row.days_overdue)


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


class CashEventRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def for_owner(self, owner_id: str) -> list[CashEvent]:
        rows = (await self.s.execute(
            select(m.CashEventRow).where(m.CashEventRow.owner_id == owner_id)
            .order_by(m.CashEventRow.due_date))).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def toggle(self, event_id: str) -> CashEvent:
        row = (await self.s.execute(
            select(m.CashEventRow).where(m.CashEventRow.id == event_id))).scalar_one()
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_repositories.py -v -m db`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/db/repositories.py tests/test_repositories.py
git commit -m "feat: repositories (owner, buyer, invoice, conversation, cash events)"
```

---

## Task 5: Seed data

**Files:**
- Create: `backend/app/db/seed.py`, `backend/tests/test_seed.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_seed.py`

```python
import pytest
from sqlalchemy import select, func

from app.db.models import BuyerRow, CashEventRow
from app.db.repositories import OwnerRepo
from app.db.seed import seed


@pytest.mark.db
async def test_seed_loads_fixture(session):
    await seed(session)
    owner = await OwnerRepo(session).get("ramesh")
    assert owner.business == "Sri Vinayaga Motors"
    n_buyers = (await session.execute(select(func.count()).select_from(BuyerRow))).scalar_one()
    assert n_buyers == 5
    n_events = (await session.execute(select(func.count()).select_from(CashEventRow))).scalar_one()
    assert n_events >= 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_seed.py -v -m db`
Expected: FAIL — `app.db.seed` not found.

- [ ] **Step 3: Implement `backend/app/db/seed.py`** (derived from `ui_kits/wireframes/data.js`)

```python
import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m

OWNER_ID = "ramesh"
_TODAY = dt.date(2026, 5, 18)


async def seed(session: AsyncSession) -> None:
    session.add(m.OwnerRow(id=OWNER_ID, name="Ramesh Iyer", business="Sri Vinayaga Motors",
                           max_extension_days=30, min_upfront_pct=30))

    buyers = [
        ("anand", "Anand Motors", "Regular · 3 yrs", 3.0, 0.82, "WhatsApp Business", "overdue", 14, 240000_00, "INV-2291"),
        ("kpauto", "KP Auto Spares", "New · 2 mo", 0.2, 0.50, "SMS", "due", 6, 85000_00, "INV-2304"),
        ("sri", "Sri Lakshmi Traders", "Premium · 6 yrs", 6.0, 0.95, "WhatsApp Business", "due", 2, 110000_00, "INV-2310"),
        ("metro", "Metro Electricals", "Regular · 4 yrs", 4.0, 0.90, "Email", "paid", 0, 320000_00, "INV-2288"),
        ("rajan", "Rajan & Sons", "Regular · 5 yrs", 5.0, 0.78, "WhatsApp Business", "overdue", 9, 55000_00, "INV-2297"),
    ]
    for bid, name, tier, yrs, otr, ch, status, overdue, amt, num in buyers:
        session.add(m.BuyerRow(id=bid, owner_id=OWNER_ID, name=name, tier=tier,
                               relationship_years=yrs, on_time_rate=otr, preferred_channel=ch))
        session.add(m.InvoiceRow(id=f"inv-{bid}", buyer_id=bid, number=num, amount_paise=amt,
                                 due_date=_TODAY - dt.timedelta(days=overdue), status=status,
                                 days_overdue=overdue))

    # Anand thread (from WFDATA.thread)
    base = dt.datetime(2026, 5, 18, 10, 0)
    thread = [
        ("agent", "context", "Retrieved buyer history: 3 yrs, usually pays in 10–12 days. Last delay settled with a short extension."),
        ("agent", "conversation", "Namaste Anand ji, hope business is good. A gentle reminder that invoice #INV-2291 for ₹2,40,000 is now past due. Could you share when we can expect it?"),
        ("buyer", None, "Sorry Ramesh, cash is tight this month. Can I pay over a few weeks?"),
    ]
    for i, (sender, agent, txt) in enumerate(thread):
        session.add(m.ConversationTurnRow(id=f"t-anand-{i}", buyer_id="anand", sender=sender,
                                          agent=agent, text=txt,
                                          created_at=base + dt.timedelta(hours=i)))

    # Cash calendar (from WFDATA.cashCalendar) — direction in/out
    cash = [
        ("ce1", "in", _TODAY, "Anand Motors", 40000_00, "Expected from Anand", "pending"),
        ("ce2", "out", _TODAY, "GST + supplier", 120000_00, "GST + supplier payment", "pending"),
        ("ce3", "in", _TODAY + dt.timedelta(days=1), "KP Auto", 90000_00, "Expected from KP Auto", "pending"),
        ("ce4", "in", _TODAY + dt.timedelta(days=2), "Sri Lakshmi", 150000_00, "Expected from Sri Lakshmi", "pending"),
        ("ce5", "out", _TODAY + dt.timedelta(days=3), "Wages", 80000_00, "Staff wages", "pending"),
        ("ce6", "in", _TODAY + dt.timedelta(days=4), "Rajan & Sons", 120000_00, "Expected from Rajan", "pending"),
    ]
    for cid, direction, due, cp, amt, label, status in cash:
        session.add(m.CashEventRow(id=cid, owner_id=OWNER_ID, direction=direction, due_date=due,
                                   counterparty=cp, amount_paise=amt, label=label, status=status))

    await session.commit()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_seed.py -v -m db`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/db/seed.py tests/test_seed.py
git commit -m "feat: seed the Ramesh Iyer / Sri Vinayaga Motors fixture"
```

---

## Task 6: LLM seam (protocol, StubLLM, AnthropicClient)

**Files:**
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/base.py`, `backend/app/llm/stub.py`, `backend/app/llm/anthropic_client.py`, `backend/tests/test_llm_stub.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_llm_stub.py`

```python
from pydantic import BaseModel

from app.llm.stub import StubLLM


class Plan(BaseModel):
    upfront_pct: int


def test_stub_text():
    llm = StubLLM(text_response="Namaste")
    assert llm.complete_text("sys", "user") == "Namaste"


def test_stub_structured():
    llm = StubLLM(structured_response=Plan(upfront_pct=30))
    out = llm.complete_structured("sys", "user", Plan)
    assert out.upfront_pct == 30


def test_stub_records_calls():
    llm = StubLLM(text_response="ok")
    llm.complete_text("sys-A", "user-A")
    assert llm.calls[0] == ("text", "sys-A", "user-A")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_llm_stub.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/llm/base.py`**

```python
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Agent could not produce usable output."""


class LLMRefusal(LLMError):
    """The model declined the request (stop_reason == 'refusal')."""


class LLM(Protocol):
    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str: ...

    def complete_structured(self, system: str, user: str, schema: type[T],
                            max_tokens: int = 1024) -> T: ...
```

- [ ] **Step 4: Implement `backend/app/llm/stub.py`**

```python
from typing import TypeVar

from pydantic import BaseModel

from app.llm.base import LLMError

T = TypeVar("T", bound=BaseModel)


class StubLLM:
    """Deterministic LLM for tests and no-key runtime."""

    def __init__(self, text_response: str = "Namaste, a gentle reminder about your invoice.",
                 structured_response: BaseModel | None = None,
                 raise_error: bool = False):
        self.text_response = text_response
        self.structured_response = structured_response
        self.raise_error = raise_error
        self.calls: list[tuple] = []

    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str:
        self.calls.append(("text", system, user))
        if self.raise_error:
            raise LLMError("stub forced error")
        return self.text_response

    def complete_structured(self, system: str, user: str, schema, max_tokens: int = 1024):
        self.calls.append(("structured", system, user))
        if self.raise_error or self.structured_response is None:
            raise LLMError("stub forced error / no structured response set")
        return self.structured_response
```

- [ ] **Step 5: Implement `backend/app/llm/anthropic_client.py`**

```python
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMError, LLMRefusal

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    def complete_text(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.messages.create(
            model=self._model, max_tokens=max_tokens,
            thinking={"type": "adaptive"}, system=system,
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model refused")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    def complete_structured(self, system: str, user: str, schema: type[T],
                            max_tokens: int = 1024) -> T:
        resp = self._client.messages.parse(
            model=self._model, max_tokens=max_tokens,
            thinking={"type": "adaptive"}, system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        if resp.stop_reason == "refusal":
            raise LLMRefusal("model refused")
        if resp.parsed_output is None:
            raise LLMError("no structured output parsed")
        return resp.parsed_output
```

- [ ] **Step 6: Create empty `backend/app/llm/__init__.py`; run tests**

Run: `python -m pytest tests/test_llm_stub.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add app/llm tests/test_llm_stub.py
git commit -m "feat: LLM seam (protocol, StubLLM, AnthropicClient with adaptive thinking + structured output)"
```

---

## Task 7: Embedder + pgvector store

**Files:**
- Create: `backend/app/retrieval/__init__.py`, `backend/app/retrieval/embedder.py`, `backend/app/retrieval/vector_store.py`, `backend/tests/test_vector_store.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_vector_store.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vector_store.py -v -m db`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/retrieval/embedder.py`** (deterministic stub; swappable for a real model later)

```python
import hashlib
import math
from typing import Protocol

EMBED_DIM = 384


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class StubEmbedder:
    """Deterministic bag-of-tokens hashing embedder. Good enough for M1 retrieval;
    swap for a real sentence-transformer (same dim) in a later milestone."""

    dim = EMBED_DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
```

- [ ] **Step 4: Implement `backend/app/retrieval/vector_store.py`**

```python
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
```

- [ ] **Step 5: Create empty `backend/app/retrieval/__init__.py`; run tests**

Run: `python -m pytest tests/test_vector_store.py -v -m db`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add app/retrieval tests/test_vector_store.py
git commit -m "feat: pgvector store + deterministic stub embedder"
```

---

## Task 8: Tracer (PostHog seam)

**Files:**
- Create: `backend/app/obs/__init__.py`, `backend/app/obs/tracer.py`, `backend/tests/test_tracer.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_tracer.py`

```python
from app.obs.tracer import NullTracer, RecordingTracer


def test_null_tracer_no_error():
    NullTracer().trace(agent="conversation", model="stub", prompt="p", response="r", meta={})


def test_recording_tracer_collects():
    t = RecordingTracer()
    t.trace(agent="orchestrator", model="-", prompt="-", response="-", meta={"decision": "act"})
    assert t.events[0]["agent"] == "orchestrator"
    assert t.events[0]["meta"]["decision"] == "act"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tracer.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/obs/tracer.py`**

```python
from typing import Any, Protocol

from app.config import settings


class Tracer(Protocol):
    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None: ...


class NullTracer:
    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None:
        return None


class RecordingTracer:
    """In-memory tracer for tests."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None:
        self.events.append({"agent": agent, "model": model, "prompt": prompt,
                            "response": response, "meta": meta})


class PostHogTracer:
    """Sends agent calls/decisions to PostHog LLM analytics. Never raises."""

    def __init__(self, api_key: str | None = None, host: str | None = None):
        import posthog
        self._client = posthog.Posthog(api_key or settings.posthog_api_key,
                                       host=host or settings.posthog_host)

    def trace(self, *, agent: str, model: str, prompt: str, response: str,
              meta: dict[str, Any]) -> None:
        try:
            self._client.capture(
                distinct_id=meta.get("owner_id", "system"),
                event="$ai_generation",
                properties={"$ai_model": model, "$ai_input": prompt,
                            "$ai_output_choices": response, "scin_agent": agent, **meta},
            )
        except Exception:  # noqa: BLE001 — observability must never break a cycle
            pass


def default_tracer() -> Tracer:
    return PostHogTracer() if settings.posthog_api_key else NullTracer()
```

- [ ] **Step 4: Create empty `backend/app/obs/__init__.py`; run tests**

Run: `python -m pytest tests/test_tracer.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/obs tests/test_tracer.py
git commit -m "feat: Tracer seam (Null/Recording/PostHog), never breaks a cycle"
```

---

## Task 9: CashCalendarService

**Files:**
- Create: `backend/app/services/__init__.py`, `backend/app/services/cash_calendar.py`, `backend/tests/test_cash_calendar.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_cash_calendar.py`

```python
import datetime as dt

from app.domain.enums import CashEventStatus, Direction
from app.domain.models import CashEvent
from app.services.cash_calendar import CashCalendarService

TODAY = dt.date(2026, 5, 18)


def _evt(direction, days, amt, status=CashEventStatus.PENDING, cp="x"):
    return CashEvent(id=f"{direction}-{days}-{amt}", owner_id="ramesh",
                     direction=direction, due_date=TODAY + dt.timedelta(days=days),
                     counterparty=cp, amount_paise=amt, label=cp, status=status)


def test_no_outgoing_means_zero_urgency():
    events = [_evt(Direction.IN, 1, 90000_00)]
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score == 0.0
    assert u.breaching_need is None


def test_uncovered_outgoing_drives_high_urgency():
    events = [_evt(Direction.OUT, 0, 120000_00, cp="GST")]  # due today, no incoming
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score >= 0.8           # fully uncovered + due-today proximity boost
    assert "GST" in u.breaching_need


def test_incoming_covers_outgoing_lowers_urgency():
    events = [_evt(Direction.OUT, 5, 100000_00, cp="Wages"),
              _evt(Direction.IN, 1, 150000_00)]
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score == 0.0           # incoming fully covers, no proximity (5 days out)


def test_done_events_ignored():
    events = [_evt(Direction.OUT, 0, 120000_00, status=CashEventStatus.DONE, cp="GST")]
    u = CashCalendarService().urgency(events, TODAY)
    assert u.score == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cash_calendar.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/services/cash_calendar.py`**

```python
import datetime as dt

from app.domain.enums import CashEventStatus, Direction
from app.domain.models import CashEvent, CashUrgency
from app.money import format_inr

WEEK_DAYS = 7
PROXIMITY_DAYS = 2
PROXIMITY_BOOST = 0.2


class CashCalendarService:
    def urgency(self, events: list[CashEvent], today: dt.date) -> CashUrgency:
        week_end = today + dt.timedelta(days=WEEK_DAYS)

        def in_week(e: CashEvent) -> bool:
            return (e.status == CashEventStatus.PENDING
                    and today <= e.due_date <= week_end)

        outs = [e for e in events if e.direction == Direction.OUT and in_week(e)]
        ins = [e for e in events if e.direction == Direction.IN and in_week(e)]

        out_total = sum(e.amount_paise for e in outs)
        in_total = sum(e.amount_paise for e in ins)

        if out_total == 0:
            return CashUrgency(score=0.0, breaching_need=None)

        coverage_gap = max(0, out_total - in_total)
        base = coverage_gap / out_total
        soon = any(e.due_date <= today + dt.timedelta(days=PROXIMITY_DAYS) for e in outs)
        boost = PROXIMITY_BOOST if (soon and base > 0) else 0.0
        score = min(1.0, base + boost)

        nearest = min(outs, key=lambda e: (e.due_date, -e.amount_paise))
        need = f"{format_inr(nearest.amount_paise)} due {nearest.due_date:%a}"
        return CashUrgency(score=score, breaching_need=need)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_cash_calendar.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/__init__.py app/services/cash_calendar.py tests/test_cash_calendar.py
git commit -m "feat: cash-calendar urgency (uncovered + near-term outgoing -> firmer)"
```

---

## Task 10: PolicyEngine

**Files:**
- Create: `backend/app/services/policy.py`, `backend/tests/test_policy.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_policy.py`

```python
from app.domain.models import (
    Policy, PaymentPlan, PaymentInstallment, CashUrgency, Buyer,
)
from app.services.policy import PolicyEngine

POLICY = Policy(max_extension_days=30, min_upfront_pct=30)
BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")


def _plan(upfront_pct, extension_days):
    return PaymentPlan(upfront_pct=upfront_pct, extension_days=extension_days,
                       installments=[PaymentInstallment(seq=1, label="Upfront",
                                                         amount_paise=80000_00, due_offset_days=0)])


def test_compliant_plan_all_ok():
    checks = PolicyEngine().evaluate(_plan(30, 30), POLICY, CashUrgency(score=0.2, breaching_need=None), BUYER)
    assert all(c.ok for c in checks)


def test_extension_breach_flags_not_ok():
    checks = PolicyEngine().evaluate(_plan(30, 45), POLICY, CashUrgency(score=0.2, breaching_need=None), BUYER)
    ext = next(c for c in checks if "extension" in c.label.lower())
    assert ext.ok is False


def test_upfront_breach_flags_not_ok():
    checks = PolicyEngine().evaluate(_plan(15, 30), POLICY, CashUrgency(score=0.2, breaching_need=None), BUYER)
    up = next(c for c in checks if "upfront" in c.label.lower())
    assert up.ok is False


def test_high_cash_urgency_flags_not_ok():
    checks = PolicyEngine().evaluate(_plan(30, 30), POLICY,
                                     CashUrgency(score=0.8, breaching_need="₹1,20,000 due Mon"), BUYER)
    cash = next(c for c in checks if "cash" in c.label.lower())
    assert cash.ok is False
    assert "1,20,000" in cash.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_policy.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/services/policy.py`**

```python
from app.domain.models import Buyer, CashUrgency, PaymentPlan, Policy, PolicyCheck

CASH_URGENCY_THRESHOLD = 0.5


class PolicyEngine:
    def evaluate(self, plan: PaymentPlan, policy: Policy, urgency: CashUrgency,
                 buyer: Buyer) -> list[PolicyCheck]:
        return [
            PolicyCheck(
                label=f"Within max extension ({policy.max_extension_days}d)",
                value=f"plan needs {plan.extension_days}d",
                ok=plan.extension_days <= policy.max_extension_days,
            ),
            PolicyCheck(
                label=f"Minimum upfront ({policy.min_upfront_pct}%)",
                value=f"plan offers {plan.upfront_pct}%",
                ok=plan.upfront_pct >= policy.min_upfront_pct,
            ),
            PolicyCheck(
                label="Owner cash need this week",
                value=urgency.breaching_need or "no urgent need",
                ok=urgency.score < CASH_URGENCY_THRESHOLD,
            ),
            PolicyCheck(
                label="Relationship tier",
                value=f"{buyer.tier} · {int(buyer.on_time_rate * 100)}% on-time",
                ok=True,
            ),
        ]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_policy.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/policy.py tests/test_policy.py
git commit -m "feat: deterministic policy engine (extension, upfront, cash-need, tier)"
```

---

## Task 11: MemoryService

**Files:**
- Create: `backend/app/services/memory.py`, `backend/tests/test_memory.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_memory.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory.py -v -m db`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/services/memory.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryRecordRow
from app.domain.enums import Tone
from app.domain.models import PaymentPlan
from app.retrieval.vector_store import PgVectorStore


class MemoryService:
    def __init__(self, session: AsyncSession, store: PgVectorStore):
        self.s = session
        self.store = store

    async def record_outcome(self, *, buyer_id: str, tone: Tone, plan: PaymentPlan | None,
                             timing: str, paid: bool) -> None:
        self.s.add(MemoryRecordRow(buyer_id=buyer_id, tone=tone.value, timing=timing, paid=paid))
        outcome = "paid" if paid else "sent, awaiting reply"
        plan_note = f" with a {len(plan.installments)}-part plan" if plan else ""
        snippet = f"{tone.value} message at {timing}{plan_note} — {outcome}"
        await self.store.add(buyer_id, snippet)

    async def best_approach(self, buyer_id: str, query: str = "what worked best") -> list[str]:
        return await self.store.search(buyer_id, query, k=3)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_memory.py -v -m db`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/memory.py tests/test_memory.py
git commit -m "feat: memory service (record outcome + retrieve winning approach)"
```

---

## Task 12: Channels (protocol + SimulatedChannel)

**Files:**
- Create: `backend/app/channels/__init__.py`, `backend/app/channels/base.py`, `backend/app/channels/simulated.py`, `backend/tests/test_channels.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_channels.py`

```python
from app.channels.simulated import SimulatedChannel


def test_simulated_channel_records_send():
    ch = SimulatedChannel()
    result = ch.send(buyer_id="anand", message="Namaste", channel_kind="WhatsApp Business")
    assert result.ok is True
    assert ch.sent[0]["message"] == "Namaste"
    assert ch.sent[0]["buyer_id"] == "anand"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_channels.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `backend/app/channels/base.py`**

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass
class DispatchResult:
    ok: bool
    detail: str = ""


class Channel(Protocol):
    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult: ...
```

- [ ] **Step 4: Implement `backend/app/channels/simulated.py`**

```python
from app.channels.base import Channel, DispatchResult


class SimulatedChannel:
    """Records sends instead of calling Twilio/SMTP. Real adapters land in M3."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, buyer_id: str, message: str, channel_kind: str) -> DispatchResult:
        self.sent.append({"buyer_id": buyer_id, "message": message, "channel_kind": channel_kind})
        return DispatchResult(ok=True, detail=f"simulated via {channel_kind}")
```

- [ ] **Step 5: Create empty `backend/app/channels/__init__.py`; run tests**

Run: `python -m pytest tests/test_channels.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add app/channels tests/test_channels.py
git commit -m "feat: Channel protocol + SimulatedChannel"
```

---

## Task 13: Agents (Context, Conversation, Negotiation)

**Files:**
- Create: `backend/app/agents/__init__.py`, `backend/app/agents/context.py`, `backend/app/agents/conversation.py`, `backend/app/agents/negotiation.py`, `backend/tests/test_agents.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_agents.py`

```python
import datetime as dt

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent, NegotiationPlanOut
from app.domain.enums import InvoiceStatus, Tone
from app.domain.models import (
    Buyer, BuyerContext, Invoice, Policy, CashUrgency,
)
from app.llm.stub import StubLLM

BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
INV = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
              due_date=dt.date(2026, 5, 15), status=InvoiceStatus.OVERDUE, days_overdue=14)


class FakeStore:
    async def search(self, buyer_id, query, k=3):
        return ["gentle message at day 7 — paid"]


async def test_context_agent_builds_context():
    ctx = await ContextAgent(FakeStore()).build(BUYER, INV)
    assert ctx.on_time_rate == 0.82
    assert ctx.history_snippets == ["gentle message at day 7 — paid"]


def test_conversation_agent_returns_draft():
    llm = StubLLM(text_response="Namaste Anand ji, hope business is good.")
    ctx = BuyerContext(buyer=BUYER, invoice=INV, on_time_rate=0.82,
                       best_approach=None, history_snippets=[])
    draft = ConversationAgent(llm).draft(ctx, CashUrgency(score=0.2, breaching_need=None), thread=[])
    assert "Namaste" in draft.text
    assert draft.tone in (Tone.GENTLE, Tone.FIRM)
    # system prompt must carry the brand voice
    assert "never" in llm.calls[0][1].lower()


def test_negotiation_agent_returns_plan():
    out = NegotiationPlanOut(upfront_pct=30, extension_days=30, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 80000_00, "due_offset_days": 0},
        {"seq": 2, "label": "Installment 2", "amount_paise": 80000_00, "due_offset_days": 15},
        {"seq": 3, "label": "Installment 3", "amount_paise": 80000_00, "due_offset_days": 30},
    ])
    llm = StubLLM(structured_response=out)
    plan = NegotiationAgent(llm).propose(
        INV, Policy(max_extension_days=30, min_upfront_pct=30),
        CashUrgency(score=0.2, breaching_need=None), buyer_request="can I pay over a few weeks")
    assert plan.upfront_pct == 30
    assert plan.total_paise == 240000_00
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `backend/app/agents/context.py`**

```python
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
```

- [ ] **Step 4: Implement `backend/app/agents/conversation.py`**

```python
from app.domain.enums import Tone
from app.domain.models import BuyerContext, CashUrgency, ConversationTurn, DraftMessage
from app.llm.base import LLM
from app.money import format_inr

_SYSTEM = """You are SimplyCashIN's Conversation agent, writing on behalf of an Indian \
MSME owner to a buyer who owes money. Voice: warm, relationship-first, respectful \
Indian-English (e.g. "Namaste Anand ji, hope business is good."). Use the buyer's name. \
Firmness scales with how overdue the payment is and how urgently the owner needs cash, \
but you NEVER threaten and NEVER use collections-agency coldness. Keep it short, plain, \
and human. Output only the message text — no preamble."""


class ConversationAgent:
    def __init__(self, llm: LLM):
        self.llm = llm

    def draft(self, context: BuyerContext, urgency: CashUrgency,
              thread: list[ConversationTurn]) -> DraftMessage:
        firm = context.invoice.days_overdue >= 10 or urgency.score >= 0.5
        tone = Tone.FIRM if firm else Tone.GENTLE
        history = "\n".join(f"{t.sender}: {t.text}" for t in thread[-4:])
        user = (
            f"Buyer: {context.buyer.name} ({context.buyer.tier}), "
            f"{int(context.on_time_rate * 100)}% on-time.\n"
            f"Invoice {context.invoice.number} for {format_inr(context.invoice.amount_paise)}, "
            f"{context.invoice.days_overdue} days overdue.\n"
            f"Owner cash urgency: {urgency.score:.2f}"
            f"{' (' + urgency.breaching_need + ')' if urgency.breaching_need else ''}.\n"
            f"Desired tone: {tone.value}.\n"
            f"Recent conversation:\n{history or '(none)'}\n\n"
            f"Write the next message to the buyer."
        )
        text = self.llm.complete_text(_SYSTEM, user)
        return DraftMessage(text=text, tone=tone)
```

- [ ] **Step 5: Implement `backend/app/agents/negotiation.py`**

```python
from pydantic import BaseModel

from app.domain.models import (
    CashUrgency, Invoice, PaymentInstallment, PaymentPlan, Policy,
)
from app.llm.base import LLM
from app.money import format_inr


class _InstallmentOut(BaseModel):
    seq: int
    label: str
    amount_paise: int
    due_offset_days: int


class NegotiationPlanOut(BaseModel):
    upfront_pct: int
    extension_days: int
    installments: list[_InstallmentOut]


_SYSTEM = """You are SimplyCashIN's Negotiation agent. Propose a payment plan for an \
overdue invoice. Respect the owner's policy (minimum upfront %, maximum extension days) \
AND the owner's cash urgency: when urgency is high, demand more upfront and a shorter \
extension. Installment amounts must sum to the full invoice amount (in paise). Return \
ONLY the structured plan."""


class NegotiationAgent:
    def __init__(self, llm: LLM):
        self.llm = llm

    def propose(self, invoice: Invoice, policy: Policy, urgency: CashUrgency,
                buyer_request: str) -> PaymentPlan:
        user = (
            f"Invoice {invoice.number}: {format_inr(invoice.amount_paise)} "
            f"({invoice.amount_paise} paise), {invoice.days_overdue} days overdue.\n"
            f"Owner policy: min upfront {policy.min_upfront_pct}%, "
            f"max extension {policy.max_extension_days} days.\n"
            f"Owner cash urgency: {urgency.score:.2f}.\n"
            f"Buyer request: {buyer_request!r}.\n"
            f"Propose a plan whose installments sum to {invoice.amount_paise} paise."
        )
        out = self.llm.complete_structured(_SYSTEM, user, NegotiationPlanOut)
        return PaymentPlan(
            upfront_pct=out.upfront_pct,
            extension_days=out.extension_days,
            installments=[PaymentInstallment(seq=i.seq, label=i.label,
                                             amount_paise=i.amount_paise,
                                             due_offset_days=i.due_offset_days)
                          for i in out.installments],
        )
```

- [ ] **Step 6: Create empty `backend/app/agents/__init__.py`; run tests**

Run: `python -m pytest tests/test_agents.py -v`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add app/agents/__init__.py app/agents/context.py app/agents/conversation.py app/agents/negotiation.py tests/test_agents.py
git commit -m "feat: Context, Conversation (tone-aware), Negotiation (structured plan) agents"
```

---

## Task 14: Orchestrator

**Files:**
- Create: `backend/app/agents/orchestrator.py`, `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_orchestrator.py`

```python
import datetime as dt

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent, NegotiationPlanOut
from app.agents.orchestrator import Orchestrator, needs_negotiation
from app.channels.simulated import SimulatedChannel
from app.domain.enums import Decision, InvoiceStatus
from app.domain.models import (
    Buyer, ConversationTurn, Invoice, Owner, Policy, CashEvent,
)
from app.domain.enums import CashEventStatus, Direction
from app.llm.stub import StubLLM
from app.obs.tracer import RecordingTracer
from app.services.cash_calendar import CashCalendarService
from app.services.policy import PolicyEngine

TODAY = dt.date(2026, 5, 18)
OWNER = Owner(id="ramesh", name="Ramesh", business="SVM",
              policy=Policy(max_extension_days=30, min_upfront_pct=30))
BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
INV = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
              due_date=dt.date(2026, 5, 4), status=InvoiceStatus.OVERDUE, days_overdue=14)


class FakeStore:
    async def search(self, buyer_id, query, k=3):
        return []


class FakeMemory:
    def __init__(self):
        self.records = []

    async def record_outcome(self, **kw):
        self.records.append(kw)


def _turn(sender, text):
    return ConversationTurn(id="t", buyer_id="anand", sender=sender, agent=None,
                            text=text, created_at=dt.datetime(2026, 5, 18, 10))


def _good_plan_llm():
    out = NegotiationPlanOut(upfront_pct=30, extension_days=30, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 80000_00, "due_offset_days": 0},
        {"seq": 2, "label": "I2", "amount_paise": 80000_00, "due_offset_days": 15},
        {"seq": 3, "label": "I3", "amount_paise": 80000_00, "due_offset_days": 30},
    ])
    return StubLLM(text_response="Namaste Anand ji.", structured_response=out)


def _bad_plan_llm():
    out = NegotiationPlanOut(upfront_pct=15, extension_days=45, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 36000_00, "due_offset_days": 0},
        {"seq": 2, "label": "I2", "amount_paise": 204000_00, "due_offset_days": 45},
    ])
    return StubLLM(text_response="Namaste Anand ji.", structured_response=out)


def _orchestrator(llm, cash_events, memory):
    return Orchestrator(
        context_agent=ContextAgent(FakeStore()),
        conversation_agent=ConversationAgent(llm),
        negotiation_agent=NegotiationAgent(llm),
        cash_service=CashCalendarService(),
        policy_engine=PolicyEngine(),
        memory=memory,
        channel=SimulatedChannel(),
        tracer=RecordingTracer(),
        cash_events=cash_events,
        today=TODAY,
    )


def test_needs_negotiation_detects_request():
    assert needs_negotiation([_turn("buyer", "cash is tight, can I pay over a few weeks?")]) is True
    assert needs_negotiation([_turn("buyer", "payment done, thanks")]) is False
    assert needs_negotiation([]) is False


async def test_compliant_plan_acts_and_dispatches():
    mem = FakeMemory()
    orch = _orchestrator(_good_plan_llm(), cash_events=[], memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ACT
    assert orch.channel.sent and "Namaste" in orch.channel.sent[0]["message"]
    assert mem.records and mem.records[0]["paid"] is False


async def test_policy_breach_escalates_without_sending():
    mem = FakeMemory()
    orch = _orchestrator(_bad_plan_llm(), cash_events=[], memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ESCALATE
    assert result.escalation is not None
    assert orch.channel.sent == []          # nothing sent on escalation


async def test_high_cash_urgency_escalates_even_with_compliant_plan():
    mem = FakeMemory()
    urgent = [CashEvent(id="ce", owner_id="ramesh", direction=Direction.OUT, due_date=TODAY,
                        counterparty="GST", amount_paise=200000_00, label="GST",
                        status=CashEventStatus.PENDING)]
    orch = _orchestrator(_good_plan_llm(), cash_events=urgent, memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ESCALATE


async def test_llm_failure_escalates():
    mem = FakeMemory()
    orch = _orchestrator(StubLLM(raise_error=True), cash_events=[], memory=mem)
    result = await orch.run_cycle(OWNER, BUYER, INV,
                                  thread=[_turn("buyer", "can I pay over a few weeks?")])
    assert result.decision is Decision.ESCALATE
    assert "could not complete" in result.escalation.reason.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `app.agents.orchestrator` not found.

- [ ] **Step 3: Implement `backend/app/agents/orchestrator.py`**

```python
import datetime as dt
import uuid
from typing import Protocol

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.channels.base import Channel
from app.domain.enums import Decision, Tone
from app.domain.models import (
    Buyer, CashEvent, ConversationTurn, CycleResult, DraftMessage, Escalation,
    Invoice, Owner,
)
from app.llm.base import LLMError
from app.money import format_inr
from app.obs.tracer import Tracer
from app.services.cash_calendar import CashCalendarService
from app.services.policy import PolicyEngine

_REQUEST_KEYWORDS = ("more time", "cash is tight", "pay over", "installment",
                     "few weeks", "extension", "can i pay", "part payment")


def needs_negotiation(thread: list[ConversationTurn]) -> bool:
    if not thread:
        return False
    last = thread[-1]
    if last.sender != "buyer":
        return False
    text = last.text.lower()
    return any(k in text for k in _REQUEST_KEYWORDS)


class _Memory(Protocol):
    async def record_outcome(self, *, buyer_id: str, tone: Tone, plan, timing: str,
                             paid: bool) -> None: ...


class Orchestrator:
    def __init__(self, *, context_agent: ContextAgent, conversation_agent: ConversationAgent,
                 negotiation_agent: NegotiationAgent, cash_service: CashCalendarService,
                 policy_engine: PolicyEngine, memory: _Memory, channel: Channel,
                 tracer: Tracer, cash_events: list[CashEvent], today: dt.date):
        self.context_agent = context_agent
        self.conversation_agent = conversation_agent
        self.negotiation_agent = negotiation_agent
        self.cash_service = cash_service
        self.policy_engine = policy_engine
        self.memory = memory
        self.channel = channel
        self.tracer = tracer
        self.cash_events = cash_events
        self.today = today

    async def run_cycle(self, owner: Owner, buyer: Buyer, invoice: Invoice,
                        thread: list[ConversationTurn]) -> CycleResult:
        context = await self.context_agent.build(buyer, invoice)
        urgency = self.cash_service.urgency(self.cash_events, self.today)

        try:
            draft = self.conversation_agent.draft(context, urgency, thread)
            plan = None
            checks = []
            if needs_negotiation(thread):
                plan = self.negotiation_agent.propose(
                    invoice, owner.policy, urgency, buyer_request=thread[-1].text)
                checks = self.policy_engine.evaluate(plan, owner.policy, urgency, buyer)
        except LLMError:
            return self._escalate(
                owner, buyer, invoice, context, urgency, draft=None, plan=None, checks=[],
                reason="An agent could not complete this cycle — needs your attention.",
                recommendation="Review and follow up manually.")

        decision = Decision.ACT if all(c.ok for c in checks) else Decision.ESCALATE

        if decision is Decision.ACT:
            self.channel.send(buyer_id=buyer.id, message=draft.text,
                              channel_kind=buyer.preferred_channel)
            await self.memory.record_outcome(
                buyer_id=buyer.id, tone=draft.tone, plan=plan,
                timing=f"day {invoice.days_overdue}", paid=False)
            self.tracer.trace(agent="orchestrator", model="-", prompt=buyer.id,
                              response="ACT",
                              meta={"owner_id": owner.id, "decision": "act"})
            return CycleResult(decision=decision, context=context, draft=draft, plan=plan,
                               checks=checks, escalation=None, urgency=urgency)

        failed = [c for c in checks if not c.ok]
        reason = "; ".join(f"{c.label}: {c.value}" for c in failed)
        recommendation = ("Hold firm — request more upfront and a shorter extension, "
                          "or escalate only the balance.")
        return self._escalate(owner, buyer, invoice, context, urgency, draft=draft,
                              plan=plan, checks=checks, reason=reason,
                              recommendation=recommendation)

    def _escalate(self, owner, buyer, invoice, context, urgency, *, draft: DraftMessage | None,
                  plan, checks, reason: str, recommendation: str) -> CycleResult:
        escalation = Escalation(id=str(uuid.uuid4()), buyer_id=buyer.id,
                                amount_paise=invoice.amount_paise, reason=reason,
                                checks=checks, recommendation=recommendation)
        self.tracer.trace(agent="orchestrator", model="-", prompt=buyer.id,
                          response="ESCALATE",
                          meta={"owner_id": owner.id, "decision": "escalate", "reason": reason})
        return CycleResult(decision=Decision.ESCALATE, context=context, draft=draft, plan=plan,
                           checks=checks, escalation=escalation, urgency=urgency)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/agents/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: Orchestrator — deterministic ACT/ESCALATE, LLM-failure->escalate, memory+dispatch on act"
```

---

## Task 15: API layer (schemas, deps, routes, app)

**Files:**
- Create: `backend/app/api/__init__.py`, `backend/app/api/schemas.py`, `backend/app/api/deps.py`, `backend/app/api/routes.py`, `backend/app/api/app.py`, `backend/tests/test_api.py`

- [ ] **Step 1: Implement `backend/app/api/schemas.py`** (WFDATA-shaped responses)

```python
from pydantic import BaseModel


class BuyerOut(BaseModel):
    id: str
    name: str
    tier: str
    amount: str          # formatted ₹
    overdue: int
    status: str
    agent: str | None
    action: str
    escalated: bool


class CheckOut(BaseModel):
    label: str
    value: str
    ok: bool


class InstallmentOut(BaseModel):
    n: int
    label: str
    amount: str
    due: str


class CycleOut(BaseModel):
    decision: str
    draft: str | None
    tone: str | None
    plan: list[InstallmentOut]
    checks: list[CheckOut]
    escalation_reason: str | None
    recommendation: str | None
    urgency: float
    breaching_need: str | None


class CashDayOut(BaseModel):
    date: str
    in_dots: int
    out_dots: int


class CashItemOut(BaseModel):
    id: str
    date: str
    direction: str
    label: str
    counterparty: str
    amount: str
    done: bool


class CashCalendarOut(BaseModel):
    days: list[CashDayOut]
    week: list[CashItemOut]
```

- [ ] **Step 2: Implement `backend/app/api/deps.py`**

```python
import datetime as dt
from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import ContextAgent
from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.agents.orchestrator import Orchestrator
from app.channels.simulated import SimulatedChannel
from app.config import settings
from app.db.repositories import CashEventRepo
from app.db.session import get_session
from app.llm.base import LLM
from app.llm.stub import StubLLM
from app.obs.tracer import default_tracer
from app.retrieval.embedder import StubEmbedder
from app.retrieval.vector_store import PgVectorStore
from app.services.cash_calendar import CashCalendarService
from app.services.memory import MemoryService
from app.services.policy import PolicyEngine

OWNER_ID = "ramesh"


def get_llm() -> LLM:
    if settings.use_stub_llm or not settings.anthropic_api_key:
        return StubLLM(text_response="Namaste ji, a gentle reminder about your invoice.")
    from app.llm.anthropic_client import AnthropicClient
    return AnthropicClient()


async def get_orchestrator(
    session: AsyncSession = Depends(get_session),
    llm: LLM = Depends(get_llm),
) -> Orchestrator:
    store = PgVectorStore(session, StubEmbedder())
    cash_events = await CashEventRepo(session).for_owner(OWNER_ID)
    return Orchestrator(
        context_agent=ContextAgent(store),
        conversation_agent=ConversationAgent(llm),
        negotiation_agent=NegotiationAgent(llm),
        cash_service=CashCalendarService(),
        policy_engine=PolicyEngine(),
        memory=MemoryService(session, store),
        channel=SimulatedChannel(),
        tracer=default_tracer(),
        cash_events=cash_events,
        today=dt.date(2026, 5, 18),
    )
```

- [ ] **Step 3: Implement `backend/app/api/routes.py`**

```python
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import Orchestrator
from app.api import schemas
from app.api.deps import OWNER_ID, get_orchestrator
from app.db.repositories import (
    BuyerRepo, CashEventRepo, ConversationRepo, InvoiceRepo, OwnerRepo,
)
from app.db.session import get_session
from app.domain.enums import CashEventStatus, Direction, InvoiceStatus
from app.money import format_inr

router = APIRouter()
TODAY = dt.date(2026, 5, 18)


@router.get("/buyers", response_model=list[schemas.BuyerOut])
async def list_buyers(session: AsyncSession = Depends(get_session)):
    buyers = await BuyerRepo(session).list_for_owner(OWNER_ID)
    out = []
    for b in buyers:
        inv = await InvoiceRepo(session).latest_for_buyer(b.id)
        action = {"overdue": "Needs follow-up", "due": "Reminder scheduled",
                  "paid": "Paid in full"}[inv.status.value]
        out.append(schemas.BuyerOut(
            id=b.id, name=b.name, tier=b.tier, amount=format_inr(inv.amount_paise),
            overdue=inv.days_overdue, status=inv.status.value,
            agent=None, action=action, escalated=False))
    return out


@router.post("/buyers/{buyer_id}/run-cycle", response_model=schemas.CycleOut)
async def run_cycle(buyer_id: str, session: AsyncSession = Depends(get_session),
                    orchestrator: Orchestrator = Depends(get_orchestrator)):
    try:
        buyer = await BuyerRepo(session).get(buyer_id)
    except Exception:
        raise HTTPException(status_code=404, detail="buyer not found")
    owner = await OwnerRepo(session).get(OWNER_ID)
    invoice = await InvoiceRepo(session).latest_for_buyer(buyer_id)
    thread = await ConversationRepo(session).thread_for_buyer(buyer_id)

    result = await orchestrator.run_cycle(owner, buyer, invoice, thread)
    await session.commit()

    plan_out = []
    if result.plan:
        for i in result.plan.installments:
            due = "Today" if i.due_offset_days == 0 else f"In {i.due_offset_days} days"
            plan_out.append(schemas.InstallmentOut(
                n=i.seq, label=i.label, amount=format_inr(i.amount_paise), due=due))
    return schemas.CycleOut(
        decision=result.decision.value,
        draft=result.draft.text if result.draft else None,
        tone=result.draft.tone.value if result.draft else None,
        plan=plan_out,
        checks=[schemas.CheckOut(label=c.label, value=c.value, ok=c.ok) for c in result.checks],
        escalation_reason=result.escalation.reason if result.escalation else None,
        recommendation=result.escalation.recommendation if result.escalation else None,
        urgency=result.urgency.score,
        breaching_need=result.urgency.breaching_need,
    )


@router.get("/cash-calendar", response_model=schemas.CashCalendarOut)
async def cash_calendar(session: AsyncSession = Depends(get_session)):
    events = await CashEventRepo(session).for_owner(OWNER_ID)
    by_day: dict[dt.date, list] = {}
    for e in events:
        by_day.setdefault(e.due_date, []).append(e)
    days = []
    for day in sorted(by_day):
        evs = by_day[day]
        days.append(schemas.CashDayOut(
            date=day.isoformat(),
            in_dots=sum(1 for e in evs if e.direction == Direction.IN),
            out_dots=sum(1 for e in evs if e.direction == Direction.OUT)))
    week_end = TODAY + dt.timedelta(days=7)
    week = [schemas.CashItemOut(
        id=e.id, date=e.due_date.isoformat(), direction=e.direction.value,
        label=e.label, counterparty=e.counterparty, amount=format_inr(e.amount_paise),
        done=e.status == CashEventStatus.DONE)
        for e in events if TODAY <= e.due_date <= week_end]
    return schemas.CashCalendarOut(days=days, week=week)


@router.post("/cash-events/{event_id}/toggle", response_model=schemas.CashItemOut)
async def toggle_cash_event(event_id: str, session: AsyncSession = Depends(get_session)):
    try:
        e = await CashEventRepo(session).toggle(event_id)
    except Exception:
        raise HTTPException(status_code=404, detail="cash event not found")
    return schemas.CashItemOut(
        id=e.id, date=e.due_date.isoformat(), direction=e.direction.value,
        label=e.label, counterparty=e.counterparty, amount=format_inr(e.amount_paise),
        done=e.status == CashEventStatus.DONE)
```

- [ ] **Step 4: Implement `backend/app/api/app.py`**

```python
from fastapi import FastAPI

from app.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="SimplyCashIN", version="0.1.0")
    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 5: Write the API test** — `backend/tests/test_api.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.app import create_app
from app.api.deps import get_llm
from app.db.seed import seed
from app.db.session import get_session
from app.llm.stub import StubLLM


@pytest.mark.db
async def test_run_cycle_escalates_for_anand(session):
    await seed(session)

    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm] = lambda: StubLLM(
        text_response="Namaste Anand ji, a reminder about INV-2291.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        buyers = (await client.get("/buyers")).json()
        assert any(b["id"] == "anand" for b in buyers)

        cal = (await client.get("/cash-calendar")).json()
        assert cal["days"] and cal["week"]

        # Anand's thread ends with "pay over a few weeks" -> negotiation runs.
        # StubLLM cannot return a structured plan, so the cycle escalates (LLM error path).
        res = (await client.post("/buyers/anand/run-cycle")).json()
        assert res["decision"] == "escalate"
        assert res["escalation_reason"]
```

> Why escalate here: with the default `StubLLM` (no `structured_response`), the Negotiation call raises `LLMError`, which the Orchestrator turns into an escalation — a valid, deterministic assertion for the wired stack. A compliant-plan ACT path is covered by the unit tests in Task 14.

- [ ] **Step 6: Create empty `backend/app/api/__init__.py`; run tests**

Run: `python -m pytest tests/test_api.py -v -m db`
Expected: PASS (1 passed).

- [ ] **Step 7: Run the whole suite + start the app once**

Run: `python -m pytest -v ; uvicorn app.api.app:app --port 8000` (Ctrl-C after it boots; open `http://localhost:8000/docs`).
Expected: all non-integration tests pass; Swagger UI lists the four endpoints.

- [ ] **Step 8: Commit**

```bash
git add app/api tests/test_api.py
git commit -m "feat: FastAPI surface (buyers, run-cycle, cash-calendar, cash-event toggle) in WFDATA shapes"
```

---

## Task 16: Escalation persistence + HITL resolve endpoint

**Files:**
- Modify: `backend/app/db/models.py` (add columns to `EscalationRow`)
- Modify: `backend/app/db/repositories.py` (add `EscalationRepo`)
- Modify: `backend/app/api/schemas.py` (add `escalation_id`; add `ResolveIn`)
- Modify: `backend/app/api/routes.py` (persist escalation on ESCALATE; add resolve route)
- Test: `backend/tests/test_hitl.py`

- [ ] **Step 1: Modify `EscalationRow` in `app/db/models.py`** — add the columns the resolve flow needs (place after the existing `recommendation` column):

```python
class EscalationRow(Base):
    __tablename__ = "escalation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyer.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    draft_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 2: Write the failing test** — `backend/tests/test_hitl.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.negotiation import NegotiationPlanOut
from app.api.app import create_app
from app.api.deps import get_llm
from app.db.seed import seed
from app.db.session import get_session
from app.llm.stub import StubLLM


def _bad_plan_stub():
    # upfront 15% (<30 breach), extension 45d (>30 breach); installments sum to invoice
    bad = NegotiationPlanOut(upfront_pct=15, extension_days=45, installments=[
        {"seq": 1, "label": "Upfront", "amount_paise": 36000_00, "due_offset_days": 0},
        {"seq": 2, "label": "Balance", "amount_paise": 204000_00, "due_offset_days": 45},
    ])
    return StubLLM(text_response="Namaste Anand ji, about INV-2291.", structured_response=bad)


@pytest.mark.db
async def test_escalation_persisted_and_resolved(session):
    await seed(session)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm] = lambda: _bad_plan_stub()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = (await client.post("/buyers/anand/run-cycle")).json()
        assert res["decision"] == "escalate"
        eid = res["escalation_id"]
        assert eid

        out = (await client.post(f"/escalations/{eid}/resolve",
                                 json={"action": "approve"})).json()
        assert out["resolved"] is True
        assert out["resolution"] == "approved"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_hitl.py -v -m db`
Expected: FAIL — `escalation_id` missing from response / resolve route 404.

- [ ] **Step 4: Add `EscalationRepo` to `app/db/repositories.py`** (append at end of file)

```python
from app.domain.models import Escalation  # add to the existing imports at top


class EscalationRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def save(self, esc: Escalation, *, draft_text: str | None,
                   channel_kind: str | None) -> None:
        self.s.add(m.EscalationRow(
            id=esc.id, buyer_id=esc.buyer_id, amount_paise=esc.amount_paise,
            reason=esc.reason, recommendation=esc.recommendation,
            draft_text=draft_text, channel_kind=channel_kind, resolved=False))

    async def get(self, esc_id: str) -> m.EscalationRow:
        return (await self.s.execute(
            select(m.EscalationRow).where(m.EscalationRow.id == esc_id))).scalar_one()

    async def resolve(self, esc_id: str, resolution: str) -> m.EscalationRow:
        row = await self.get(esc_id)
        row.resolved = True
        row.resolution = resolution
        await self.s.commit()
        return row
```

- [ ] **Step 5: Add `escalation_id` to `CycleOut` and a `ResolveIn` schema in `app/api/schemas.py`**

In `CycleOut`, add the field (after `recommendation`):
```python
    escalation_id: str | None
```
Add a new schema at the end of the file:
```python
class ResolveIn(BaseModel):
    action: str            # "approve" | "edit" | "override"
    text: str | None = None
```

- [ ] **Step 6: Modify `app/api/routes.py`** — persist the escalation in `run_cycle` and add the resolve route.

In `run_cycle`, after `await session.commit()` and before building `plan_out`, persist:
```python
    if result.escalation:
        await EscalationRepo(session).save(
            result.escalation,
            draft_text=result.draft.text if result.draft else None,
            channel_kind=buyer.preferred_channel)
        await session.commit()
```
In the returned `CycleOut(...)`, add:
```python
        escalation_id=result.escalation.id if result.escalation else None,
```
Add the resolve route at the end of the file:
```python
@router.post("/escalations/{esc_id}/resolve")
async def resolve_escalation(esc_id: str, body: schemas.ResolveIn,
                             session: AsyncSession = Depends(get_session)):
    from app.channels.simulated import SimulatedChannel
    repo = EscalationRepo(session)
    try:
        row = await repo.get(esc_id)
    except Exception:
        raise HTTPException(status_code=404, detail="escalation not found")

    channel = SimulatedChannel()
    if body.action == "approve" and row.draft_text:
        channel.send(buyer_id=row.buyer_id, message=row.draft_text,
                     channel_kind=row.channel_kind or "WhatsApp Business")
        resolution = "approved"
    elif body.action == "edit" and body.text:
        channel.send(buyer_id=row.buyer_id, message=body.text,
                     channel_kind=row.channel_kind or "WhatsApp Business")
        resolution = "edited"
    elif body.action == "override":
        resolution = "overridden"
    else:
        raise HTTPException(status_code=400, detail="invalid action or missing text")

    await repo.resolve(esc_id, resolution)
    return {"id": esc_id, "resolved": True, "resolution": resolution}
```
Update the imports at the top of `routes.py` to include `EscalationRepo`:
```python
from app.db.repositories import (
    BuyerRepo, CashEventRepo, ConversationRepo, EscalationRepo, InvoiceRepo, OwnerRepo,
)
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_hitl.py -v -m db`
Expected: PASS (1 passed).

- [ ] **Step 8: Commit**

```bash
git add app/db/models.py app/db/repositories.py app/api/schemas.py app/api/routes.py tests/test_hitl.py
git commit -m "feat: HITL — persist escalations and resolve (approve/edit/override) endpoint"
```

---

## Task 17: Alembic migration (production schema)

**Files:**
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_initial.py`

> Tests build schema via `Base.metadata.create_all` (Task 3). This task gives the real, ordered migration for non-test environments.

- [ ] **Step 1: Initialize Alembic**

Run: `cd backend && alembic init migrations`
Then set `sqlalchemy.url` handling in `migrations/env.py` to read `settings.database_url` and `target_metadata = Base.metadata` (import `from app.db.base import Base` and `import app.db.models`).

- [ ] **Step 2: Create `backend/migrations/versions/0001_initial.py`** (enable pgvector, then autogenerate)

First, ensure the extension migration runs before tables. Edit the generated `upgrade()` to start with:
```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # ... autogenerated create_table calls ...
```
Generate with: `alembic revision --autogenerate -m "initial"` (with `docker compose up -d` running and `DATABASE_URL` set), then move the `CREATE EXTENSION` line to the top of `upgrade()`.

- [ ] **Step 3: Apply and verify**

Run: `alembic upgrade head`
Expected: tables created in `scin`; `alembic current` shows `0001`.

- [ ] **Step 4: Seed the dev database (manual one-off script)**

Create `backend/scripts/seed_dev.py`:
```python
import asyncio

from app.db.seed import seed
from app.db.session import SessionFactory


async def main() -> None:
    async with SessionFactory() as s:
        await seed(s)


if __name__ == "__main__":
    asyncio.run(main())
```
Run: `python scripts/seed_dev.py` then `uvicorn app.api.app:app` and hit `/buyers`.

- [ ] **Step 5: Commit**

```bash
git add alembic.ini migrations scripts/seed_dev.py
git commit -m "chore: Alembic initial migration (pgvector extension + schema) + dev seed script"
```

---

## Task 18: Integration tests against real Claude (opt-in)

**Files:**
- Create: `backend/tests/test_integration_claude.py`

- [ ] **Step 1: Write the integration test** — `backend/tests/test_integration_claude.py`

```python
import datetime as dt
import os

import pytest

from app.agents.conversation import ConversationAgent
from app.agents.negotiation import NegotiationAgent
from app.domain.enums import InvoiceStatus
from app.domain.models import Buyer, BuyerContext, Invoice, Policy, CashUrgency
from app.llm.anthropic_client import AnthropicClient

pytestmark = pytest.mark.integration

BUYER = Buyer(id="anand", owner_id="ramesh", name="Anand Motors", tier="Regular · 3 yrs",
              relationship_years=3.0, on_time_rate=0.82, preferred_channel="WhatsApp Business")
INV = Invoice(id="inv1", buyer_id="anand", number="INV-2291", amount_paise=240000_00,
              due_date=dt.date(2026, 5, 4), status=InvoiceStatus.OVERDUE, days_overdue=14)


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no API key")
def test_conversation_draft_is_warm_and_named():
    llm = AnthropicClient()
    ctx = BuyerContext(buyer=BUYER, invoice=INV, on_time_rate=0.82,
                       best_approach=None, history_snippets=[])
    draft = ConversationAgent(llm).draft(ctx, CashUrgency(score=0.3, breaching_need=None), thread=[])
    assert "Anand" in draft.text
    assert len(draft.text) > 20


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no API key")
def test_negotiation_plan_sums_to_invoice():
    llm = AnthropicClient()
    plan = NegotiationAgent(llm).propose(
        INV, Policy(max_extension_days=30, min_upfront_pct=30),
        CashUrgency(score=0.3, breaching_need=None),
        buyer_request="cash is tight, can I pay over a few weeks?")
    assert plan.total_paise == 240000_00
    assert plan.upfront_pct >= 30
    assert plan.extension_days <= 30
```

- [ ] **Step 2: Run the integration tests (requires key + network)**

Run: `python -m pytest tests/test_integration_claude.py -v -m integration`
Expected: PASS (2 passed) when `ANTHROPIC_API_KEY` is set; skipped otherwise.

> Note: real model output is non-deterministic. If `total_paise` assertion is flaky, the Negotiation prompt may need tightening (it already instructs "installments must sum to N paise") — treat a failure here as a prompt-tuning signal, not a code bug.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_claude.py
git commit -m "test: opt-in integration tests for real Claude (conversation tone, plan sums to invoice)"
```

---

## Final verification

- [ ] **Run the full default suite**

Run: `cd backend && python -m pytest -v`
Expected: all unit + db tests pass; integration tests excluded by `addopts`.

- [ ] **Boot and smoke-test the API**

Run: `docker compose up -d && python scripts/seed_dev.py && uvicorn app.api.app:app`
Then: `GET /buyers`, `GET /cash-calendar`, `POST /buyers/anand/run-cycle`, `POST /cash-events/ce2/toggle`.
Expected: each returns 200 with WFDATA-shaped JSON; run-cycle returns a decision.

- [ ] **Confirm spec coverage** — every M1 unit in the spec maps to a task:
  Context (T13) · Conversation (T13) · Negotiation (T13) · Orchestrator (T14) ·
  CashCalendarService (T9) · PolicyEngine (T10) · MemoryService (T11) ·
  Channel/Simulated (T12) · LLM seam (T6) · pgvector store (T7) · Tracer (T8) ·
  repositories (T4) · seed (T5) · API endpoints buyers/run-cycle/cash-calendar/
  cash-event toggle (T15) · HITL escalation persistence + resolve (T16) ·
  migration (T17) · integration (T18).
```
