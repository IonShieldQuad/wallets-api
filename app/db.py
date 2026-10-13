"""Асинхронный движок, фабрика сессий и зависимость для эндпоинтов."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def create_engine(url: str, *, echo: bool = False, poolclass: type | None = None) -> AsyncEngine:
    """Движок по URL. ``poolclass=NullPool`` используется тестами: соединение на запрос,
    оно не переживает тест и не привязывается к чужому event loop."""
    kwargs: dict[str, object] = {"echo": echo, "pool_pre_ping": True}
    if poolclass is not None:
        kwargs["poolclass"] = poolclass
    return create_async_engine(url, **kwargs)


_settings = get_settings()
engine: AsyncEngine = create_engine(_settings.database_url, echo=_settings.sql_echo)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI: одна сессия на запрос. Переопределяется в тестах (tests/conftest.py)."""
    async with SessionFactory() as session:
        yield session
