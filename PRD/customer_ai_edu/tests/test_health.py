import pytest
from httpx import ASGITransport, AsyncClient

from edu_ai.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "edu-ai-service"


async def test_index(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_search_without_tenant_returns_empty() -> None:
    from edu_ai.knowledge import milvus_store

    assert milvus_store.search([0.0] * 1024, []) == []
