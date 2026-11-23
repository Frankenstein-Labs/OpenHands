from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.deps import OrganizationContext, get_org_context
from app.api.v1.agents import get_agents_service
from app.main import app
from app.schemas.agents import AgentCreate, AgentUpdate
from app.services.agents import AgentNotFound, AgentsService

ORG = uuid4()
USER = '11111111-1111-1111-1111-111111111111'


class FakeAgentsRepository:
    def __init__(self) -> None:
        self.rows: dict = {}

    async def list(self, access_token, organization_id):
        return list(self.rows.values())

    async def create(self, access_token, organization_id, user_id, data):
        row = {
            **data,
            'id': uuid4(),
            'organization_id': organization_id,
            'created_by': UUID(user_id),
            'archived': False,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
        }
        self.rows[row['id']] = row
        return row

    async def get(self, access_token, organization_id, agent_id):
        return self.rows.get(agent_id)

    async def update(self, access_token, organization_id, agent_id, data):
        row = self.rows.get(agent_id)
        if row is not None:
            row.update(data)
        return row

    async def delete(self, access_token, organization_id, agent_id):
        self.rows.pop(agent_id, None)


@pytest.mark.asyncio
async def test_create_and_get_agent_roundtrip() -> None:
    service = AgentsService(FakeAgentsRepository())
    created = await service.create('t', ORG, USER, AgentCreate(name='Bot'))
    fetched = await service.get('t', ORG, created['id'])
    assert fetched['name'] == 'Bot'


@pytest.mark.asyncio
async def test_update_unknown_agent_raises() -> None:
    service = AgentsService(FakeAgentsRepository())
    with pytest.raises(AgentNotFound):
        await service.update('t', ORG, uuid4(), AgentUpdate(name='x'))


@pytest.mark.asyncio
async def test_viewer_cannot_create_agent() -> None:
    app.dependency_overrides[get_org_context] = lambda: OrganizationContext(ORG, USER, 'viewer', 't')
    app.dependency_overrides[get_agents_service] = lambda: AgentsService(FakeAgentsRepository())
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/api/v1/agents', json={'name': 'Bot'})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
