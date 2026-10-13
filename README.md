# Wallets API — тестовое задание на Python-разработчика.

REST API для работы с кошельками пользователей: изменить баланс, получить баланс.

**Стек:** FastAPI (async) · PostgreSQL 16 · SQLAlchemy 2.0 async + asyncpg · Alembic · pytest · Docker Compose.
**Спецификация и критерии приёмки:** [SPEC.md](SPEC.md). Решения и их альтернативы: [DECISIONS.md](DECISIONS.md).

---

## Быстрый старт

Вся система поднимается одной командой (миграции применяются автоматически перед стартом API):

```bash
docker compose up --build
```

Проверка:

```bash
curl -s http://127.0.0.1:8000/health/live
```

Создать пару кошельков и увидеть рабочий сценарий целиком:

```bash
docker compose exec app python -m scripts.seed --count 2
```

Дальше — сценарий из раздела «Эндпоинты» (подставить выданный UUID).

Остановить:

```bash
docker compose down          # контейнеры и сеть
docker compose down -v       # ещё и данные Postgres
```

## Эндпоинты

### Изменение баланса

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>/operation" \
     -H "Content-Type: application/json" \
     -d '{"operation_type": "DEPOSIT", "amount": 1000}'
# → 200 {"wallet_id": "<uuid>", "operation_type": "DEPOSIT", "amount": "1000.00", "balance": "1000.00"}

curl -s -X POST "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>/operation" \
     -H "Content-Type: application/json" \
     -d '{"operation_type": "WITHDRAW", "amount": 300}'
# → 200 {"wallet_id": "<uuid>", "operation_type": "WITHDRAW", "amount": "300.00", "balance": "700.00"}
```

### Получение баланса

```bash
curl -s "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>"
# → 200 {"wallet_id": "<uuid>", "balance": "700.00"}
```

### Коды ответов

| Ситуация | Код |
|---|---|
| Успех | `200` |
| Кошелька с таким UUID нет | `404` |
| Снятие больше баланса | `409` `insufficient funds` |
| `amount ≤ 0`, больше 2 знаков после точки, неизвестный `operation_type` | `422` |
| `WALLET_UUID` не UUID | `422` |

## Тесты

Тесты идут против отдельной базы `wallets_test` (создаётся автоматически при первом старте контейнера `db`).
Нужен только контейнер с базой:

```bash
docker compose up -d db
docker compose run --rm app pytest            # весь набор
docker compose run --rm app pytest -m "not slow"   # без тяжёлых проверок конкурентности
```

Или на хосте, без Docker:

```bash
.venv/Scripts/python -m pytest
```

Линтер (PEP8-часть задания):

```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
```

## Миграции

```bash
# новая миграция после правки app/models.py
docker compose run --rm app alembic revision --autogenerate -m "create wallets"
docker compose run --rm app alembic upgrade head
docker compose run --rm app alembic downgrade -1
```

`alembic upgrade head` вручную не нужен: контейнер `app` применяет миграции перед стартом uvicorn.

## Конфигурация

Настройки читаются из окружения с префиксом `WALLETS_` (см. `.env.example`).
Порт базы наружу — **55432**, а не 5432: на этой машине 5432 занят локальным PostgreSQL 18.
Внутри сети compose контейнеры видят друг друга по обычному `db:5432`.
При запуске через `docker compose` их подставляет compose — `.env` для этого не нужен.
Для запуска на хосте скопировать шаблон и указать адрес своей базы:

```bash
cp .env.example .env
```

| Переменная | Значение по умолчанию |
|---|---|
| `WALLETS_DATABASE_URL` | `postgresql+asyncpg://wallets:wallets@127.0.0.1:55432/wallets` |
| `WALLETS_TEST_DATABASE_URL` | тот же URL с базой `wallets_test` (выводится автоматически) |
| `WALLETS_LOG_LEVEL` | `INFO` |
| `WALLETS_SQL_ECHO` | `false` |

## Структура

```
app/
  main.py            FastAPI-приложение, подключение роутера, /health/live, /health/ready
  config.py          настройки (pydantic-settings, префикс WALLETS_)
  db.py              async-движок, фабрика сессий, зависимость get_session
  models.py          SQLAlchemy-модель Wallet
  schemas.py         pydantic-схемы запроса/ответа
  errors.py          доменные ошибки (нет кошелька, недостаточно средств)
  service.py         сервисный слой: операции над кошельком
  api/v1/wallets.py  два эндпоинта из задания
alembic/             миграции (env.py настроен на async-движок)
tests/               pytest: conftest.py + тесты по критериям приёмки
scripts/seed.py      создать кошельки для ручной проверки
```


