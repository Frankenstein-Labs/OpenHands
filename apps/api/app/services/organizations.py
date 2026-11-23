from __future__ import annotations

from uuid import UUID

from app.database.supabase import SupabaseClient
from app.repositories.organizations import OrganizationsRepository
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate


class OrganizationNotFound(Exception):
    pass


class OrganizationsService:
    def __init__(self, client: SupabaseClient) -> None:
        self.repository = OrganizationsRepository(client)

    async def list_organizations(self, access_token: str):
        return await self.repository.list_for_user(access_token)

    async def create_organization(self, access_token: str, payload: OrganizationCreate):
        return await self.repository.create_with_owner(access_token, payload.slug, payload.name)

    async def get_organization(self, access_token: str, organization_id: UUID):
        organization = await self.repository.get_for_user(access_token, organization_id)
        if organization is None:
            raise OrganizationNotFound
        return organization

    async def update_organization(self, access_token: str, organization_id: UUID, payload: OrganizationUpdate):
        organization = await self.repository.update_for_user(access_token, organization_id, payload.name)
        if organization is None:
            raise OrganizationNotFound
        return organization
