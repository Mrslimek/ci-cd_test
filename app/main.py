"""Точка входа: FastAPI + единственный GraphQL-эндпоинт /graphql.

Запуск локально:   uv run uvicorn app.main:app --reload
Запуск в Docker:   docker compose up --build
GraphiQL:          http://localhost:8000/graphql
"""

import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.db.query_counter import SQLQueryCountMiddleware
from app.db.session import engine
from app.graphql.context import get_context
from app.graphql.schema import schema
from app.seed import init_database

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        # Каждая SQL-строка с параметрами (echo=True у engine).
        "sqlalchemy.engine": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # Сообщения приложения (счётчик SQL, сид и т.д.).
        "app": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


def setup_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ждём Postgres (при docker compose up), создаём таблицы, сеем данные.
    await init_database()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="GraphQL Learning Sandbox", lifespan=lifespan)
    app.add_middleware(SQLQueryCountMiddleware)

    # Единый GraphQL-эндпоинт: POST /graphql — API, GET /graphql — GraphiQL IDE.
    graphql_app = GraphQLRouter(schema, context_getter=get_context)
    app.include_router(graphql_app, prefix="/graphql")

    @app.get("/")
    async def root() -> dict:
        return {
            "app": "graphql-learning-sandbox",
            "graphiql": "/graphql",
            "health": "/health",
        }

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
