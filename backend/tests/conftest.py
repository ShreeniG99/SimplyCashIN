import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (register tables)
from app.db.session import make_engine, make_session_factory


async def _ensure_test_database(url_str: str) -> None:
    """Create the test database if missing (fresh docker-compose volume).
    Best-effort: hosted roles may lack CREATEDB — there the DB must already
    exist, and any error here falls through to the engine fixture's skip."""
    url = make_url(url_str)
    admin = create_async_engine(url.set(database="postgres"),
                                isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": url.database})
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        await admin.dispose()


@pytest_asyncio.fixture
async def engine():
    # Function-scoped so the engine and each test share one event loop
    # (pytest-asyncio 1.x runs async tests on per-function loops).
    try:
        await _ensure_test_database(settings.test_database_url)
    except Exception:  # noqa: BLE001 — hosted Postgres without CREATEDB
        pass
    eng = make_engine(settings.test_database_url)
    try:
        # Own transaction so a permission error (Supabase pre-provisions the
        # extension; the app role cannot CREATE EXTENSION) doesn't poison the
        # schema-creation transaction below.
        try:
            async with eng.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:  # noqa: BLE001
            pass
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001
        await eng.dispose()
        pytest.skip(f"Postgres+pgvector not available: {exc}")
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = make_session_factory(engine)
    async with factory() as s:
        yield s
