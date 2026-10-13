"""Точка входа FastAPI: сборка приложения, роутеры, health-эндпоинты."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.wallets import router as wallets_router
from app.config import get_settings
from app.db import get_session

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(
        title="Wallets API",
        version="0.1.0",
        description="REST API для работы с кошельками. Спецификация — SPEC.md в корне репозитория.",
    )
    app.include_router(wallets_router, prefix="/api/v1")

    @app.get("/health/live", tags=["health"], summary="Процесс жив (БД не проверяется)")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/health/ready",
        tags=["health"],
        summary="БД отвечает (иначе 503)",
        responses={503: {"description": "База недоступна"}},
    )
    async def health_ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
        try:
            await session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - readiness обязан отдать 503, а не 500
            logger.warning("readiness probe failed: %s", exc)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable") from exc
        return {"status": "ok"}

    return app


app = create_app()
