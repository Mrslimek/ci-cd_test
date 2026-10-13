"""GraphQL-типы (code-first: схема генерируется из этих классов).

Здесь сознательно ДВЕ версии типа поста:
  * Post       — вложенные поля (author, comments) решаются через DataLoader:
                 на весь запрос уходит 1-2 батч-запроса;
  * PostNaive  — те же данные, но каждый вложенный резолвер ходит в БД
                 отдельным SELECT'ом. Это и есть N+1, оставлен для экспериментов.

Имена полей Strawberry автоматически конвертирует в camelCase:
author_id -> authorId.
"""

import strawberry
from sqlalchemy import select

from app.db import models
from app.graphql.context import GraphQLContext


@strawberry.type
class User:
    id: int
    name: str
    email: str

    @strawberry.field
    async def posts(self, info: strawberry.Info[GraphQLContext]) -> list["Post"]:
        """Посты одного пользователя. Запрос один — это не N+1 (N здесь = 1)."""
        stmt = (
            select(models.Post)
            .where(models.Post.author_id == self.id)
            .order_by(models.Post.id)
        )
        posts = (await info.context.session.execute(stmt)).scalars().all()
        return [Post.from_model(post) for post in posts]

    @classmethod
    def from_model(cls, user: models.User) -> "User":
        return cls(id=user.id, name=user.name, email=user.email)


@strawberry.type
class Comment:
    id: int
    text: str
    post_id: int
    author_id: int

    @strawberry.field
    async def author(self, info: strawberry.Info[GraphQLContext]) -> User | None:
        """Автор комментария — через тот же UserByIdLoader, что и у постов:
        все авторы (постов и комментариев) собираются в один SELECT."""
        user = await info.context.user_by_id.load(self.author_id)
        return User.from_model(user) if user is not None else None

    @classmethod
    def from_model(cls, comment: models.Comment) -> "Comment":
        return cls(
            id=comment.id,
            text=comment.text,
            post_id=comment.post_id,
            author_id=comment.author_id,
        )


@strawberry.type
class Post:
    id: int
    title: str
    content: str
    author_id: int

    @strawberry.field
    async def author(self, info: strawberry.Info[GraphQLContext]) -> User | None:
        """ОПТИМИЗИРОВАННО: все author_id батчатся в один SELECT ... IN (...)."""
        user = await info.context.user_by_id.load(self.author_id)
        return User.from_model(user) if user is not None else None

    @strawberry.field
    async def comments(self, info: strawberry.Info[GraphQLContext]) -> list[Comment]:
        """ОПТИМИЗИРОВАННО: все post_id батчатся в один SELECT ... IN (...)."""
        comments = await info.context.comments_by_post.load(self.id)
        return [Comment.from_model(comment) for comment in comments]

    @classmethod
    def from_model(cls, post: models.Post) -> "Post":
        return cls(
            id=post.id,
            title=post.title,
            content=post.content,
            author_id=post.author_id,
        )


# ----------------------------------------------------------------------------
# «Наивная» версия — каждый вложенный резолвер = отдельный SQL-запрос (N+1).
# ----------------------------------------------------------------------------


@strawberry.type
class CommentNaive:
    id: int
    text: str
    post_id: int
    author_id: int

    @strawberry.field
    async def author(self, info: strawberry.Info[GraphQLContext]) -> User | None:
        # N+1: по одному SELECT'у на КАЖДЫЙ комментарий.
        stmt = select(models.User).where(models.User.id == self.author_id)
        user = (await info.context.session.execute(stmt)).scalar_one_or_none()
        return User.from_model(user) if user is not None else None


@strawberry.type(name="PostNaive")
class PostNaive:
    """Тот же Post, но вложенные поля решаются «в лоб» — для демонстрации N+1."""

    id: int
    title: str
    content: str
    author_id: int

    @strawberry.field
    async def author(self, info: strawberry.Info[GraphQLContext]) -> User | None:
        # N+1: по одному SELECT'у на КАЖДЫЙ пост.
        stmt = select(models.User).where(models.User.id == self.author_id)
        user = (await info.context.session.execute(stmt)).scalar_one_or_none()
        return User.from_model(user) if user is not None else None

    @strawberry.field
    async def comments(self, info: strawberry.Info[GraphQLContext]) -> list[CommentNaive]:
        # N+1: по одному SELECT'у на КАЖДЫЙ пост.
        stmt = (
            select(models.Comment)
            .where(models.Comment.post_id == self.id)
            .order_by(models.Comment.id)
        )
        comments = (await info.context.session.execute(stmt)).scalars().all()
        return [
            CommentNaive(
                id=comment.id,
                text=comment.text,
                post_id=comment.post_id,
                author_id=comment.author_id,
            )
            for comment in comments
        ]
