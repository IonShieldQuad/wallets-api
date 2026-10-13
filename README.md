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

## Проверено

| Что | Чем подтверждено |
|---|---|
| Оба эндпоинта, коды ответов, формат денег | 30 тестов `pytest`, включая валидацию входа и оба конкурентных сценария |
| Конкурентность: нет потерянных обновлений, баланс не уходит в минус | `scripts/concurrency_probe.py` против запущенного сервиса: 100 параллельных `DEPOSIT` по 10 → баланс ровно `1000.00`; 20 параллельных `WITHDRAW` по 100 → 10 успехов, 10 отказов `409`, баланс `0.00` |
| Миграции | `alembic upgrade head` → `downgrade base` → `upgrade head` на чистой базе: схема создаётся, удаляется и создаётся заново |
| «Одна команда» и сценарий из README | `docker compose up --build`, оба контейнера healthy, запросы дают указанные ответы и коды |
| PEP8 | `ruff check .` и `ruff format --check .` — без замечаний |

Проверка конкурентности воспроизводится на запущенном сервисе. Скрипт меняет баланс,
поэтому ему нужен отдельный кошелёк:

```bash
docker compose exec app python -m scripts.seed --count 1
docker compose exec app python -m scripts.concurrency_probe --wallet <WALLET_UUID> --deposits 100 --amount 10 --withdrawals 20 --withdraw-amount 100
```

## Эндпоинты

**Проще всего проверить руками здесь: <http://127.0.0.1:8000/docs>** — интерактивная документация
FastAPI, где запрос отправляется кнопкой «Execute» и ничего не нужно экранировать.

Ниже — те же запросы через curl. Команды специально **одной строкой** и с двойными кавычками:
в cmd.exe обратный слэш не переносит строку (там нужен `^`), а одинарные кавычки вокруг JSON
передаются в curl буквально — он получает невалидный JSON и отвечает `json_invalid`.
Вариант ниже работает и в cmd.exe, и в bash.

### Изменение баланса

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>/operation" -H "Content-Type: application/json" -d "{\"operation_type\": \"DEPOSIT\", \"amount\": 1000}"
# → 200 {"wallet_id":"<uuid>","balance":"1000.00","operation_type":"DEPOSIT","amount":"1000.00"}

curl -s -X POST "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>/operation" -H "Content-Type: application/json" -d "{\"operation_type\": \"WITHDRAW\", \"amount\": 300}"
# → 200 {"wallet_id":"<uuid>","balance":"700.00","operation_type":"WITHDRAW","amount":"300.00"}

curl -s -X POST "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>/operation" -H "Content-Type: application/json" -d "{\"operation_type\": \"WITHDRAW\", \"amount\": 100000}"
# → 409 {"detail":"insufficient funds"}   (и баланс не меняется)
```

### Получение баланса

```bash
curl -s "http://127.0.0.1:8000/api/v1/wallets/<WALLET_UUID>"
# → 200 {"wallet_id":"<uuid>","balance":"700.00"}

curl -s "http://127.0.0.1:8000/api/v1/wallets/6c1d4c68-6b3d-4e2c-9a5e-2f0a4d8b1c33"
# → 404 {"detail":"wallet not found"}
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
.venv/Scripts/python -m pytest                     # на хосте: быстро и видит свежие файлы
.venv/Scripts/python -m pytest -m "not slow"        # без тяжёлых проверок конкурентности
docker compose run --rm --build app pytest          # в контейнере; --build нужен после правки кода
```

Линтер (PEP8-часть задания):

```bash
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
```

## Миграции

```bash
# новая миграция после правки app/models.py
.venv/Scripts/python -m alembic revision --autogenerate -m "create wallets"
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m alembic downgrade -1
```

Генерация идёт **на хосте**, через venv: контейнер `app` собран из копии кода, поэтому файл,
созданный внутри `docker compose run`, останется в контейнере и пропадёт вместе с ним.
(В cmd.exe путь тот же: `.venv\Scripts\python -m alembic …` — или активировать venv и звать
`alembic` напрямую.)

Обычно `alembic upgrade head` вручную не нужен: контейнер `app` применяет миграции перед стартом
uvicorn, а тесты накатывают их сами (`tests/conftest.py`).

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
scripts/concurrency_probe.py   параллельные запросы к запущенному сервису (INV-1, INV-2)
```


