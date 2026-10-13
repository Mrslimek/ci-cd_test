"""GraphQL-контекст: то, что доступно резолверам через info.context.

Создаётся на каждый HTTP-запрос: своя AsyncSession и свои экземпляры
DataLoader (их кэш живёт ровно один запрос — как и задумано).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import BaseContext

from app.db.session import AsyncSessionLocal
from app.graphql.loaders import CommentsByPostIdLoader, UserByIdLoader


@dataclass
class GraphQLContext(BaseContext):
    """BaseContext даёт доступ к info.context.request/response."""

    session: AsyncSession
    user_by_id: UserByIdLoader
    comments_by_post: CommentsByPostIdLoader


async def get_context() -> AsyncIterator[GraphQLContext]:
    """Dependency для GraphQLRouter (generator-with-yield закрывает сессию)."""
    async with AsyncSessionLocal() as session:
        yield GraphQLContext(
            session=session,
            user_by_id=UserByIdLoader(session),
            comments_by_post=CommentsByPostIdLoader(session),
        )
