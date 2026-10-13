"""Модели БД.

Схема создаётся миграциями Alembic (NFR-2), а не ``create_all`` — иначе миграции и модель
расходятся, и это выясняется на чистой базе у проверяющего.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        # FR-5: отрицательный баланс невозможен на уровне БД, а не только по коду приложения.
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - отладочный вывод
        return f"Wallet(id={self.id!r}, balance={self.balance!r})"
