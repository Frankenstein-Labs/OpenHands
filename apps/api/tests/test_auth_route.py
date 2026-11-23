import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_auth_me_requires_bearer_token() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/v1/auth/me')

    assert response.status_code == 401
    assert response.json()['detail'] == 'Authentication required'
