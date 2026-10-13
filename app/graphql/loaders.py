"""Strawberry DataLoaders — решение проблемы N+1.

Идея DataLoader:
  * во время выполнения GraphQL-запроса резолверы полей вызываются для каждого
    объекта отдельно (20 постов -> 20 вызовов Post.author);
  * вместо того чтобы каждый раз ходить в БД, резолвер вызывает load(key) —
    DataLoader собирает все ключи в рамках одного тика event loop
    и выполняет ОДИН запрос SELECT ... WHERE id IN (...);
  * дополнительно DataLoader кэширует результаты по ключу в рамках запроса:
    если 10 постов одного автора, его пользователь будет прочитан 1 раз.

API Strawberry (актуальные версии): в конструктор DataLoader передаётся
батч-функция load_fn(keys) -> список результатов. Контракт: длина и порядок
результата должны совпадать с keys; для отсутствующих ключей — None.
"""

from collections import defaultdict
from functools import partial

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.dataloader import DataLoader

from app.db import models


async def _load_users_by_ids(
    session: AsyncSession, keys: list[int]
) -> list["models.User | None"]:
    """Батч-функция для Post/Comment -> User: один SELECT на весь список ключей."""
    result = await session.execute(
        select(models.User).where(models.User.id.in_(keys))
    )
    users_by_id = {user.id: user for user in result.scalars()}
    return [users_by_id.get(key) for key in keys]


async def _load_comments_by_post_ids(
    session: AsyncSession, keys: list[int]
) -> list[list["models.Comment"]]:
    """Батч-функция для Post -> Comments: один SELECT на весь список ключей."""
    result = await session.execute(
        select(models.Comment)
        .where(models.Comment.post_id.in_(keys))
        .order_by(models.Comment.id)
    )
    comments_by_post: dict[int, list[models.Comment]] = defaultdict(list)
    for comment in result.scalars():
        comments_by_post[comment.post_id].append(comment)
    return [comments_by_post[post_id] for post_id in keys]


class UserByIdLoader(DataLoader[int, "models.User | None"]):
    """Батч-загрузка авторов по списку user_id."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(load_fn=partial(_load_users_by_ids, session))


class CommentsByPostIdLoader(DataLoader[int, list["models.Comment"]]):
    """Батч-загрузка комментариев по списку post_id."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(load_fn=partial(_load_comments_by_post_ids, session))
