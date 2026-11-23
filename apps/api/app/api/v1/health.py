from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=['health'])


class HealthResponse(BaseModel):
    status: Literal['ok']
    service: str


class DependencyStatus(BaseModel):
    configured: bool
    checked: bool = False
    status: Literal['configured', 'not_configured', 'not_checked']


class ReadyResponse(BaseModel):
    status: Literal['ready', 'not_ready']
    service: str
    dependencies: dict[str, DependencyStatus]


@router.get('/health', response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status='ok', service=settings.app_name)


@router.get('/ready', response_model=ReadyResponse)
async def ready(settings: Settings = Depends(get_settings)) -> ReadyResponse:
    dependencies = {
        'supabase': DependencyStatus(
            configured=settings.supabase_configured,
            status='configured' if settings.supabase_configured else 'not_configured',
        ),
        'redis': DependencyStatus(
            configured=bool(settings.redis_url),
            status='configured' if settings.redis_url else 'not_configured',
        ),
    }
    is_ready = all(dependency.configured for dependency in dependencies.values())
    response = ReadyResponse(
        status='ready' if is_ready else 'not_ready',
        service=settings.app_name,
        dependencies=dependencies,
    )
    if not is_ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response.model_dump())
    return response
