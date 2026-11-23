from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.schemas.files import PresignRequest
from app.services.files import FilesService, FileTooLarge, UnsupportedMime

ORG = uuid4()
USER = '11111111-1111-1111-1111-111111111111'


class FakeFilesRepository:
    def __init__(self) -> None:
        self.rows: dict = {}

    async def create(self, access_token, organization_id, user_id, data):
        row = {
            **data,
            'id': uuid4(),
            'organization_id': organization_id,
            'created_by': UUID(user_id),
            'checksum': None,
            'metadata': {},
            'created_at': datetime.now(timezone.utc),
        }
        self.rows[row['id']] = row
        return row

    async def list(self, access_token, organization_id):
        return [row for row in self.rows.values() if row['status'] != 'deleted']

    async def get(self, access_token, organization_id, file_id):
        return self.rows.get(file_id)

    async def mark_deleted(self, access_token, organization_id, file_id):
        row = self.rows.get(file_id)
        if row is not None:
            row['status'] = 'deleted'
        return row


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def sign_upload(self, access_token, bucket, object_path):
        return f'https://upload/{bucket}/{object_path}'

    async def sign_download(self, access_token, bucket, object_path, expires_in):
        return f'https://download/{bucket}/{object_path}'

    async def delete_object(self, access_token, bucket, object_path):
        self.deleted.append(object_path)


def make_service():
    repository = FakeFilesRepository()
    storage = FakeStorage()
    service = FilesService(repository, storage, max_upload_bytes=1000, download_ttl_seconds=60)
    return service, repository, storage


@pytest.mark.asyncio
async def test_presign_scopes_path_to_org_and_sanitizes_name() -> None:
    service, _, _ = make_service()
    result = await service.presign(
        't', ORG, USER,
        PresignRequest(filename='../../etc/passwd', mime_type='text/plain', size_bytes=10),
    )
    assert result['object_path'].startswith(f'{ORG}/')
    assert '..' not in result['object_path']
    assert result['object_path'].endswith('passwd')


@pytest.mark.asyncio
async def test_presign_rejects_oversized_and_disallowed_mime() -> None:
    service, _, _ = make_service()
    with pytest.raises(FileTooLarge):
        await service.presign(
            't', ORG, USER,
            PresignRequest(filename='a.txt', mime_type='text/plain', size_bytes=2000),
        )
    with pytest.raises(UnsupportedMime):
        await service.presign(
            't', ORG, USER,
            PresignRequest(filename='a.exe', mime_type='application/x-msdownload', size_bytes=10),
        )


@pytest.mark.asyncio
async def test_delete_marks_row_and_removes_object() -> None:
    service, repository, storage = make_service()
    created = await service.presign(
        't', ORG, USER,
        PresignRequest(filename='a.txt', mime_type='text/plain', size_bytes=10),
    )
    await service.delete('t', ORG, created['file_id'])
    assert repository.rows[created['file_id']]['status'] == 'deleted'
    assert storage.deleted == [created['object_path']]
