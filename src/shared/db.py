from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.shared.config import get_settings


def create_engine(database_url: str | None = None):
    url = database_url or get_settings().DATABASE_URL
    return create_async_engine(url, echo=False)


def create_session_factory(engine=None) -> async_sessionmaker[AsyncSession]:
    if engine is None:
        engine = create_engine()
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(
    factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    if factory is None:
        factory = create_session_factory()
    async with factory() as session:
        yield session
