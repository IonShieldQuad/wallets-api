"""Настройки приложения.

Читаются из окружения с префиксом ``WALLETS_`` (плюс ``.env`` при запуске на хосте).
Адрес тестовой базы — производная от основной: та же база, только имя БД с суффиксом ``_test``
(см. ``db/init/01-create-test-db.sql``), поэтому отдельная переменная нужна лишь при нетиповой раскладке.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+asyncpg://wallets:wallets@127.0.0.1:55432/wallets"
TEST_DATABASE_SUFFIX = "_test"


def derive_test_url(url: str) -> str:
    """``.../wallets`` → ``.../wallets_test``. Уже тестовый URL возвращается как есть."""
    base, _, database = url.rpartition("/")
    if not base or database.endswith(TEST_DATABASE_SUFFIX):
        return url
    return f"{base}/{database}{TEST_DATABASE_SUFFIX}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WALLETS_", env_file=".env", extra="ignore")

    database_url: str = DEFAULT_DATABASE_URL
    test_database_url: str | None = None
    log_level: str = "INFO"
    sql_echo: bool = False

    @property
    def resolved_test_database_url(self) -> str:
        return self.test_database_url or derive_test_url(self.database_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
