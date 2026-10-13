"""GraphQL-запросы: фильтры, пагинация, вложенные поля, ошибки."""

from sqlalchemy import func, select

from app.db import models
from app.db.session import AsyncSessionLocal


async def test_posts_default_limit_returns_all_seeded(graphql):
    result = await graphql("{ posts { id title } }")
    posts = result["data"]["posts"]
    assert not result.get("errors")
    assert len(posts) == 20  # дефолтный limit=20 равен числу посаженных постов
    assert [p["id"] for p in posts] == list(range(1, 21))  # сортировка по id


async def test_posts_pagination_limit_offset(graphql):
    result = await graphql("{ posts(limit: 5, offset: 10) { id } }")
    assert [p["id"] for p in result["data"]["posts"]] == [11, 12, 13, 14, 15]


async def test_posts_limit_is_clamped(graphql):
    upper = await graphql("{ posts(limit: 1000) { id } }")
    assert len(upper["data"]["posts"]) == 20  # сверху ограничено min(limit, 100)

    lower = await graphql("{ posts(limit: 0) { id } }")
    assert len(lower["data"]["posts"]) == 1  # снизу ограничено max(limit, 1)


async def test_posts_search_is_case_insensitive(graphql):
    # В сиде «over-fetching» есть только в заголовке первого поста,
    # в тесте намеренно другой регистр — ищем без учёта регистра.
    result = await graphql('{ posts(search: "OVER-fetching") { id title } }')
    posts = result["data"]["posts"]
    assert len(posts) == 1
    assert "over-fetching" in posts[0]["title"].lower()


async def test_posts_filter_by_author_matches_database(graphql):
    result = await graphql("{ posts(authorId: 2, limit: 100) { id authorId } }")
    posts = result["data"]["posts"]

    async with AsyncSessionLocal() as session:
        expected = await session.scalar(
            select(func.count()).select_from(models.Post).where(models.Post.author_id == 2)
        )

    assert expected > 0
    assert len(posts) == expected
    assert all(p["authorId"] == 2 for p in posts)


async def test_user_with_nested_posts(graphql):
    result = await graphql('{ user(id: "3") { id name email posts { id authorId } } }')
    user = result["data"]["user"]
    assert user["id"] == 3
    assert user["name"] == "Carol Sanchez"
    assert user["email"] == "carol@example.com"
    assert user["posts"]
    assert all(p["authorId"] == 3 for p in user["posts"])


async def test_user_not_found_returns_null_without_errors(graphql):
    result = await graphql('{ user(id: "99999") { id } }')
    assert result["data"]["user"] is None
    assert not result.get("errors")


async def test_unknown_field_reports_error(graphql):
    result = await graphql("{ nonexistent }")
    assert result["errors"]
    assert result["data"] is None


async def test_posts_and_posts_naive_return_same_data(graphql):
    """Две версии типа поста читают одни и те же строки — данные совпадают."""
    optimized = (await graphql("{ posts(limit: 100) { id title content } }"))["data"]["posts"]
    naive = (await graphql("{ postsNaive(limit: 100) { id title content } }"))["data"]["postsNaive"]
    assert naive == optimized


async def test_nested_authors_and_comments_are_resolved(graphql):
    query = """
    query {
      posts(limit: 5) {
        id
        author { id name }
        comments { id text author { id name } }
      }
    }
    """
    result = await graphql(query)
    assert not result.get("errors")

    posts = result["data"]["posts"]
    assert len(posts) == 5
    for post in posts:
        assert post["author"] is not None
        assert post["author"]["name"]
        for comment in post["comments"]:
            assert comment["author"] is not None
