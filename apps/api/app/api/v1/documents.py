from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import OrganizationContext, get_org_context, require_role
from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.documents import DocumentsRepository
from app.schemas.documents import (
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetailResponse,
    DocumentResponse,
    SearchResponse,
)
from app.services.documents import DocumentNotFound, DocumentsService, EmptyDocument

router = APIRouter(prefix="/documents", tags=["documents"])


def get_documents_service(
    client: SupabaseClient = Depends(get_supabase_client),
) -> DocumentsService:
    return DocumentsService(DocumentsRepository(client))


@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    context: OrganizationContext = Depends(get_org_context),
    service: DocumentsService = Depends(get_documents_service),
):
    try:
        return await service.create(
            context.access_token, context.organization_id, context.user_id, payload
        )
    except EmptyDocument as exc:
        raise HTTPException(status_code=422, detail="document content is empty") from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Supabase is not configured") from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    context: OrganizationContext = Depends(get_org_context),
    service: DocumentsService = Depends(get_documents_service),
):
    try:
        return await service.list(context.access_token, context.organization_id)
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Supabase is not configured") from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=50),
    context: OrganizationContext = Depends(get_org_context),
    service: DocumentsService = Depends(get_documents_service),
):
    try:
        return await service.search(context.access_token, context.organization_id, q, limit)
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Supabase is not configured") from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc) from exc


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: DocumentsService = Depends(get_documents_service),
):
    try:
        return await service.detail(context.access_token, context.organization_id, document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Supabase is not configured") from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc, not_found_detail="document not found") from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: DocumentsService = Depends(get_documents_service),
):
    require_role(context, {"owner", "admin"})
    try:
        await service.delete(context.access_token, context.organization_id, document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc
    except SupabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Supabase is not configured") from exc
    except SupabaseRequestError as exc:
        raise translate_supabase_error(exc, not_found_detail="document not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
