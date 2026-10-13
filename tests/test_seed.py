"""Сид: объёмы данных, идемпотентность и воспроизводимость."""

from sqlalchemy import delete, func, select

from app.db import models
from app.db.session import AsyncSessionLocal
from app.seed import (
    N_COMMENTS,
    N_POSTS,
    N_USERS,
    POST_TITLES,
    USERS,
    seed_if_empty,
)


async def _count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_seeded_counts():
    async with AsyncSessionLocal() as session:
        counts = (
            await _count(session, models.User),
            await _count(session, models.Post),
            await _count(session, models.Comment),
        )
    assert counts == (N_USERS, N_POSTS, N_COMMENTS)
    assert counts == (5, 20, 50)


async def test_seed_content_is_deterministic():
    async with AsyncSessionLocal() as session:
        first_post = await session.get(models.Post, 1)
        emails = [
            email for (email,) in (await session.execute(select(models.User.email).order_by(models.User.id))).all()
        ]

    # Посты создаются в порядке POST_TITLES, пользователи — в порядке USERS.
    assert first_post.title == POST_TITLES[0]
    assert emails == [email for _, email in USERS]


async def test_seed_skips_non_empty_database():
    # Фикстура database уже посеяла данные — повторный вызов ничего не делает.
    assert await seed_if_empty() is False


async def test_seed_refills_after_wipe():
    async with AsyncSessionLocal() as session:
        for model in (models.Comment, models.Post, models.User):
            await session.execute(delete(model))
        await session.commit()

    assert await seed_if_empty() is True

    async with AsyncSessionLocal() as session:
        counts = (
            await _count(session, models.User),
            await _count(session, models.Post),
            await _count(session, models.Comment),
        )
    assert counts == (N_USERS, N_POSTS, N_COMMENTS)
