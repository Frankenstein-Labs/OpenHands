from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_platform_admin
from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.models import ModelsRepository
from app.schemas.models import (
    ModelCreate,
    ModelResponse,
    ModelUpdate,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
)
from app.security.jwt import CurrentUser, get_access_token, get_current_user
from app.services.models import ModelsService

router = APIRouter(tags=['ai-catalog'])


def get_models_service(client: SupabaseClient = Depends(get_supabase_client)) -> ModelsService:
    return ModelsService(ModelsRepository(client))


def _raise(exc: Exception) -> None:
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc) from exc
    raise exc


@router.get('/providers', response_model=list[ProviderResponse])
async def list_providers(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.list_providers(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/models', response_model=list[ModelResponse])
async def list_models(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.list_models(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/models/available', response_model=list[ModelResponse])
async def list_available_models(
    _: CurrentUser = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.list_available(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)

@router.post('/providers', response_model=ProviderResponse, status_code=201)
async def create_provider(
    payload: ProviderCreate,
    _: None = Depends(require_platform_admin),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.create_provider(payload.model_dump())
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.patch('/providers/{provider_id}', response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    _: None = Depends(require_platform_admin),
    service: ModelsService = Depends(get_models_service),
):
    try:
        updated = await service.update_provider(
            provider_id, payload.model_dump(exclude_unset=True)
        )
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail='provider not found')
    return updated


@router.post('/models', response_model=ModelResponse, status_code=201)
async def create_model(
    payload: ModelCreate,
    _: None = Depends(require_platform_admin),
    service: ModelsService = Depends(get_models_service),
):
    try:
        return await service.create_model(payload.model_dump())
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.patch('/models/{model_id}', response_model=ModelResponse)
async def update_model(
    model_id: str,
    payload: ModelUpdate,
    _: None = Depends(require_platform_admin),
    service: ModelsService = Depends(get_models_service),
):
    try:
        updated = await service.update_model(model_id, payload.model_dump(exclude_unset=True))
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail='model not found')
    return updated
