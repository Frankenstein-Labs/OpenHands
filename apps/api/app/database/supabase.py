from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import Depends

from app.core.config import Settings, get_settings


class SupabaseNotConfigured(RuntimeError):
    pass


class SupabaseRequestError(RuntimeError):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f'Supabase request failed with status {status_code}')
        self.status_code = status_code
        self.detail = detail


class SupabaseClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise SupabaseNotConfigured('SUPABASE_URL and SUPABASE_ANON_KEY are required')
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=settings.supabase_timeout_seconds)
        self.base_url = settings.supabase_url.rstrip('/')

    async def close(self) -> None:
        await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        admin: bool = False,
        params: dict[str, str] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> Any:
        key = self.settings.supabase_service_role_key if admin else self.settings.supabase_anon_key
        if admin and not key:
            raise SupabaseNotConfigured('SUPABASE_SERVICE_ROLE_KEY is required for admin access')
        headers = {'apikey': key or ''}
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
        elif admin:
            headers['Authorization'] = f'Bearer {key}'
        if prefer:
            headers['Prefer'] = prefer
        try:
            response = await self.client.request(
                method,
                f'{self.base_url}/rest/v1/{path.lstrip("/")}',
                headers=headers,
                params=params,
                json=json,
            )
        except httpx.HTTPError as exc:
            raise SupabaseRequestError(503, 'Supabase is unavailable') from exc
        if response.is_error:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise SupabaseRequestError(response.status_code, detail)
        if not response.content:
            return None
        return response.json()

    async def rpc(self, function_name: str, payload: dict[str, Any], *, access_token: str) -> Any:
        return await self.request('POST', f'rpc/{function_name}', access_token=access_token, json=payload)

    async def _storage_request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        json: Any = None,
    ) -> Any:
        headers = {
            'apikey': self.settings.supabase_anon_key or '',
            'Authorization': f'Bearer {access_token}',
        }
        try:
            response = await self.client.request(
                method,
                f'{self.base_url}/storage/v1/{path.lstrip("/")}',
                headers=headers,
                json=json,
            )
        except httpx.HTTPError as exc:
            raise SupabaseRequestError(503, 'Supabase storage is unavailable') from exc
        if response.is_error:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise SupabaseRequestError(response.status_code, detail)
        if not response.content:
            return None
        return response.json()

    async def storage_sign_upload(self, access_token: str, bucket: str, object_path: str) -> Any:
        return await self._storage_request(
            'POST', f'object/upload/sign/{bucket}/{object_path}',
            access_token=access_token, json={},
        )

    async def storage_sign_download(self, access_token: str, bucket: str, object_path: str, expires_in: int) -> Any:
        return await self._storage_request(
            'POST', f'object/sign/{bucket}/{object_path}',
            access_token=access_token, json={'expiresIn': expires_in},
        )

    async def storage_delete(self, access_token: str, bucket: str, object_path: str) -> Any:
        return await self._storage_request(
            'DELETE', f'object/{bucket}/{object_path}', access_token=access_token,
        )


async def get_supabase_client(settings: Settings = Depends(get_settings)) -> AsyncIterator[SupabaseClient]:
    client = SupabaseClient(settings)
    try:
        yield client
    finally:
        await client.close()
