"""Батч-функции DataLoader'ов: контракт про порядок ключей и пропуски."""

from sqlalchemy import select

from app.db import models
from app.db.session import AsyncSessionLocal
from app.graphql.loaders import _load_comments_by_post_ids, _load_users_by_ids


async def test_users_by_ids_preserves_key_order():
    async with AsyncSessionLocal() as session:
        loaded = await _load_users_by_ids(session, [3, 999, 1, 3])

    # Длина и порядок результата повторяют keys; несуществующий ключ — None;
    # повторный ключ не даёт повторного запроса (кэш в рамках батча не нужен —
    # один и тот же id просто встречается в ответе дважды).
    assert [user.id if user else None for user in loaded] == [3, None, 1, 3]


async def test_comments_by_post_ids_groups_and_sorts():
    async with AsyncSessionLocal() as session:
        posts = (
            (await session.execute(select(models.Post).order_by(models.Post.id).limit(3)))
            .scalars()
            .all()
        )
        keys = [post.id for post in posts]
        loaded = await _load_comments_by_post_ids(session, [*keys, 9999])

    assert len(loaded) == 4
    assert loaded[-1] == []  # у несуществующего post_id комментариев нет

    for post_id, comments in zip(keys, loaded):
        assert all(comment.post_id == post_id for comment in comments)
        ids = [comment.id for comment in comments]
        assert ids == sorted(ids)  # внутри поста — по возрастанию id
