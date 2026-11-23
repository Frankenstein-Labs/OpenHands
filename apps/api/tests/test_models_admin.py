import pytest
from fastapi import HTTPException

from app.api.deps import require_platform_admin
from app.core.config import Settings
from app.repositories.models import ModelsRepository
from app.security.jwt import CurrentUser
from app.services.models import ModelsService


def _user(user_id: str = "user-1") -> CurrentUser:
    return CurrentUser(id=user_id, role="authenticated", email=None, claims={})


def test_platform_admin_rejects_unknown_user() -> None:
    settings = Settings(platform_admin_user_ids=["admin-1"])

    with pytest.raises(HTTPException) as excinfo:
        require_platform_admin(_user("user-1"), settings)

    assert excinfo.value.status_code == 403


def test_platform_admin_rejects_when_unconfigured() -> None:
    with pytest.raises(HTTPException) as excinfo:
        require_platform_admin(_user("user-1"), Settings(platform_admin_user_ids=[]))

    assert excinfo.value.status_code == 403


def test_platform_admin_accepts_listed_user() -> None:
    require_platform_admin(_user("admin-1"), Settings(platform_admin_user_ids=["admin-1"]))


class FakeClient:
    def __init__(self) -> None:
        self.calls: list = []

    async def request(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **kwargs})
        return [{"id": "p1", "name": "Provider", "kind": "frankenstein", "enabled": True}]


@pytest.mark.asyncio
async def test_catalogue_writes_use_service_role() -> None:
    client = FakeClient()
    repository = ModelsRepository(client)

    result = await repository.create_provider(
        {"id": "p1", "name": "Provider", "kind": "frankenstein"}
    )

    assert result["id"] == "p1"
    assert client.calls[0]["admin"] is True
    assert client.calls[0]["path"] == "ai_providers"


@pytest.mark.asyncio
async def test_update_provider_returns_none_when_missing() -> None:
    class EmptyClient(FakeClient):
        async def request(self, method, path, **kwargs):
            return []

    service = ModelsService(ModelsRepository(EmptyClient()))

    assert await service.update_provider("missing", {"enabled": True}) is None
