from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import OrganizationContext, get_org_context, require_role
from app.api.errors import translate_supabase_error
from app.database.supabase import (
    SupabaseClient,
    SupabaseNotConfigured,
    SupabaseRequestError,
    get_supabase_client,
)
from app.repositories.agents import AgentsRepository
from app.schemas.agents import AgentCreate, AgentResponse, AgentUpdate
from app.services.agents import AgentNotFound, AgentsService

router = APIRouter(prefix='/agents', tags=['agents'])

_WRITE_ROLES = {'owner', 'admin', 'member'}
_ADMIN_ROLES = {'owner', 'admin'}


def get_agents_service(client: SupabaseClient = Depends(get_supabase_client)) -> AgentsService:
    return AgentsService(AgentsRepository(client))


def _raise(exc: Exception) -> None:
    if isinstance(exc, AgentNotFound):
        raise HTTPException(status_code=404, detail='Agent not found') from exc
    if isinstance(exc, SupabaseNotConfigured):
        raise HTTPException(status_code=503, detail='Supabase is not configured') from exc
    if isinstance(exc, SupabaseRequestError):
        raise translate_supabase_error(exc, not_found_detail='Agent not found') from exc
    raise exc


@router.get('', response_model=list[AgentResponse])
async def list_agents(
    context: OrganizationContext = Depends(get_org_context),
    service: AgentsService = Depends(get_agents_service),
):
    try:
        return await service.list(context.access_token, context.organization_id)
    except (AgentNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.post('', response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    context: OrganizationContext = Depends(get_org_context),
    service: AgentsService = Depends(get_agents_service),
):
    require_role(context, _WRITE_ROLES)
    try:
        return await service.create(context.access_token, context.organization_id, context.user_id, payload)
    except (SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.get('/{agent_id}', response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: AgentsService = Depends(get_agents_service),
):
    try:
        return await service.get(context.access_token, context.organization_id, agent_id)
    except (AgentNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.patch('/{agent_id}', response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    context: OrganizationContext = Depends(get_org_context),
    service: AgentsService = Depends(get_agents_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        return await service.update(context.access_token, context.organization_id, agent_id, payload)
    except (AgentNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)


@router.delete('/{agent_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    context: OrganizationContext = Depends(get_org_context),
    service: AgentsService = Depends(get_agents_service),
):
    require_role(context, _ADMIN_ROLES)
    try:
        await service.delete(context.access_token, context.organization_id, agent_id)
    except (AgentNotFound, SupabaseNotConfigured, SupabaseRequestError) as exc:
        _raise(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
