"""Общие фикстуры тестов.

Схема тестовой базы создаётся МИГРАЦИЯМИ (``alembic upgrade head``), а не ``create_all``: так
тот же код, которым база поднимается в проде, проверяется и тестами (AC-7).
Тестовая база — ``wallets_test`` (см. ``db/init/01-create-test-db.sql``).

Соединения берутся через ``NullPool``: пул, переживший тест, остаётся привязан к чужому event loop
и падает на «attached to a different loop». С NullPool соединение живёт ровно один запрос.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import create_engine, get_session
from app.main import app
from app.models import Wallet

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = get_settings().resolved_test_database_url


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Выполнить корутину из синхронной фикстуры: своего event loop здесь ещё нет."""
    return asyncio.run(coro)


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Накатить миграции на тестовую базу. Падение здесь означает, что AC-7 не выполнен."""
    env = {**os.environ, "WALLETS_DATABASE_URL": TEST_DATABASE_URL}
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(
            "alembic upgrade head не прошёл на тестовой базе "
            f"({TEST_DATABASE_URL}). Поднят ли контейнер с базой? `docker compose up -d db`\n"
            f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"
        )
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def test_engine(migrated_database: str) -> AsyncEngine:
    """Движок к тестовой базе. Создаётся после миграций, соединения не кэшируются (NullPool)."""
    engine = create_engine(migrated_database, poolclass=NullPool)
    yield engine
    run_async(engine.dispose())


@pytest.fixture
def session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def db(
    session_factory: async_sessionmaker[AsyncSession], test_engine: AsyncEngine
) -> AsyncIterator[AsyncSession]:
    """Сессия к тестовой базе. Таблица очищена — порядок запуска тестов ни на что не влияет."""
    async with test_engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE wallets"))
    async with session_factory() as session:
        yield session


@pytest.fixture
async def plain_client() -> AsyncIterator[AsyncClient]:
    """Клиент без подмены БД: для эндпоинтов, которым база не нужна (liveness)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession], db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент к приложению с подменённой зависимостью сессии БД (тестовая база).

    ``raise_app_exceptions=False``: необработанное исключение приходит как HTTP 500, а не как
    трейсбек посреди теста — по 500 сразу виден незакрытый путь.
    """

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
async def wallet_factory(db: AsyncSession) -> Callable[[str | Decimal], Coroutine[Any, Any, uuid.UUID]]:
    """Создать кошелёк с заданным балансом и вернуть его UUID."""

    async def _create(balance: str | Decimal = "0.00") -> uuid.UUID:
        wallet_id = uuid.uuid4()
        db.add(Wallet(id=wallet_id, balance=Decimal(str(balance))))
        await db.commit()
        return wallet_id

    return _create
