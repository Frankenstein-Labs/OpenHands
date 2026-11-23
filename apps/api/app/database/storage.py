from __future__ import annotations

from typing import Any, Protocol

from app.database.supabase import SupabaseClient


class StorageSigner(Protocol):
    async def sign_upload(self, access_token: str, bucket: str, object_path: str) -> str: ...
    async def sign_download(self, access_token: str, bucket: str, object_path: str, expires_in: int) -> str: ...
    async def delete_object(self, access_token: str, bucket: str, object_path: str) -> None: ...


def _extract_url(data: Any) -> str:
    if isinstance(data, dict):
        for key in ('signedURL', 'signedUrl', 'signed_url', 'url'):
            if data.get(key):
                return data[key]
    raise ValueError('storage response did not contain a signed URL')


class SupabaseStorage:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def sign_upload(self, access_token: str, bucket: str, object_path: str) -> str:
        return _extract_url(await self.client.storage_sign_upload(access_token, bucket, object_path))

    async def sign_download(self, access_token: str, bucket: str, object_path: str, expires_in: int) -> str:
        return _extract_url(
            await self.client.storage_sign_download(access_token, bucket, object_path, expires_in)
        )

    async def delete_object(self, access_token: str, bucket: str, object_path: str) -> None:
        await self.client.storage_delete(access_token, bucket, object_path)
