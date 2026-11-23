from uuid import uuid4

import pytest

from app.schemas.documents import DocumentCreate
from app.services.documents import DocumentNotFound, DocumentsService, chunk_text

ORG = uuid4()


class FakeDocumentsRepository:
    def __init__(self) -> None:
        self.document = None
        self.chunks: list = []

    async def create_document(self, access_token, organization_id, user_id, data):
        self.document = {
            "id": str(uuid4()),
            "organization_id": str(organization_id),
            "created_by": user_id,
            **data,
        }
        return self.document

    async def insert_chunks(self, access_token, organization_id, document_id, chunks):
        self.chunks = chunks

    async def list_documents(self, access_token, organization_id):
        return [self.document] if self.document else []

    async def get_document(self, access_token, organization_id, document_id):
        if self.document and str(self.document["id"]) == str(document_id):
            return self.document
        return None

    async def list_chunks(self, access_token, organization_id, document_id):
        return self.chunks

    async def delete_document(self, access_token, organization_id, document_id):
        self.document = None

    async def search(self, access_token, organization_id, query, limit):
        return [
            {
                "document_id": str(uuid4()),
                "document_title": "Notes",
                "chunk_index": 0,
                "content": "deployment checklist",
                "rank": 0.5,
            }
        ]


def test_chunk_text_keeps_short_text_whole() -> None:
    assert chunk_text("short note") == ["short note"]


def test_chunk_text_splits_long_text_with_bounded_chunks() -> None:
    text = " ".join(f"sentence number {index} about deployments." for index in range(200))

    chunks = chunk_text(text, max_chars=300, overlap_chars=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert all(chunk.endswith(".") for chunk in chunks)
    assert "sentence number 199" in chunks[-1]


def test_chunk_text_returns_empty_for_blank_input() -> None:
    assert chunk_text("   \n  ") == []


@pytest.mark.asyncio
async def test_create_document_stores_chunks_and_size() -> None:
    repository = FakeDocumentsRepository()
    service = DocumentsService(repository)
    payload = DocumentCreate(
        title="Runbook", content="deploy the api. restart workers. verify health."
    )

    result = await service.create("token", ORG, "user-1", payload)

    assert result["chunk_count"] == 1
    assert repository.document["title"] == "Runbook"
    assert repository.document["size_bytes"] == len(payload.content.encode("utf-8"))
    assert repository.chunks[0]["chunk_index"] == 0
    assert repository.chunks[0]["token_count"] >= 1


@pytest.mark.asyncio
async def test_detail_missing_document_raises() -> None:
    service = DocumentsService(FakeDocumentsRepository())

    with pytest.raises(DocumentNotFound):
        await service.detail("token", ORG, uuid4())


@pytest.mark.asyncio
async def test_search_returns_query_and_hits() -> None:
    service = DocumentsService(FakeDocumentsRepository())

    result = await service.search("token", ORG, "deployment", 5)

    assert result["query"] == "deployment"
    assert result["hits"][0]["document_title"] == "Notes"
