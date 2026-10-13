"""Проверка конкурентности на запущенном сервисе: параллельные HTTP-запросы, а не вызовы в процессе.

    docker compose up --build
    docker compose exec app python -m scripts.concurrency_probe --wallet <WALLET_UUID>
    # на хосте, без Docker: .venv/Scripts/python -m scripts.concurrency_probe --wallet <WALLET_UUID>

Проверяет инварианты из SPEC.md §4 на живом сервере:

* INV-1 — N параллельных DEPOSIT: ни одно обновление не теряется, итог равен сумме;
* INV-2 — M параллельных WITHDRAW: успешных ровно столько, сколько вмещает баланс,
  остальные получают 409, баланс не уходит в минус.

Скрипт **меняет баланс** указанного кошелька, поэтому ему нужен отдельный кошелёк
(`python -m scripts.seed --count 1`). Внутри — только стандартная библиотека, поэтому он запускается
и на хосте, и в контейнере (где нет dev-зависимостей вроде httpx).

Код выхода: 0 — оба инварианта выполнены, 1 — нет.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

TIMEOUT_SECONDS = 60.0


def call(method: str, url: str, payload: dict | None = None) -> tuple[int, dict | str]:
    """Один HTTP-запрос. Возвращает код ответа и тело (dict для JSON, иначе строку)."""
    request = urllib.request.Request(url, method=method)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request.data = data
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, decode(response.read())
    except urllib.error.HTTPError as error:  # 4xx/5xx — тоже ответ, а не сбой
        return error.code, decode(error.read())
    except urllib.error.URLError as error:
        raise SystemExit(f"Сервис недоступен по адресу {url}: {error.reason}") from error


def decode(raw: bytes) -> dict | str:
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def balance_of(base_url: str, wallet: str) -> Decimal:
    status, body = call("GET", f"{base_url}/api/v1/wallets/{wallet}")
    if status != 200:
        raise SystemExit(
            f"GET баланс -> {status} {body}\n"
            "Нужен UUID существующего кошелька: docker compose exec app python -m scripts.seed --count 1"
        )
    return Decimal(body["balance"])  # type: ignore[index]


def fire_parallel(base_url: str, wallet: str, operation: str, amount: Decimal, count: int) -> list[int]:
    """Отправить count одинаковых операций одновременно и вернуть коды ответов."""
    url = f"{base_url}/api/v1/wallets/{wallet}/operation"
    payload = {"operation_type": operation, "amount": str(amount)}

    def one(_: int) -> int:
        return call("POST", url, payload)[0]

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(one, range(count)))


def check(results: list[tuple[bool, str]]) -> int:
    for ok, description in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {description}")
    failed = [description for ok, description in results if not ok]
    print()
    if failed:
        print(f"ИТОГ: {len(results) - len(failed)} из {len(results)} проверок пройдено, нарушено {len(failed)}")
        return 1
    print(f"ИТОГ: все {len(results)} проверок пройдены")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка INV-1 и INV-2 на запущенном сервисе")
    parser.add_argument("--wallet", required=True, help="UUID кошелька, который можно менять")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="адрес сервиса")
    parser.add_argument("--deposits", type=int, default=50, help="сколько параллельных пополнений")
    parser.add_argument("--amount", default="10", help="сумма одного пополнения")
    parser.add_argument("--withdrawals", type=int, default=20, help="сколько параллельных списаний")
    parser.add_argument(
        "--withdraw-amount",
        default=None,
        help="сумма одного списания (по умолчанию равна --amount)",
    )
    args = parser.parse_args()

    deposit_amount = Decimal(args.amount)
    withdraw_amount = Decimal(args.withdraw_amount or args.amount)
    if deposit_amount <= 0 or withdraw_amount <= 0:
        raise SystemExit("суммы должны быть больше нуля")

    started = balance_of(args.base_url, args.wallet)
    print(f"Кошелёк {args.wallet}, стартовый баланс {started}")
    print()

    results: list[tuple[bool, str]] = []

    print(f"INV-1: {args.deposits} параллельных DEPOSIT по {deposit_amount}")
    deposit_codes = fire_parallel(args.base_url, args.wallet, "DEPOSIT", deposit_amount, args.deposits)
    expected_after_deposits = started + deposit_amount * args.deposits
    after_deposits = balance_of(args.base_url, args.wallet)
    results.append(
        (
            set(deposit_codes) == {200},
            f"все пополнения приняты (коды: {sorted(set(deposit_codes))}, ожидалось [200])",
        )
    )
    results.append(
        (
            after_deposits == expected_after_deposits,
            f"баланс {after_deposits} равен ожидаемому {expected_after_deposits} (потерянных обновлений нет)",
        )
    )

    print()
    print(f"INV-2: {args.withdrawals} параллельных WITHDRAW по {withdraw_amount} при балансе {after_deposits}")
    withdraw_codes = fire_parallel(args.base_url, args.wallet, "WITHDRAW", withdraw_amount, args.withdrawals)
    affordable = min(args.withdrawals, int(after_deposits // withdraw_amount))
    ok_count = withdraw_codes.count(200)
    conflict_count = withdraw_codes.count(409)
    after_withdrawals = balance_of(args.base_url, args.wallet)
    expected_after_withdrawals = after_deposits - withdraw_amount * affordable

    results.append(
        (
            ok_count == affordable,
            f"успешных списаний {ok_count}, ожидалось {affordable} (по балансу)",
        )
    )
    results.append(
        (
            conflict_count == args.withdrawals - affordable,
            f"отказов 409: {conflict_count}, ожидалось {args.withdrawals - affordable}",
        )
    )
    results.append(
        (
            set(withdraw_codes) <= {200, 409},
            f"других кодов нет (все: {sorted(set(withdraw_codes))})",
        )
    )
    results.append(
        (
            after_withdrawals == expected_after_withdrawals,
            f"итоговый баланс {after_withdrawals} равен ожидаемому {expected_after_withdrawals}, минуса нет",
        )
    )

    print()
    return check(results)


if __name__ == "__main__":
    raise SystemExit(main())
