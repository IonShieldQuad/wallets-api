"""Сервисный слой: операции над кошельком (SPEC.md §3, §4).

Правила:
* одна операция = одна транзакция, коммит делается здесь, а не в роутере;
* «прочитал → посчитал → записал» без блокировки строки и без условия в ``WHERE`` недопустимо:
  такой код теряет обновления при параллельных запросах (SPEC.md §4, INV-1…INV-3);
* нет кошелька → ``WalletNotFoundError``; не хватает средств → ``InsufficientFundsError``.

Два допустимых механизма (выбрать один и обосновать в ADR):
  (a) ``SELECT … FOR UPDATE`` — блокировка строки на время транзакции, изменение в Python;
  (b) один атомарный ``UPDATE wallets SET balance = balance + :delta WHERE id = :id
      [AND balance + :delta >= 0]`` с проверкой ``rowcount``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Wallet
from app.schemas import OperationType


class WalletService:
    """Операции над кошельками в рамках одной сессии БД."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_wallet(self, wallet_id: uuid.UUID) -> Wallet:
        """Вернуть кошелёк или поднять ``WalletNotFoundError``.

        TODO: см. SPEC.md §3 (FR-2) и §5 (коды ответов).
        """
        raise NotImplementedError("TODO: SPEC.md §3 FR-2, §5")

    async def apply_operation(self, wallet_id: uuid.UUID, operation: OperationType, amount: Decimal) -> Wallet:
        """Применить DEPOSIT/WITHDRAW и вернуть кошелёк с новым балансом.

        TODO: базовый сценарий — SPEC.md §3 (FR-1, FR-3, FR-4).
        TODO: корректность под параллельными запросами — SPEC.md §4 (INV-1…INV-3).
        """
        raise NotImplementedError("TODO: SPEC.md §3 и §4")
