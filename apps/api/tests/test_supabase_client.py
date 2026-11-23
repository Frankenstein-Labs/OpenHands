import httpx
import pytest

from app.core.config import Settings
from app.database.supabase import SupabaseClient, SupabaseNotConfigured


@pytest.mark.asyncio
async def test_supabase_client_forwards_user_token_and_anon_key() -> None:
    observed = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed['authorization'] = request.headers.get('authorization')
        observed['apikey'] = request.headers.get('apikey')
        return httpx.Response(200, json=[{'id': 'one'}])

    client = SupabaseClient(
        Settings(supabase_url='https://supabase.test', supabase_anon_key='anon-test'),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.request('GET', 'organizations', access_token='user-token')
    await client.close()

    assert result == [{'id': 'one'}]
    assert observed == {'authorization': 'Bearer user-token', 'apikey': 'anon-test'}


@pytest.mark.asyncio
async def test_admin_mode_requires_server_key() -> None:
    client = SupabaseClient(
        Settings(supabase_url='https://supabase.test', supabase_anon_key='anon-test'),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[]))),
    )
    with pytest.raises(SupabaseNotConfigured):
        await client.request('GET', 'organizations', admin=True)
    await client.close()
