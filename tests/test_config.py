"""Настройки pydantic-settings: приоритет env-переменных над .env."""

from app.config import Settings


def test_env_variable_overrides_env_file(monkeypatch):
    # .env в проекте указывает на Postgres, но env-переменная сильнее —
    # на этом держится и подмена DATABASE_URL на SQLite в conftest.
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    assert Settings().database_url == "sqlite+aiosqlite:///:memory:"


def test_log_sql_parsed_as_bool(monkeypatch):
    monkeypatch.setenv("LOG_SQL", "false")
    assert Settings().log_sql is False
    monkeypatch.setenv("LOG_SQL", "true")
    assert Settings().log_sql is True
