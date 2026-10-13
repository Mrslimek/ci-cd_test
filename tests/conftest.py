"""Общие фикстуры тестов.

Тесты не требуют Postgres: DATABASE_URL подменяется на файловый SQLite
ДО любого импорта app.* — engine в app.db.session создаётся в момент
импорта, позже перебиндить его нельзя. Поэтому переменная окружения
выставляется на верхнем уровне conftest (pytest импортирует его раньше
тест-модулей), а приоритет env над .env обеспечивает pydantic-settings.
"""

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="graphql-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DIR}/test.db"
os.environ["LOG_SQL"] = "false"  # не шумим SQL-логами в выводе pytest

import httpx
import pytest

from app.db.base import Base
from app.db.session import engine
from app.main import app as fastapi_app
from app.seed import create_tables, seed_if_empty


@pytest.fixture(autouse=True)
async def database():
    """Чистая база с детерминированным сидом на каждый тест.

    По окончании теста таблицы пересоздаются с нуля, а engine.dispose()
    сбрасывает пул соединений: у каждого теста свой event loop
    (pytest-asyncio), а соединение aiosqlite привязано к loop'у,
    в котором было создано.
    """
    await create_tables()
    await seed_if_empty()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client():
    """httpx-клиент поверх ASGI-приложения.

    ASGITransport не запускает lifespan — init_database (ожидание Postgres)
    в тестах не выполняется, базу готовит фикстура database.
    """
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def graphql(client):
    """Помощник: POST на /graphql и разбор JSON-ответа."""

    async def _graphql(query: str, variables: dict | None = None) -> dict:
        response = await client.post(
            "/graphql", json={"query": query, "variables": variables or {}}
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _graphql
