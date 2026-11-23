from fastapi import HTTPException, status

from app.database.supabase import SupabaseRequestError


def translate_supabase_error(
    exc: SupabaseRequestError,
    *,
    not_found_detail: str = 'Resource not found',
    conflict_detail: str = 'Resource already exists',
) -> HTTPException:
    if exc.status_code in (401, 403):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Operation is not permitted')
    if exc.status_code == 404:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    if exc.status_code == 409:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail)
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Supabase request failed')
