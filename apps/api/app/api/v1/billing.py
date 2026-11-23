from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import OrganizationContext, get_org_context, require_role
from app.api.errors import translate_supabase_error
from app.billing.base import BillingNotConfigured, get_billing_provider
from app.core.config import Settings, get_settings
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.billing import BillingRepository
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    InvoiceResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.security.jwt import get_access_token
from app.services.billing import BillingService

router = APIRouter(prefix='/billing', tags=['billing'])

_ADMIN_ROLES = {'owner', 'admin'}


def get_billing_service(
    client: SupabaseClient = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> BillingService:
    return BillingService(
        BillingRepository(client),
        get_billing_provider(settings),
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
    )


def _raise(exc: Exception) -> None:
    if isinstance(exc, BillingNotConfigured):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='Billing resource not found') from exc
    raise exc


@router.get('/plans', response_model=list[PlanResponse])
async def list_plans(
    access_token: str = Depends(get_access_token),
    service: BillingService = Depends(get_billing_service),
):
    try:
        return await service.plans(access_token)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/subscription', response_model=SubscriptionResponse)
async def get_subscription(
    context: OrganizationContext = Depends(get_org_context),
    service: BillingService = Depends(get_billing_service),
):
    try:
        return await service.subscription(context.access_token, context.organization_id)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.post('/checkout-session', response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def create_checkout_session(
    payload: CheckoutRequest,
    context: OrganizationContext = Depends(get_org_context),
    service: BillingService = Depends(get_billing_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        return await service.checkout(context.access_token, context.organization_id, payload)
    except (BillingNotConfigured, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/invoices', response_model=list[InvoiceResponse])
async def list_invoices(
    context: OrganizationContext = Depends(get_org_context),
    service: BillingService = Depends(get_billing_service),
):
    try:
        return await service.invoices(context.access_token, context.organization_id)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
