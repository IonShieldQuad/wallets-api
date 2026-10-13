"""Эндпоинты кошелька — критерии приёмки AC-1…AC-6 (SPEC.md §7)."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

Wallets = list[str]

OPERATION_URL = "/api/v1/wallets/{wallet_id}/operation"
BALANCE_URL = "/api/v1/wallets/{wallet_id}"


def operation(payload_type: str, amount: object) -> dict[str, object]:
    return {"operation_type": payload_type, "amount": amount}


async def test_get_balance_returns_stored_value(client: AsyncClient, wallet_factory) -> None:
    """AC-1: баланс читается из БД и отдаётся строкой с двумя знаками."""
    wallet_id = await wallet_factory("700.00")

    response = await client.get(BALANCE_URL.format(wallet_id=wallet_id))

    assert response.status_code == 200
    assert response.json() == {"wallet_id": str(wallet_id), "balance": "700.00"}


async def test_deposit_increases_balance(client: AsyncClient, wallet_factory) -> None:
    """AC-2: DEPOSIT увеличивает баланс на сумму и возвращает новое значение."""
    wallet_id = await wallet_factory("250.50")

    response = await client.post(OPERATION_URL.format(wallet_id=wallet_id), json=operation("DEPOSIT", 1000))

    assert response.status_code == 200
    assert response.json() == {
        "wallet_id": str(wallet_id),
        "operation_type": "DEPOSIT",
        "amount": "1000.00",
        "balance": "1250.50",
    }
    balance = await client.get(BALANCE_URL.format(wallet_id=wallet_id))
    assert balance.json()["balance"] == "1250.50"


async def test_withdraw_decreases_balance(client: AsyncClient, wallet_factory) -> None:
    """AC-3: WITHDRAW уменьшает баланс."""
    wallet_id = await wallet_factory("1000.00")

    response = await client.post(OPERATION_URL.format(wallet_id=wallet_id), json=operation("WITHDRAW", "300.25"))

    assert response.status_code == 200
    assert response.json()["balance"] == "699.75"


async def test_withdraw_more_than_balance_is_rejected(client: AsyncClient, wallet_factory, db: AsyncSession) -> None:
    """AC-3: снятие больше баланса → 409, баланс не меняется."""
    wallet_id = await wallet_factory("100.00")

    response = await client.post(OPERATION_URL.format(wallet_id=wallet_id), json=operation("WITHDRAW", "100.01"))

    assert response.status_code == 409
    assert response.json() == {"detail": "insufficient funds"}
    balance = await client.get(BALANCE_URL.format(wallet_id=wallet_id))
    assert balance.json()["balance"] == "100.00"


async def test_operation_on_unknown_wallet_is_404(client: AsyncClient) -> None:
    """AC-4: операция по несуществующему кошельку → 404, кошелёк не создаётся."""
    unknown = "6c1d4c68-6b3d-4e2c-9a5e-2f0a4d8b1c33"

    response = await client.post(OPERATION_URL.format(wallet_id=unknown), json=operation("DEPOSIT", 10))

    assert response.status_code == 404
    assert response.json() == {"detail": "wallet not found"}


async def test_balance_of_unknown_wallet_is_404(client: AsyncClient) -> None:
    """AC-4: баланс несуществующего кошелька → 404."""
    unknown = "0b0f2b7a-2c4b-4a1e-9c39-7d5f2a1b8e44"

    response = await client.get(BALANCE_URL.format(wallet_id=unknown))

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [operation("DEPOSIT", 0), operation("DEPOSIT", -1), operation("WITHDRAW", "1.234"), operation("TRANSFER", 5)],
)
async def test_invalid_operation_body_is_422(client: AsyncClient, wallet_factory, payload: dict) -> None:
    """AC-4: невалидное тело → 422 (FR-4)."""
    wallet_id = await wallet_factory("10.00")

    response = await client.post(OPERATION_URL.format(wallet_id=wallet_id), json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("wallet_id", ["not-a-uuid", "12345"])
async def test_malformed_uuid_is_422(client: AsyncClient, wallet_id: str) -> None:
    """AC-4: UUID в пути невалиден → 422."""
    response = await client.get(BALANCE_URL.format(wallet_id=wallet_id))

    assert response.status_code == 422


@pytest.mark.slow
async def test_concurrent_deposits_lose_no_updates(client: AsyncClient, wallet_factory) -> None:
    """AC-5 / INV-1: 50 параллельных DEPOSIT по 10 → ровно "500.00", ни одно не потеряно."""
    wallet_id = await wallet_factory("0.00")

    responses = await asyncio.gather(
        *[client.post(OPERATION_URL.format(wallet_id=wallet_id), json=operation("DEPOSIT", 10)) for _ in range(50)]
    )

    assert {response.status_code for response in responses} == {200}
    balance = await client.get(BALANCE_URL.format(wallet_id=wallet_id))
    assert balance.json()["balance"] == "500.00"


@pytest.mark.slow
async def test_concurrent_withdrawals_do_not_overdraw(client: AsyncClient, wallet_factory) -> None:
    """AC-6 / INV-2: 20 параллельных WITHDRAW по 100 при балансе 1000 → 10×200, 10×409, баланс "0.00"."""
    wallet_id = await wallet_factory("1000.00")

    responses = await asyncio.gather(
        *[client.post(OPERATION_URL.format(wallet_id=wallet_id), json=operation("WITHDRAW", 100)) for _ in range(20)]
    )
    codes = [response.status_code for response in responses]

    assert codes.count(200) == 10
    assert codes.count(409) == 10
    balance = await client.get(BALANCE_URL.format(wallet_id=wallet_id))
    assert balance.json()["balance"] == "0.00"
