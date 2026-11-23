import json

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import OrganizationContext, get_org_context, require_role
from app.api.errors import translate_supabase_error
from app.core.config import Settings, get_settings
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.github.app_auth import GitHubAppClient, GitHubError, GitHubNotConfigured
from app.github.webhooks import WebhookSignatureError
from app.repositories.github import GitHubRepository
from app.schemas.github import (
    InstallationLinkRequest,
    InstallationResponse,
    RepositoryResponse,
    WebhookAck,
)
from app.services.github import GitHubService

router = APIRouter(tags=['github'])

_ADMIN_ROLES = {'owner', 'admin'}


def get_github_service(
    client: SupabaseClient = Depends(get_supabase_client),
    settings: Settings = Depends(get_settings),
) -> GitHubService:
    if not settings.github_app_id or not settings.github_app_private_key:
        raise HTTPException(status_code=503, detail='GitHub App is not configured')
    app_client = GitHubAppClient(
        settings.github_app_id,
        settings.github_app_private_key,
        base_url=settings.github_api_base_url,
    )
    return GitHubService(GitHubRepository(client), app_client, settings.github_webhook_secret)


def _raise(exc: Exception) -> None:
    if isinstance(exc, WebhookSignatureError):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, GitHubNotConfigured):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, GitHubError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='GitHub resource not found') from exc
    raise exc


@router.post(
    '/integrations/github/installations',
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_installation(
    payload: InstallationLinkRequest,
    context: OrganizationContext = Depends(get_org_context),
    service: GitHubService = Depends(get_github_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        return await service.link_installation(
            context.access_token, context.organization_id, payload.installation_id
        )
    except (GitHubError, GitHubNotConfigured, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/integrations/github/installations', response_model=list[InstallationResponse])
async def list_installations(
    context: OrganizationContext = Depends(get_org_context),
    service: GitHubService = Depends(get_github_service),
):
    try:
        return await service.list_installations(context.access_token, context.organization_id)
    except (GitHubError, GitHubNotConfigured, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/integrations/github/repositories', response_model=list[RepositoryResponse])
async def list_repositories(
    context: OrganizationContext = Depends(get_org_context),
    service: GitHubService = Depends(get_github_service),
):
    try:
        return await service.list_repositories(context.access_token, context.organization_id)
    except (GitHubError, GitHubNotConfigured, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.post('/webhooks/github', response_model=WebhookAck)
async def github_webhook(
    request: Request,
    service: GitHubService = Depends(get_github_service),
):
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='invalid JSON payload') from exc
    delivery_id = request.headers.get('x-github-delivery')
    if not delivery_id:
        raise HTTPException(status_code=400, detail='missing delivery id')
    try:
        return await service.handle_webhook(
            request.headers.get('x-github-event', 'unknown'),
            delivery_id,
            raw_body,
            payload,
            request.headers.get('x-hub-signature-256'),
        )
    except (WebhookSignatureError, GitHubError, GitHubNotConfigured, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
