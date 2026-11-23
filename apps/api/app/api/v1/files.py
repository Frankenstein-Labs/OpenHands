from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import OrganizationContext, get_org_context, require_role
from app.api.errors import translate_supabase_error
from app.core.config import Settings, get_settings
from app.database.storage import SupabaseStorage
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.files import FilesRepository
from app.schemas.files import DownloadResponse, FileResponse, PresignRequest, PresignResponse
from app.services.files import FileNotFound, FilesService, FileTooLarge, UnsupportedMime

router = APIRouter(prefix='/files', tags=['files'])

_WRITE_ROLES = {'owner', 'admin', 'member'}
_ADMIN_ROLES = {'owner', 'admin'}


def get_files_service(
    client: SupabaseClient = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> FilesService:
    return FilesService(
        FilesRepository(client),
        SupabaseStorage(client),
        max_upload_bytes=settings.max_upload_bytes,
        download_ttl_seconds=settings.storage_signed_url_ttl_seconds,
    )


def _raise(exc: Exception) -> None:
    if isinstance(exc, FileNotFound):
        raise HTTPException(status_code=404, detail='File not found') from exc
    if isinstance(exc, FileTooLarge):
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    if isinstance(exc, UnsupportedMime):
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='File not found') from exc
    raise exc


@router.post('/presign', response_model=PresignResponse, status_code=status.HTTP_201_CREATED)
async def presign_upload(
    payload: PresignRequest,
    context: OrganizationContext = Depends(get_org_context),
    service: FilesService = Depends(get_files_service),
):
    require_role(context, _WRITE_ROLES)
    try:
        return await service.presign(context.access_token, context.organization_id, context.user_id, payload)
    except (FileNotFound, FileTooLarge, UnsupportedMime, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('', response_model=list[FileResponse])
async def list_files(
    context: OrganizationContext = Depends(get_org_context),
    service: FilesService = Depends(get_files_service),
):
    try:
        return await service.list(context.access_token, context.organization_id)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/{file_id}', response_model=DownloadResponse)
async def download_file(
    file_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: FilesService = Depends(get_files_service),
):
    try:
        return await service.download(context.access_token, context.organization_id, file_id)
    except (FileNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.delete('/{file_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: FilesService = Depends(get_files_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        await service.delete(context.access_token, context.organization_id, file_id)
    except (FileNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
