"""Настройки приложения (pydantic-settings).

Значения по умолчанию можно переопределить переменными окружения или файлом .env.
Переменные окружения имеют приоритет над .env — поэтому в docker compose
достаточно прописать DATABASE_URL в environment сервиса.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://graphql:graphql@localhost:5433/graphql"

    # Логировать каждый SQL-запрос SQLAlchemy (echo=True у engine).
    # Нужно для наглядной демонстрации N+1 vs DataLoader.
    log_sql: bool = True


settings = Settings()
