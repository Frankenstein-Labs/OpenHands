from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=400000)
    source: Literal["manual", "upload", "github", "conversation"] = "manual"
    mime_type: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = {}


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by: UUID
    title: str
    source: str
    mime_type: str | None = None
    size_bytes: int | None = None
    status: str
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_index: int
    content: str
    token_count: int | None = None


class DocumentCreateResponse(BaseModel):
    document: DocumentResponse
    chunk_count: int


class DocumentDetailResponse(BaseModel):
    document: DocumentResponse
    chunks: list[ChunkResponse]


class SearchHit(BaseModel):
    document_id: UUID
    document_title: str
    chunk_index: int
    content: str
    rank: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
