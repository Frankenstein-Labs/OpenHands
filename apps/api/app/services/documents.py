from __future__ import annotations

from typing import Any
from uuid import UUID

from app.repositories.documents import DocumentsRepository

MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150
MIN_CHUNK_CUT_RATIO = 0.6


class EmptyDocument(Exception):
    pass


class DocumentNotFound(Exception):
    pass


def chunk_text(
    text: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split text into overlapping chunks, preferring sentence/word boundaries."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            window = cleaned[start:end]
            boundary = max(
                window.rfind(". "), window.rfind("? "), window.rfind("! "), window.rfind("; ")
            )
            if boundary >= int(max_chars * MIN_CHUNK_CUT_RATIO):
                end = start + boundary + 1
            else:
                space = window.rfind(" ")
                if space >= int(max_chars * MIN_CHUNK_CUT_RATIO):
                    end = start + space
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class DocumentsService:
    def __init__(self, repository: DocumentsRepository) -> None:
        self.repository = repository

    async def create(
        self,
        access_token: str,
        organization_id: UUID,
        user_id: str,
        payload: Any,
    ) -> dict[str, Any]:
        chunks = chunk_text(payload.content)
        if not chunks:
            raise EmptyDocument
        document = await self.repository.create_document(
            access_token,
            organization_id,
            user_id,
            {
                "title": payload.title,
                "source": payload.source,
                "mime_type": payload.mime_type,
                "size_bytes": len(payload.content.encode("utf-8")),
                "status": "ready",
                "metadata": payload.metadata,
            },
        )
        await self.repository.insert_chunks(
            access_token,
            organization_id,
            document["id"],
            [
                {
                    "chunk_index": index,
                    "content": chunk,
                    "token_count": estimate_tokens(chunk),
                }
                for index, chunk in enumerate(chunks)
            ],
        )
        return {"document": document, "chunk_count": len(chunks)}

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list_documents(access_token, organization_id)

    async def detail(
        self, access_token: str, organization_id: UUID, document_id: UUID
    ) -> dict[str, Any]:
        document = await self.repository.get_document(access_token, organization_id, document_id)
        if document is None:
            raise DocumentNotFound
        chunks = await self.repository.list_chunks(access_token, organization_id, document_id)
        return {"document": document, "chunks": chunks}

    async def delete(self, access_token: str, organization_id: UUID, document_id: UUID) -> None:
        document = await self.repository.get_document(access_token, organization_id, document_id)
        if document is None:
            raise DocumentNotFound
        await self.repository.delete_document(access_token, organization_id, document_id)

    async def search(
        self, access_token: str, organization_id: UUID, query: str, limit: int
    ) -> dict[str, Any]:
        hits = await self.repository.search(access_token, organization_id, query, limit)
        return {"query": query, "hits": hits}
