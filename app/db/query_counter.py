"""Счётчик SQL-запросов в рамках одного HTTP-запроса.

В логе и так виден каждый SQL (echo=True у engine), но пересчитывать строки
руками утомительно. Этот модуль добавляет итоговую строку вида:

    ▶ POST /graphql — SQL-запросов выполнено: 91

Технические детали:
  * SQLAlchemy выполняет драйверный код в greenlet'ах — contextvars при этом
    сохраняются (исправлено в SQLAlchemy 1.4.23+, см. sqlalchemy#6555).
  * Strawberry DataLoader делает батч-запросы в отдельных asyncio-задачах,
    а контекст задачи — это копия: изменение ContextVar внутри задачи не видно
    снаружи. Поэтому в ContextVar кладётся мутируемый объект-счётчик: все
    задачи ссылаются на один и тот же объект, и инкременты видны middleware.
"""

import logging
from contextvars import ContextVar
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class _QueryCounter:
    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0


_current_counter: ContextVar[_QueryCounter | None] = ContextVar(
    "sql_query_counter", default=None
)


@event.listens_for(Engine, "before_cursor_execute")
def _increment_counter(
    conn: Any,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    counter = _current_counter.get()
    if counter is not None:
        counter.value += 1


class SQLQueryCountMiddleware:
    """Чистый ASGI-middleware (без BaseHTTPMiddleware — тот ломает contextvars).

    Оборачивает каждый HTTP-запрос своим счётчиком и по завершении пишет
    итог в лог.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        counter = _QueryCounter()
        token = _current_counter.set(counter)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_counter.reset(token)
            logger.info("═" * 64)
            logger.info(
                "▶ %s %s — SQL-запросов выполнено: %s",
                scope.get("method", "?"),
                scope.get("path", "?"),
                counter.value,
            )
            logger.info("═" * 64)
