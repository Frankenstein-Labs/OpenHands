from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

BucketName = Literal['org-files', 'conversation-exports', 'run-artifacts']


class PresignRequest(BaseModel):
    bucket: BucketName = 'org-files'
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=255)
    size_bytes: int = Field(ge=1)


class PresignResponse(BaseModel):
    file_id: UUID
    bucket: str
    object_path: str
    upload_url: str
    expires_in: int


class DownloadResponse(BaseModel):
    url: str
    expires_in: int


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by: UUID
    bucket: str
    object_path: str
    mime_type: str
    size_bytes: int
    checksum: str | None = None
    status: str
    metadata: dict[str, Any] = {}
    created_at: datetime
