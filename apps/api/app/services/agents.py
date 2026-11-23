from __future__ import annotations

from typing import Any
from uuid import UUID

from app.repositories.agents import AgentsRepository
from app.schemas.agents import AgentCreate, AgentUpdate


class AgentNotFound(Exception):
    pass


class AgentsService:
    def __init__(self, repository: AgentsRepository) -> None:
        self.repository = repository

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list(access_token, organization_id)

    async def create(self, access_token: str, organization_id: UUID, user_id: str, payload: AgentCreate) -> dict[str, Any]:
        return await self.repository.create(access_token, organization_id, user_id, payload.model_dump())

    async def get(self, access_token: str, organization_id: UUID, agent_id: UUID) -> dict[str, Any]:
        agent = await self.repository.get(access_token, organization_id, agent_id)
        if agent is None:
            raise AgentNotFound
        return agent

    async def update(self, access_token: str, organization_id: UUID, agent_id: UUID, payload: AgentUpdate) -> dict[str, Any]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return await self.get(access_token, organization_id, agent_id)
        agent = await self.repository.update(access_token, organization_id, agent_id, data)
        if agent is None:
            raise AgentNotFound
        return agent

    async def delete(self, access_token: str, organization_id: UUID, agent_id: UUID) -> None:
        await self.get(access_token, organization_id, agent_id)
        await self.repository.delete(access_token, organization_id, agent_id)