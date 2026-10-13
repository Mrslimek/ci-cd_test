# GraphQL Learning Sandbox

Учебный проект, чтобы на практике разобраться с GraphQL: FastAPI + Strawberry GraphQL
(code-first, схема из type hints) + SQLAlchemy 2.0 (async) + asyncpg + PostgreSQL,
и главное — наглядное решение проблемы **N+1** через Strawberry DataLoader.

## Стек

| Компонент            | Роль                                          |
|----------------------|-----------------------------------------------|
| Python 3.12          | язык (требование проекта — 3.11+)             |
| FastAPI              | веб-фреймворк, ASGI                           |
| Strawberry GraphQL   | GraphQL-схема из type hints + GraphiQL        |
| SQLAlchemy 2.0 async | ORM (Mapped/mapped_column)                    |
| asyncpg              | асинхронный драйвер PostgreSQL                |
| uv                   | пакетный менеджер и виртуальное окружение     |
| Docker Compose       | PostgreSQL 16 + контейнер приложения          |

## Структура проекта

```
graphql/
├── app/
│   ├── main.py               # FastAPI, единый эндпоинт /graphql, logging, lifespan
│   ├── config.py             # настройки (DATABASE_URL, LOG_SQL) через pydantic-settings
│   ├── seed.py               # ожидание БД, create_all, сид: 5 юзеров / 20 постов / 50 комментов
│   ├── db/
│   │   ├── base.py           # DeclarativeBase
│   │   ├── models.py         # User / Post / Comment + связи Many-to-One
│   │   ├── session.py        # async engine (echo=True!) + async_sessionmaker
│   │   └── query_counter.py  # счётчик SQL на HTTP-запрос (ASGI-middleware + contextvars)
│   └── graphql/
│       ├── context.py        # GraphQLContext: сессия + лоадеры, живут один запрос
│       ├── loaders.py        # UserByIdLoader, CommentsByPostIdLoader (DataLoader)
│       ├── types.py          # User, Post, Comment (+ «наивные» PostNaive, CommentNaive)
│       └── schema.py         # Query (posts, postsNaive, user) + Mutation (createPost)
├── docker-compose.yml        # db (postgres:16, порт хоста 5433) + api (порт 8000)
├── Dockerfile                # образ на базе ghcr.io/astral-sh/uv
├── pyproject.toml / uv.lock  # зависимости (uv)
└── .env / .env.example       # настройки для локального запуска без Docker
```

## Запуск

```bash
docker compose up --build
```

- GraphiQL IDE: **http://localhost:8000/graphql** (GET в браузере)
- Postgres доступен с хоста: `localhost:5433` (5433, чтобы не конфликтовать с локальным Postgres), пользователь/пароль/база: `graphql`/`graphql`/`graphql`
- При старте api-контейнер сам ждёт Postgres, создаёт таблицы и сеет данные (сид идемпотентный: если данные есть — пропускается)

Останов: `docker compose down` (данные в volume). Сброс базы и повторный сид:
`docker compose down -v && docker compose up`.

Локальная разработка без Docker (БД остаётся в compose, код — на хосте с reload):

```bash
docker compose up -d db
uv sync
uv run uvicorn app.main:app --reload
```

## Демо N+1 vs DataLoader

В схеме два набора типов на одни и те же таблицы:

- `posts(...)` — вложенные `author`/`comments` решаются через **DataLoader**;
- `postsNaive(...)` — те же поля решаются «в лоб», отдельным SELECT'ом на каждый объект.

Выполните в GraphiQL два одинаковых по форме запроса и смотрите в консоль
(`docker compose logs -f api`). Реально измеренные цифры этого репозитория:

| Запрос                                                       | SQL-запросов |
|--------------------------------------------------------------|--------------|
| `postsNaive(limit: 20) { author comments { author } }`       | **91**       |
| `posts(limit: 20) { author comments { author } }`            | **3**        |

