# Wallets API — воспроизводимый контейнер.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

RUN groupadd --system app && useradd --system --gid app --home-dir /srv app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY tests ./tests

RUN chown -R app:app /srv
USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3).status == 200 else 1)"]

# «Одна команда» из задания поднимает и схему, и сервис: миграции идут перед uvicorn.
# Один воркер намеренно: корректность под параллельными запросами обеспечивается в БД (SPEC §4),
# а не в памяти процесса, поэтому число воркеров на неё не влияет.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
