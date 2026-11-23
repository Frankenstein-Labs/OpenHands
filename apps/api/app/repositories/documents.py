from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.supabase import SupabaseClient

_DOCUMENT_SELECT = (
    "id,organization_id,created_by,title,source,mime_type,size_bytes,status,"
    "metadata,created_at,updated_at"
)


class DocumentsRepository:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def create_document(
        self, access_token: str, organization_id: UUID, user_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.client.request(
            "POST",
            "documents",
            access_token=access_token,
            json={**data, "organization_id": str(organization_id), "created_by": user_id},
            prefer="return=representation",
        )
        return result[0] if isinstance(result, list) else result

    async def insert_chunks(
        self,
        access_token: str,
        organization_id: UUID,
        document_id: UUID,
        chunks: list[dict[str, Any]],
    ) -> None:
        rows = [
            {
                "document_id": str(document_id),
                "organization_id": str(organization_id),
                **chunk,
            }
            for chunk in chunks
        ]
        if rows:
            await self.client.request(
                "POST", "document_chunks", access_token=access_token, json=rows
            )

    async def list_documents(
        self, access_token: str, organization_id: UUID
    ) -> list[dict[str, Any]]:
        result = await self.client.request(
            "GET",
            "documents",
            access_token=access_token,
            params={
                "select": _DOCUMENT_SELECT,
                "organization_id": f"eq.{organization_id}",
                "order": "created_at.desc",
            },
        )
        return result or []

    async def get_document(
        self, access_token: str, organization_id: UUID, document_id: UUID
    ) -> dict[str, Any] | None:
        result = await self.client.request(
            "GET",
            "documents",
            access_token=access_token,
            params={
                "select": _DOCUMENT_SELECT,
                "id": f"eq.{document_id}",
                "organization_id": f"eq.{organization_id}",
                "limit": "1",
            },
        )
        return result[0] if result else None

    async def list_chunks(
        self, access_token: str, organization_id: UUID, document_id: UUID
    ) -> list[dict[str, Any]]:
        result = await self.client.request(
            "GET",
            "document_chunks",
            access_token=access_token,
            params={
                "select": "chunk_index,content,token_count",
                "document_id": f"eq.{document_id}",
                "organization_id": f"eq.{organization_id}",
                "order": "chunk_index.asc",
            },
        )
        return result or []

    async def delete_document(
        self, access_token: str, organization_id: UUID, document_id: UUID
    ) -> None:
        await self.client.request(
            "DELETE",
            "documents",
            access_token=access_token,
            params={"id": f"eq.{document_id}", "organization_id": f"eq.{organization_id}"},
        )

    async def search(
        self, access_token: str, organization_id: UUID, query: str, limit: int
    ) -> list[dict[str, Any]]:
        result = await self.client.rpc(
            "search_document_chunks",
            {
                "target_organization_id": str(organization_id),
                "query_text": query,
                "match_limit": limit,
            },
            access_token=access_token,
        )
        return result or []
