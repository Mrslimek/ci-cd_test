"""Главный тезис проекта: DataLoader против N+1 — на реальном подсчёте SQL.

Считаем запросы через before_cursor_execute во время HTTP-вызова к /graphql:
posts решает вложенные поля батчами (IN (...)), postsNaive — по SELECT'у
на каждый вложенный объект. Сид детерминирован, поэтому на 5 постах:
оптимистично 1 + максимум 3 батча, наивно — минимум 1 + 5 + 5.
"""

from contextlib import contextmanager

from sqlalchemy import event

from app.db.session import engine

NESTED_FIELDS = """
  id
  author { id name }
  comments { id text author { id name } }
"""


@contextmanager
def count_sql_queries():
    counts = {"value": 0}

    def _increment(*args, **kwargs):
        counts["value"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _increment)
    try:
        yield counts
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _increment)


async def test_posts_resolves_nested_fields_with_batches(graphql):
    with count_sql_queries() as counts:
        result = await graphql(f"{{ posts(limit: 5) {{ {NESTED_FIELDS} }} }}")

    assert not result.get("errors")
    # 1 SELECT постов + до 3 батчей: авторы постов, комментарии,
    # авторы комментариев (часть может уже быть в кэше DataLoader'а).
    assert 3 <= counts["value"] <= 4


async def test_posts_naive_is_n_plus_one(graphql):
    with count_sql_queries() as counts:
        result = await graphql(f"{{ postsNaive(limit: 5) {{ {NESTED_FIELDS} }} }}")

    assert not result.get("errors")
    # 1 (посты) + 5 (автор на каждый пост) + 5 (комментарии на каждый пост)
    # + по SELECT'у на автора каждого комментария.
    assert counts["value"] >= 11


async def test_dataloader_executes_fewer_queries_than_naive(graphql):
    with count_sql_queries() as optimized:
        await graphql(f"{{ posts(limit: 5) {{ {NESTED_FIELDS} }} }}")
    with count_sql_queries() as naive:
        await graphql(f"{{ postsNaive(limit: 5) {{ {NESTED_FIELDS} }} }}")

    assert optimized["value"] < naive["value"]
