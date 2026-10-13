"""Создание таблиц и автозаполнение БД тестовыми данными.

Запуск вручную:      uv run python -m app.seed
При `docker compose up` api-контейнер делает то же самое при старте
(см. lifespan в app.main).

Модель данных: 5 пользователей, 20 постов, 50 комментариев.
random.Random(42) — данные воспроизводимы от запуска к запуску.

Вместо Alembic здесь Base.metadata.create_all — для учебного sandbox
достаточно; миграции легко добавить позже (см. README).
"""

import asyncio
import logging
import random
import time

from sqlalchemy import func, select, text

from app.db.base import Base
from app.db.models import Comment, Post, User
from app.db.session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

N_USERS = 5
N_POSTS = 20
N_COMMENTS = 50

USERS: list[tuple[str, str]] = [
    ("Alice Johnson", "alice@example.com"),
    ("Bob Miller", "bob@example.com"),
    ("Carol Sanchez", "carol@example.com"),
    ("Dave Kim", "dave@example.com"),
    ("Eve Petrova", "eve@example.com"),
]

POST_TITLES: list[str] = [
    "Почему GraphQL: over-fetching и under-fetching в REST",
    "Схема как контракт: знакомство с SDL",
    "Резолверы: как GraphQL собирает ответ по дереву",
    "Query и Mutation: один эндпоинт вместо десятков",
    "N+1: тихая проблема каждого GraphQL-сервера",
    "DataLoader: батчинг и кэш внутри одного запроса",
    "Интроспекция: откуда GraphiQL знает вашу схему",
    "Переменные и фрагменты: переиспользуемые запросы",
    "Алиасы и директивы @skip и @include",
    "Пагинация: offset/limit против курсора",
    "Strawberry: схема из type hints",
    "SQLAlchemy 2.0: асинхронный ORM на примерах",
    "AsyncSession: одна сессия на HTTP-запрос",
    "Пул соединений: что будет под нагрузкой",
    "Кэширование резолверов: где заканчивается польза",
    "Ошибки в GraphQL: partial results и поле errors",
    "Subscriptions: realtime через WebSocket",
    "Schema-first против code-first",
    "Тестирование GraphQL API",
    "Когда GraphQL не нужен: честный взгляд",
]

POST_BODIES: list[str] = [
    "Разбираем тему на минималках, чтобы почувствовать суть без лишней теории. "
    "Попробуйте повторить примеры в GraphiQL — так усваивается быстрее всего.",
    "Смотрим под капот: открываем SQL-логи и считаем запросы. "
    "Числа убедительнее любых аргументов.",
    "Практика: берём песочницу, открываем GraphiQL и экспериментируем. "
    "Заодно наблюдаем разницу в логах сервера.",
    "Немного теории и сразу к делу: минимальный пример, который можно "
    "запустить у себя за пару минут.",
    "Итоги и чек-лист: что стоит запомнить и где легко ошибиться. "
    "Спойлер: почти всегда дело в N+1.",
]

COMMENT_TEXTS: list[str] = [
    "Спасибо, очень ясно!",
    "Жду пост про subscriptions.",
    "А как это ведёт себя под нагрузкой?",
    "Столкнулся с таким же на проде.",
    "Есть ссылка на репозиторий?",
    "Не согласен, для простого CRUD хватит REST.",
    "DataLoader кэширует по ключу в рамках запроса, верно?",
    "Сколько SQL уходит на такой запрос?",
    "Теперь вижу разницу между батчингом и кэшированием.",
    "Это же классический N+1?",
    "GraphiQL с автодополнением — восторг.",
    "Мутации сначала выглядят странно, потом привыкаешь.",
    "Добавьте пример с курсорной пагинацией, плиз.",
    "Перечитал три раза, наконец дошло.",
    "В целом согласен, но нюансы есть.",
]


async def wait_for_db(timeout_s: float = 60.0) -> None:
    """Ждём, пока Postgres примет соединения (нужно при docker compose up)."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # на старте контейнера возможны любые ошибки соединения
            if time.monotonic() >= deadline:
                raise
            logger.warning("Postgres ещё не готов (%s) — повтор через 1с", exc)
            await asyncio.sleep(1)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_if_empty() -> bool:
    """Сеет данные, только если база пуста. Возвращает True, если сеял."""
    async with AsyncSessionLocal() as session:
        user_count = await session.scalar(select(func.count()).select_from(User))
        if user_count:
            return False

        rng = random.Random(42)

        users = [User(name=name, email=email) for name, email in USERS]
        session.add_all(users)
        await session.flush()  # выделяем id до использования в постах

        posts = [
            Post(
                title=POST_TITLES[i],
                content=f"{POST_TITLES[i]}.\n\n{rng.choice(POST_BODIES)}",
                author_id=rng.choice(users).id,
            )
            for i in range(N_POSTS)
        ]
        session.add_all(posts)
        await session.flush()

        comments = [
            Comment(
                text=rng.choice(COMMENT_TEXTS),
                post_id=rng.choice(posts).id,
                author_id=rng.choice(users).id,
            )
            for _ in range(N_COMMENTS)
        ]
        session.add_all(comments)
        await session.commit()

        logger.info(
            "Засеяно: %d пользователей, %d постов, %d комментариев",
            len(users),
            len(posts),
            len(comments),
        )
        return True


async def init_database() -> None:
    await wait_for_db()
    await create_tables()
    if await seed_if_empty():
        logger.info("Сид выполнен")
    else:
        logger.info("Данные уже есть — сид пропущен")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    try:
        await init_database()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
