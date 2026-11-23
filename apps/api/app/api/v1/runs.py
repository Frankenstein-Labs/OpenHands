from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import OrganizationContext, get_org_context
from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.agents import AgentsRepository
from app.repositories.models import ModelsRepository
from app.repositories.runs import RunsRepository
from app.repositories.usage import UsageRepository
from app.schemas.runs import RunCreate, RunEventResponse, RunResponse
from app.services.models import ModelsService
from app.services.runs import (
    InvalidRunState,
    QuotaExceeded,
    RunNotFound,
    RunsService,
    RunValidationError,
)

router = APIRouter(prefix='/runs', tags=['runs'])


def get_runs_service(client: SupabaseClient = Depends(get_supabase_client)) -> RunsService:
    return RunsService(
        RunsRepository(client),
        UsageRepository(client),
        AgentsRepository(client),
        ModelsService(ModelsRepository(client)),
    )


def _raise(exc: Exception) -> None:
    if isinstance(exc, RunNotFound):
        raise HTTPException(status_code=404, detail='Run not found') from exc
    if isinstance(exc, RunValidationError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, QuotaExceeded):
        raise HTTPException(status_code=402, detail=exc.detail) from exc
    if isinstance(exc, InvalidRunState):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='Run not found') from exc
    raise exc


@router.post('', response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    context: OrganizationContext = Depends(get_org_context),
    service: RunsService = Depends(get_runs_service),
):
    try:
        return await service.create(context.access_token, context.organization_id, context.user_id, payload)
    except (RunNotFound, RunValidationError, QuotaExceeded, InvalidRunState,
            SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/{run_id}', response_model=RunResponse)
async def get_run(
    run_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: RunsService = Depends(get_runs_service),
):
    try:
        return await service.get(context.access_token, context.organization_id, run_id)
    except (RunNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.post('/{run_id}/cancel', response_model=RunResponse)
async def cancel_run(
    run_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: RunsService = Depends(get_runs_service),
):
    try:
        return await service.cancel(context.access_token, context.organization_id, run_id)
    except (RunNotFound, InvalidRunState, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/{run_id}/events', response_model=list[RunEventResponse])
async def list_run_events(
    run_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: RunsService = Depends(get_runs_service),
):
    try:
        return await service.events(context.access_token, context.organization_id, run_id)
    except (RunNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
