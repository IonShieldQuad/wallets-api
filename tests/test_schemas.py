"""Контракт запроса и ответа (SPEC.md §5) — без базы и без HTTP.

Этот модуль зелёный с самого начала: он фиксирует договор (деньги — строки, валидация суммы),
а не проверяет ещё не написанную логику.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import BalanceResponse, OperationRequest, OperationResponse, OperationType


def test_balance_is_serialized_as_string_with_two_decimals() -> None:
    """Баланс уходит строкой ``"1000.00"``: JSON-число потеряло бы точность у клиента."""
    response = BalanceResponse(wallet_id=uuid.uuid4(), balance=Decimal("1000.0"))

    payload = json.loads(response.model_dump_json())

    assert payload["balance"] == "1000.00"
    assert isinstance(payload["balance"], str)


def test_operation_response_carries_operation_amount_and_balance() -> None:
    response = OperationResponse(
        wallet_id=uuid.uuid4(),
        operation_type=OperationType.WITHDRAW,
        amount=Decimal("300"),
        balance=Decimal("700"),
    )

    payload = json.loads(response.model_dump_json())

    assert payload["operation_type"] == "WITHDRAW"
    assert payload["amount"] == "300.00"
    assert payload["balance"] == "700.00"


@pytest.mark.parametrize("amount", [1000, "1000", "1000.00", 0.01])
def test_valid_amounts_are_accepted(amount: object) -> None:
    request = OperationRequest(operation_type="DEPOSIT", amount=amount)

    assert request.amount == Decimal(str(amount))


@pytest.mark.parametrize(
    "payload",
    [
        {"operation_type": "DEPOSIT", "amount": 0},
        {"operation_type": "DEPOSIT", "amount": -5},
        {"operation_type": "WITHDRAW", "amount": "1.234"},
        {"operation_type": "TRANSFER", "amount": 1},
        {"operation_type": "deposit", "amount": 1},
        {"operation_type": "DEPOSIT"},
        {"amount": 10},
        {"operation_type": "DEPOSIT", "amount": "not-a-number"},
    ],
)
def test_invalid_requests_are_rejected(payload: dict[str, object]) -> None:
    """FR-4: сумма больше нуля и не более двух знаков, тип операции — только два значения."""
    with pytest.raises(ValidationError):
        OperationRequest(**payload)
