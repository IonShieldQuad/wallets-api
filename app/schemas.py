"""Схемы запроса и ответа.

Деньги отдаются строками (``"1000.00"``): JSON-число на стороне клиента превращается в float
и теряет точность, а ``Decimal`` — нет. Договор зафиксирован в SPEC.md §5.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer


class OperationType(StrEnum):
    """Два значения из задания, других не существует."""

    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"


class OperationRequest(BaseModel):
    """Тело ``POST /api/v1/wallets/<uuid>/operation``. Валидация — FR-4, ошибка → 422."""

    operation_type: OperationType
    amount: Decimal = Field(
        gt=0,
        max_digits=20,
        decimal_places=2,
        description="Сумма операции: больше нуля, не более двух знаков после точки",
    )


class BalanceResponse(BaseModel):
    wallet_id: uuid.UUID
    balance: Decimal

    @field_serializer("balance")
    def _serialize_balance(self, value: Decimal) -> str:
        return f"{value:.2f}"


class OperationResponse(BalanceResponse):
    operation_type: OperationType
    amount: Decimal

    @field_serializer("amount")
    def _serialize_amount(self, value: Decimal) -> str:
        return f"{value:.2f}"
