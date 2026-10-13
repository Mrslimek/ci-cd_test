"""SQLQueryCountMiddleware: счётчик живёт ровно в рамках HTTP-запроса."""

from sqlalchemy import text

from app.db.query_counter import SQLQueryCountMiddleware, _current_counter
from app.db.session import AsyncSessionLocal


async def _noop_receive():
    return {"type": "http.request"}


async def _noop_send(message):
    pass


async def test_counter_counts_sql_within_request_scope():
    seen = {}

    async def inner_app(scope, receive, send):
        seen["start"] = _current_counter.get().value
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            await session.execute(text("SELECT 1"))
        seen["end"] = _current_counter.get().value

    middleware = SQLQueryCountMiddleware(inner_app)
    await middleware(
        {"type": "http", "method": "POST", "path": "/graphql"},
        _noop_receive,
        _noop_send,
    )

    assert seen == {"start": 0, "end": 2}
    # После запроса счётчик снят: SQL вне HTTP-запроса не считается.
    assert _current_counter.get() is None


async def test_non_http_scopes_pass_through_untouched():
    seen = {}

    async def inner_app(scope, receive, send):
        seen["scope_type"] = scope["type"]

    middleware = SQLQueryCountMiddleware(inner_app)
    await middleware({"type": "lifespan"}, _noop_receive, _noop_send)

    assert seen["scope_type"] == "lifespan"
    assert _current_counter.get() is None
