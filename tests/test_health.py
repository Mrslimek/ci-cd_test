"""REST-эндпоинты: /, /health и страница GraphiQL."""


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_root_describes_api(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "app": "graphql-learning-sandbox",
        "graphiql": "/graphql",
        "health": "/health",
    }


async def test_graphiql_served_on_get(client):
    response = await client.get("/graphql", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "graphiql" in response.text.lower()