91 = 1 (посты) + 20 (автор каждого поста) + 20 (комментарии каждого поста) + 50 (автор каждого комментария).
3 = 1 (посты) + 1 (`SELECT users WHERE id IN (...)` — все авторы разом) + 1 (`SELECT comments WHERE post_id IN (...)`).
Авторы комментариев не потребовали четвёртого запроса: в сиде всего 5 пользователей, и они уже лежат в **кэше** лоадера за этот запрос.

Каждый SQL-запрос дублируется в лог строками `sqlalchemy.engine.Engine` (echo=True), а по завершении каждого HTTP-запроса middleware печатает итог:

```
▶ POST /graphql — SQL-запросов выполнено: 91
```

## Примеры запросов

### 1. Список постов с фильтрацией и вложенными авторами/комментариями (оптимизировано)

```graphql
query {
  posts(search: "dataloader", limit: 5) {
    id
    title
    author { id name email }
    comments { id text author { name } }
  }
}
```

Аргументы: `search` (ILIKE по title/content), `authorId`, `limit` (1..100), `offset`.

### 2. То же самое, но «в лоб» — увидеть N+1 (91 SQL-запрос)

```graphql
query {
  postsNaive(limit: 20) {
    id
    title
    author { name }
    comments { id text author { name } }
  }
}
```

### 3. Пользователь по ID с постами

```graphql
query {
  user(id: 1) {
    id
    name
    email
    posts { id title }
  }
}
```

### 4. Мутация создания поста (input-тип + переменные)

```graphql
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    id
    title
    authorId
    author { name }
  }
}
```

Переменные (вкладка Query Variables в GraphiQL):

```json
{ "input": { "title": "Мой пост", "content": "Привет из GraphiQL", "authorId": "1" } }
```

### curl-варианты

```bash
# оптимизированный запрос
curl -s -X POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"query { posts(limit: 20) { id title author { name } comments { id text author { name } } } }"}'

# N+1 версия — сравните счётчик в docker compose logs api
curl -s -X POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"query { postsNaive(limit: 20) { id title author { name } comments { id text author { name } } } }"}'

# мутация
curl -s -X POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"mutation($input: CreatePostInput!) { createPost(input: $input) { id title author { name } } }","variables":{"input":{"title":"Из curl","content":"text","authorId":"2"}}}'
```

## Как здесь устроен DataLoader

1. `GraphQLContext` (app/graphql/context.py) создаётся на каждый HTTP-запрос и держит
   `AsyncSession` + два экземпляра лоадеров — их кэш живёт ровно один запрос.
2. Резолвер поля не ходит в БД, а вызывает `info.context.user_by_id.load(self.author_id)` —
   возвращает Future.
3. DataLoader за один тик event loop собирает все накопившиеся ключи и дергает
   батч-функцию `_load_users_by_ids` → единственный `SELECT ... WHERE id IN (...)`.
4. Порядок результатов обязан совпадать с порядком ключей — это контракт `load_fn`;
   для отсутствующих ключей возвращается `None`.

В текущих версиях Strawberry батч-функция передаётся в конструктор
(`DataLoader(load_fn=...)`); кастомный контекст обязан наследовать `BaseContext`.

## Полезные мелочи

- Схема в SDL: `uv run python -c "from app.graphql.schema import schema; print(schema.as_str())"`
- Ручной ре-сид: `uv run python -m app.seed` (или `docker compose down -v` для полной пересборки базы)
- Интроспекция: в GraphiQL справа — Docs; или `query { __schema { types { name } } }`
- Сид детерминированный (`random.Random(42)`) — данные одинаковы при каждом пересоздании

## Идеи для дальнейшего изучения

- Alembic вместо `create_all` (миграции)
- Cursor-based пагинация (Relay-style connections)
- Subscriptions (WebSocket) в Strawberry
- Кастомные ошибки/расширения в ответе мутаций
- Тесты схемы через `strawberry.test` + httpx
