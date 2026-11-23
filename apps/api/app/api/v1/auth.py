from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.security.jwt import CurrentUser, get_current_user

router = APIRouter(prefix='/auth', tags=['auth'])


class CurrentUserResponse(BaseModel):
    id: str
    role: str | None = None
    email: str | None = None


@router.get('/me', response_model=CurrentUserResponse)
async def current_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(id=user.id, role=user.role, email=user.email)
