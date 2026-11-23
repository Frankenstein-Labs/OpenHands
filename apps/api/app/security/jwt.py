from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    role: str | None
    email: str | None
    claims: dict[str, Any]


class JWTVerificationError(Exception):
    pass


class SupabaseJWTVerifier:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=5.0)
        self._keys: dict[str, Any] = {}
        self._keys_fetched_at = 0.0
        self._cache_ttl_seconds = 300.0

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_signing_key(self, kid: str | None) -> Any:
        if not self.settings.jwks_url:
            raise JWTVerificationError('Supabase JWKS URL is not configured')
        now = time.monotonic()
        if not self._keys or now - self._keys_fetched_at > self._cache_ttl_seconds:
            try:
                response = await self.client.get(self.settings.jwks_url)
                response.raise_for_status()
                payload = response.json()
                keys = payload.get('keys', [])
                self._keys = {key['kid']: PyJWK(key).key for key in keys if key.get('kid')}
                self._keys_fetched_at = now
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise JWTVerificationError('Unable to retrieve Supabase signing keys') from exc
        if not kid or kid not in self._keys:
            raise JWTVerificationError('Unknown JWT key id')
        return self._keys[kid]

    async def verify(self, token: str) -> CurrentUser:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get('alg')
            allowed_algorithms = ['RS256', 'ES256']
            key: Any
            if algorithm == 'HS256' and self.settings.supabase_jwt_secret:
                allowed_algorithms = ['HS256']
                key = self.settings.supabase_jwt_secret
            else:
                if algorithm not in allowed_algorithms:
                    raise JWTVerificationError('JWT algorithm is not allowed')
                key = await self._get_signing_key(header.get('kid'))

            if not self.settings.jwt_issuer:
                raise JWTVerificationError('Supabase JWT issuer is not configured')
            claims = jwt.decode(
                token,
                key,
                algorithms=allowed_algorithms,
                audience=self.settings.supabase_jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={'require': ['exp', 'sub', 'iss', 'aud']},
            )
            user_id = claims.get('sub')
            if not isinstance(user_id, str) or not user_id:
                raise JWTVerificationError('JWT subject is invalid')
            return CurrentUser(
                id=user_id,
                role=claims.get('role') if isinstance(claims.get('role'), str) else None,
                email=claims.get('email') if isinstance(claims.get('email'), str) else None,
                claims=claims,
            )
        except (InvalidTokenError, JWTVerificationError, TypeError, ValueError) as exc:
            if isinstance(exc, JWTVerificationError):
                raise
            raise JWTVerificationError('Invalid Supabase JWT') from exc


bearer_scheme = HTTPBearer(auto_error=False)


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    return credentials.credentials


async def get_jwt_verifier(settings: Settings = Depends(get_settings)) -> AsyncIterator[SupabaseJWTVerifier]:
    verifier = SupabaseJWTVerifier(settings)
    try:
        yield verifier
    finally:
        await verifier.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    verifier: SupabaseJWTVerifier = Depends(get_jwt_verifier),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication required')
    try:
        return await verifier.verify(credentials.credentials)
    except JWTVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid authentication token') from exc
