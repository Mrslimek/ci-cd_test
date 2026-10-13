"""Async-движок и фабрика сессий SQLAlchemy.

Одна AsyncSession создаётся на один HTTP-запрос (см. app.graphql.context).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    # echo=True — каждый SQL-запрос (текст + параметры) пишется в лог
    # через logger "sqlalchemy.engine". Вместе с SQLQueryCountMiddleware
    # это даёт полную картину: какие запросы ушли и сколько их было.
    echo=settings.log_sql,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # Объекты остаются читаемыми после commit — удобно возвращать их
    # из мутаций без лишнего refresh().
    expire_on_commit=False,
    autoflush=False,
)


async def get_session():
    """FastAPI-зависимость: одна сессия на один HTTP-запрос."""
    async with AsyncSessionLocal() as session:
        yield session
