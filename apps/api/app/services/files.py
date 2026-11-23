from __future__ import annotations

import uuid
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from app.database.storage import StorageSigner
from app.repositories.files import FilesRepository
from app.schemas.files import PresignRequest

_ALLOWED_MIME_PREFIXES = ('image/', 'text/', 'application/pdf', 'application/json', 'application/zip')
_ALLOWED_EXACT_MIME = {'application/octet-stream'}


class FileTooLarge(Exception):
    pass


class UnsupportedMime(Exception):
    pass


class FileNotFound(Exception):
    pass


def _safe_filename(name: str) -> str:
    base = PurePosixPath(name.replace('\\', '/')).name.strip()
    cleaned = ''.join(ch for ch in base if ch.isalnum() or ch in '._- ').strip()
    return (cleaned or 'file')[:200]


class FilesService:
    def __init__(
        self,
        repository: FilesRepository,
        storage: StorageSigner,
        *,
        max_upload_bytes: int,
        download_ttl_seconds: int,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.max_upload_bytes = max_upload_bytes
        self.download_ttl_seconds = download_ttl_seconds

    def _validate(self, mime_type: str, size_bytes: int) -> None:
        if size_bytes > self.max_upload_bytes:
            raise FileTooLarge(f'file exceeds {self.max_upload_bytes} bytes')
        if mime_type not in _ALLOWED_EXACT_MIME and not mime_type.startswith(_ALLOWED_MIME_PREFIXES):
            raise UnsupportedMime(f'unsupported MIME type: {mime_type}')

    async def presign(self, access_token: str, organization_id: UUID, user_id: str, payload: PresignRequest) -> dict[str, Any]:
        self._validate(payload.mime_type, payload.size_bytes)
        object_path = f'{organization_id}/{uuid.uuid4().hex}/{_safe_filename(payload.filename)}'
        file_row = await self.repository.create(
            access_token, organization_id, user_id,
            {
                'bucket': payload.bucket,
                'object_path': object_path,
                'mime_type': payload.mime_type,
                'size_bytes': payload.size_bytes,
                'status': 'pending',
            },
        )
        upload_url = await self.storage.sign_upload(access_token, payload.bucket, object_path)
        return {
            'file_id': file_row['id'],
            'bucket': payload.bucket,
            'object_path': object_path,
            'upload_url': upload_url,
            'expires_in': self.download_ttl_seconds,
        }

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list(access_token, organization_id)

    async def _active_file(self, access_token: str, organization_id: UUID, file_id: UUID) -> dict[str, Any]:
        file_row = await self.repository.get(access_token, organization_id, file_id)
        if file_row is None or file_row.get('status') == 'deleted':
            raise FileNotFound
        return file_row

    async def download(self, access_token: str, organization_id: UUID, file_id: UUID) -> dict[str, Any]:
        file_row = await self._active_file(access_token, organization_id, file_id)
        url = await self.storage.sign_download(
            access_token, file_row['bucket'], file_row['object_path'], self.download_ttl_seconds
        )
        return {'url': url, 'expires_in': self.download_ttl_seconds}

    async def delete(self, access_token: str, organization_id: UUID, file_id: UUID) -> None:
        file_row = await self._active_file(access_token, organization_id, file_id)
        await self.repository.mark_deleted(access_token, organization_id, file_id)
        await self.storage.delete_object(access_token, file_row['bucket'], file_row['object_path'])
