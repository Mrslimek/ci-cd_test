"""Корневые Query и Mutation + сборка схемы."""

import strawberry
from sqlalchemy import or_, select

from app.db import models
from app.graphql.context import GraphQLContext
from app.graphql.types import Post, PostNaive, User


def _posts_statement(
    search: str | None,
    author_id: int | None,
    limit: int,
    offset: int,
):
    """Общий построитель SELECT'а для posts и postsNaive (чтобы демо было честным)."""
    stmt = select(models.Post).order_by(models.Post.id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                models.Post.title.ilike(pattern),
                models.Post.content.ilike(pattern),
            )
        )
    if author_id is not None:
        stmt = stmt.where(models.Post.author_id == author_id)
    return stmt.limit(max(1, min(limit, 100))).offset(max(0, offset))


@strawberry.type
class Query:
    @strawberry.field
    async def posts(
        self,
        info: strawberry.Info[GraphQLContext],
        search: str | None = None,
        author_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Post]:
        """Список постов с фильтрами. Вложенные author/comments — через DataLoader."""
        stmt = _posts_statement(search, author_id, limit, offset)
        posts = (await info.context.session.execute(stmt)).scalars().all()
        return [Post.from_model(post) for post in posts]

    @strawberry.field
    async def posts_naive(
        self,
        info: strawberry.Info[GraphQLContext],
        search: str | None = None,
        author_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PostNaive]:
        """Тот же список постов, но вложенные поля решаются «в лоб» (N+1).

        Выполните posts и postsNaive с одинаковым набором полей и сравните
        счётчик SQL-запросов в логах сервера.
        """
        stmt = _posts_statement(search, author_id, limit, offset)
        posts = (await info.context.session.execute(stmt)).scalars().all()
        return [
            PostNaive(
                id=post.id,
                title=post.title,
                content=post.content,
                author_id=post.author_id,
            )
            for post in posts
        ]

    @strawberry.field
    async def user(
        self, info: strawberry.Info[GraphQLContext], id: strawberry.ID
    ) -> User | None:
        """Пользователь по ID вместе с постами (posts { ... } внутри)."""
        user = await info.context.session.get(models.User, int(id))
        return User.from_model(user) if user is not None else None


@strawberry.input
class CreatePostInput:
    title: str
    content: str
    author_id: strawberry.ID


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_post(
        self, info: strawberry.Info[GraphQLContext], input: CreatePostInput
    ) -> Post:
        """Создание поста: input-тип CreatePostInput { title, content, authorId }."""
        session = info.context.session

        author = await session.get(models.User, int(input.author_id))
        if author is None:
            # Любое исключение в Strawberry превращается в errors[0].message
            # GraphQL-ответа, при этом data остаётся null.
            raise ValueError(f"Автор с id={input.author_id} не найден")

        post = models.Post(
            title=input.title,
            content=input.content,
            author_id=author.id,
        )
        session.add(post)
        await session.commit()
        return Post.from_model(post)


schema = strawberry.Schema(query=Query, mutation=Mutation)
