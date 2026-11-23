from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import OrganizationContext, get_org_context
from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.usage import UsageRepository
from app.schemas.usage import EntitlementResponse, LimitsResponse, UsageSummary
from app.services.usage import EntitlementNotFound, UsageService

router = APIRouter(tags=['usage'])


def get_usage_service(client: SupabaseClient = Depends(get_supabase_client)) -> UsageService:
    return UsageService(UsageRepository(client))


def _raise(exc: Exception) -> None:
    if isinstance(exc, EntitlementNotFound):
        raise HTTPException(status_code=404, detail='Entitlement not found') from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='Entitlement not found') from exc
    raise exc


@router.get('/usage', response_model=UsageSummary)
async def get_usage(
    context: OrganizationContext = Depends(get_org_context),
    service: UsageService = Depends(get_usage_service),
):
    try:
        return await service.summary(context.access_token, context.organization_id)
    except (EntitlementNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/usage/limits', response_model=LimitsResponse)
async def get_limits(
    context: OrganizationContext = Depends(get_org_context),
    service: UsageService = Depends(get_usage_service),
):
    try:
        return await service.limits(context.access_token, context.organization_id)
    except (EntitlementNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/entitlements', response_model=EntitlementResponse)
async def get_entitlements(
    context: OrganizationContext = Depends(get_org_context),
    service: UsageService = Depends(get_usage_service),
):
    try:
        return await service.entitlement(context.access_token, context.organization_id)
    except (EntitlementNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
