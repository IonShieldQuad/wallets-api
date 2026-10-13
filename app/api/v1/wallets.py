"""Два эндпоинта из задания = HTTP-обвязка вокруг сервисного слоя.

Здесь только контракт: разбор пути и тела, вызов сервиса, перевод доменных ошибок в коды
ответа (SPEC.md §5). Логика изменения баланса — в ``app/service.py``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import InsufficientFundsError, WalletNotFoundError
from app.schemas import BalanceResponse, OperationRequest, OperationResponse
from app.service import WalletService

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post(
    "/{wallet_id}/operation",
    response_model=OperationResponse,
    summary="Изменить баланс кошелька",
    responses={
        404: {"description": "Кошелька с таким UUID нет"},
        409: {"description": "Недостаточно средств для списания"},
        422: {"description": "Невалидное тело запроса или UUID"},
    },
)
async def apply_wallet_operation(
    wallet_id: uuid.UUID,
    payload: OperationRequest,
    session: AsyncSession = Depends(get_session),
) -> OperationResponse:
    service = WalletService(session)
    try:
        wallet = await service.apply_operation(wallet_id, payload.operation_type, payload.amount)
    except WalletNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="wallet not found") from exc
    except InsufficientFundsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="insufficient funds") from exc

    return OperationResponse(
        wallet_id=wallet.id,
        operation_type=payload.operation_type,
        amount=payload.amount,
        balance=wallet.balance,
    )


@router.get(
    "/{wallet_id}",
    response_model=BalanceResponse,
    summary="Получить баланс кошелька",
    responses={404: {"description": "Кошелька с таким UUID нет"}, 422: {"description": "UUID невалиден"}},
)
async def get_wallet_balance(
    wallet_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> BalanceResponse:
    service = WalletService(session)
    try:
        wallet = await service.get_wallet(wallet_id)
    except WalletNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="wallet not found") from exc

    return BalanceResponse(wallet_id=wallet.id, balance=wallet.balance)
