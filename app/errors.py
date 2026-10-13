"""Доменные ошибки сервисного слоя.

Сервис не знает про HTTP: он поднимает эти исключения, а роутер переводит их в коды
из SPEC.md §5. Так коды ответов описаны в одном месте, а не размазаны по логике.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID


class WalletNotFoundError(Exception):
    """Кошелька с таким UUID нет в БД → 404."""

    def __init__(self, wallet_id: UUID) -> None:
        super().__init__(f"wallet not found: {wallet_id}")
        self.wallet_id = wallet_id


class InsufficientFundsError(Exception):
    """Снятие больше баланса → 409."""

    def __init__(self, wallet_id: UUID, balance: Decimal, amount: Decimal) -> None:
        super().__init__(f"insufficient funds: balance={balance}, amount={amount}")
        self.wallet_id = wallet_id
        self.balance = balance
        self.amount = amount
