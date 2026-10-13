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

from app.errors import InsufficientFundsError, WalletNotFoundError
from app.models import Wallet
from app.schemas import OperationType


class WalletService:
    """Операции над кошельками в рамках одной сессии БД."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_wallet(self, wallet_id: uuid.UUID) -> Wallet:
        """Вернуть кошелёк или поднять ``WalletNotFoundError``."""

        wallet = await self._session.get(Wallet, wallet_id)
        if wallet is None:
            raise WalletNotFoundError(wallet_id)
        return wallet

    async def apply_operation(self, wallet_id: uuid.UUID, operation: OperationType, amount: Decimal) -> Wallet:
        """Применить DEPOSIT/WITHDRAW и вернуть кошелёк с новым балансом."""

        async with self._session.begin():
            wallet = await self._session.get(Wallet, wallet_id, with_for_update=True)
            if wallet is None:
                raise WalletNotFoundError(wallet_id)
            if operation == OperationType.DEPOSIT:
                wallet.balance += amount
            else:
                if wallet.balance < amount:
                    raise InsufficientFundsError(wallet_id, wallet.balance, amount)
                wallet.balance -= amount
        return wallet
