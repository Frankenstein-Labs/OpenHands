from __future__ import annotations

from typing import Any

from app.repositories.profiles import ProfilesRepository
from app.schemas.profiles import ProfileUpdate


class ProfilesService:
    def __init__(self, repository: ProfilesRepository) -> None:
        self.repository = repository

    async def get_or_create(self, access_token: str, user_id: str) -> dict[str, Any]:
        profile = await self.repository.get(access_token, user_id)
        if profile is None:
            profile = await self.repository.insert(access_token, user_id)
        return profile

    async def update(self, access_token: str, user_id: str, payload: ProfileUpdate) -> dict[str, Any]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return await self.get_or_create(access_token, user_id)
        profile = await self.repository.patch(access_token, user_id, data)
        if profile is None:
            # Row may not exist yet (e.g. user created before the trigger); create then patch.
            await self.repository.insert(access_token, user_id)
            profile = await self.repository.patch(access_token, user_id, data)
        return profile
