import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_does_not_require_external_services() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/health')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


@pytest.mark.asyncio
async def test_ready_reports_unconfigured_dependencies() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/ready')

    assert response.status_code == 503
    assert response.json()['detail']['status'] == 'not_ready'
    assert response.json()['detail']['dependencies']['supabase']['configured'] is False
    assert response.json()['detail']['dependencies']['redis']['configured'] is False
