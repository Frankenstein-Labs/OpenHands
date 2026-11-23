from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.repositories.invitations import InvitationsRepository
from app.schemas.invitations import InvitationCreate


class InvitationError(Exception):
    pass


class InvitationsService:
    def __init__(self, repository: InvitationsRepository, *, ttl_hours: int = 168) -> None:
        self.repository = repository
        self.ttl_hours = ttl_hours

    async def create(
        self,
        access_token: str,
        organization_id: UUID,
        invited_by: str,
        payload: InvitationCreate,
    ) -> dict[str, Any]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)).isoformat()
        row = await self.repository.create(
            access_token, organization_id,
            {
                'email': str(payload.email).lower(),
                'role': payload.role,
                'token_hash': token_hash,
                'expires_at': expires_at,
                'invited_by': invited_by,
                'status': 'pending',
            },
        )
        return {**row, 'token': raw_token}

    async def list(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list(access_token, organization_id)

    async def accept(self, access_token: str, invite_token: str) -> dict[str, Any]:
        token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
        membership = await self.repository.accept(access_token, token_hash)
        if not membership:
            raise InvitationError('invalid or expired invitation')
        return {'organization_id': membership['organization_id'], 'role': membership['role']}
