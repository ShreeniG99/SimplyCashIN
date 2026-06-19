import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  (register tables)
from app.db.session import make_engine, make_session_factory


@pytest_asyncio.fixture
async def engine():
    # Function-scoped so the engine and each test share one event loop
    # (pytest-asyncio 1.x runs async tests on per-function loops). The `vector`
    # extension is pre-provisioned on Supabase by an admin; the app role cannot
    # CREATE EXTENSION, so we don't attempt it here.
    eng = make_engine(settings.test_database_url)
    try:
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
