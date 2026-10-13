"""Создать кошельки для ручной проверки.

    docker compose exec app python -m scripts.seed --count 2
    .venv/Scripts/python -m scripts.seed --count 2        # на хосте, с поднятым контейнером db

Печатает UUID и готовые curl-команды: проверяющему не нужно заходить в psql.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from decimal import Decimal

from app.db import SessionFactory
from app.models import Wallet


async def create_wallets(count: int, balance: Decimal) -> list[uuid.UUID]:
    async with SessionFactory() as session:
        wallets = [Wallet(id=uuid.uuid4(), balance=balance) for _ in range(count)]
        session.add_all(wallets)
        await session.commit()
        return [wallet.id for wallet in wallets]


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать кошельки для проверки API")
    parser.add_argument("--count", type=int, default=1, help="сколько кошельков создать")
    parser.add_argument("--balance", default="0.00", help="стартовый баланс каждого кошелька")
    args = parser.parse_args()

    wallets = asyncio.run(create_wallets(args.count, Decimal(args.balance)))

    print(f"Создано кошельков: {len(wallets)} (баланс {args.balance})")
    for wallet_id in wallets:
        print(f"  {wallet_id}")
    if wallets:
        first = wallets[0]
        print("\nПроверка:")
        print(f"  curl -s http://127.0.0.1:8000/api/v1/wallets/{first}")
        print(
            f"  curl -s -X POST http://127.0.0.1:8000/api/v1/wallets/{first}/operation "
            """-H "Content-Type: application/json" -d '{"operation_type": "DEPOSIT", "amount": 1000}'"""
        )


if __name__ == "__main__":
    main()
