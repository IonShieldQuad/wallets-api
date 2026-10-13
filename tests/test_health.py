"""Health-эндпоинты (SPEC.md §3, FR-6)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_liveness_returns_ok(plain_client: AsyncClient) -> None:
    """Процесс жив: 200 без обращения к базе (работает и без поднятого Postgres)."""
    response = await plain_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_returns_ok_when_database_available(client: AsyncClient) -> None:
    """Готовность: 200, когда база отвечает."""
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
