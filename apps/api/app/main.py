import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.agents import router as agents_router
from app.api.v1.ai_gateway import router as ai_gateway_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.documents import router as documents_router
from app.api.v1.files import router as files_router
from app.api.v1.github import router as github_router
from app.api.v1.health import router as health_router
from app.api.v1.invitations import router as invitations_router
from app.api.v1.memberships import router as memberships_router
from app.api.v1.models import router as models_router
from app.api.v1.org_ai import router as org_ai_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.runs import router as runs_router
from app.api.v1.usage import router as usage_router
from app.core.config import get_settings

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info('starting %s', get_settings().app_name)
    yield
    logger.info('stopping %s', get_settings().app_name)


app = FastAPI(
    title='OpenHands SaaS API',
    version='0.1.0',
    description='Independent multi-tenant API foundation for OpenHands SaaS.',
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'X-Request-ID'],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception('unhandled request error path=%s', request.url.path)
    return JSONResponse(status_code=500, content={'detail': 'Internal server error'})


app.include_router(health_router, prefix='/api/v1')
app.include_router(auth_router, prefix='/api/v1')
app.include_router(organizations_router, prefix='/api/v1')
app.include_router(memberships_router, prefix='/api/v1')
app.include_router(profiles_router, prefix='/api/v1')
app.include_router(models_router, prefix='/api/v1')
app.include_router(agents_router, prefix='/api/v1')
app.include_router(runs_router, prefix='/api/v1')
app.include_router(usage_router, prefix='/api/v1')
app.include_router(files_router, prefix='/api/v1')
app.include_router(billing_router, prefix='/api/v1')
app.include_router(invitations_router, prefix='/api/v1')
app.include_router(github_router, prefix='/api/v1')
app.include_router(ai_gateway_router, prefix='/api/v1')
app.include_router(documents_router, prefix='/api/v1')
app.include_router(org_ai_router, prefix='/api/v1')
