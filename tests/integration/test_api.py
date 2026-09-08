from httpx import ASGITransport, AsyncClient

from risk_platform.main import app


async def test_liveness() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
