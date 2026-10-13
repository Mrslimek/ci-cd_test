"""Мутация createPost: успех, ошибка несуществующего автора, валидация."""

CREATE_POST = """
mutation ($input: CreatePostInput!) {
  createPost(input: $input) {
    id
    title
    content
    authorId
    author { id name }
  }
}
"""


async def test_create_post(graphql):
    result = await graphql(
        CREATE_POST,
        {"input": {"title": "Из теста", "content": "Создано мутацией", "authorId": "2"}},
    )
    assert not result.get("errors")

    post = result["data"]["createPost"]
    assert post["id"] == 21  # сид занимает id 1..20
    assert post["title"] == "Из теста"
    assert post["content"] == "Создано мутацией"
    assert post["authorId"] == 2
    assert post["author"]["name"] == "Bob Miller"

    # Пост виден последующим запросом с фильтром по автору.
    listing = await graphql("{ posts(authorId: 2, limit: 100) { id } }")
    assert post["id"] in [p["id"] for p in listing["data"]["posts"]]


async def test_create_post_with_unknown_author_fails(graphql):
    result = await graphql(
        CREATE_POST,
        {"input": {"title": "x", "content": "y", "authorId": "9999"}},
    )
    assert result["errors"]
    assert "не найден" in result["errors"][0]["message"]
    # Исключение в резолвере превращается в errors[0], а data остаётся null
    # (см. докстринг create_post в app/graphql/schema.py).
    assert result["data"] is None

    # Ничего не создалось — в базе по-прежнему только сид.
    listing = await graphql("{ posts(limit: 100) { id } }")
    assert len(listing["data"]["posts"]) == 20


async def test_create_post_without_required_argument_is_error(graphql):
    result = await graphql("mutation { createPost { id } }")
    assert result["errors"]
    assert result["data"] is None
