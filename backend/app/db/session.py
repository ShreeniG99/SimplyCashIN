from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)

from app.config import settings


def make_engine(url: str | None = None) -> AsyncEngine:
    url = url or settings.database_url
    # Hosted Postgres (e.g. Supabase) requires TLS; local docker does not.
    connect_args: dict = {}
    if "localhost" not in url and "127.0.0.1" not in url:
        connect_args["ssl"] = "require"
    return create_async_engine(url, future=True, connect_args=connect_args)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


_engine = make_engine()
SessionFactory = make_session_factory(_engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
