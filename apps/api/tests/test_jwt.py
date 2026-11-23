import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import Settings
from app.main import app
from app.security.jwt import SupabaseJWTVerifier, get_current_user


@pytest.fixture
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    def b64(value: int) -> str:
        import base64
        raw = value.to_bytes((value.bit_length() + 7) // 8, 'big')
        return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
    jwk = {'kty': 'RSA', 'kid': 'test-key', 'use': 'sig', 'alg': 'RS256', 'n': b64(public_numbers.n), 'e': b64(public_numbers.e)}
    return private_key, jwk


@pytest.mark.asyncio
async def test_valid_supabase_jwt_is_accepted(rsa_keypair) -> None:
    private_key, jwk = rsa_keypair
    settings = Settings(
        supabase_jwks_url='https://supabase.test/auth/v1/.well-known/jwks.json',
        supabase_jwt_issuer='https://supabase.test/auth/v1',
        supabase_jwt_audience='authenticated',
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'keys': [jwk]})

    verifier = SupabaseJWTVerifier(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    token = jwt.encode(
        {'sub': 'user-123', 'role': 'authenticated', 'aud': 'authenticated', 'iss': settings.jwt_issuer, 'exp': int(time.time()) + 60},
        private_key,
        algorithm='RS256',
        headers={'kid': 'test-key'},
    )
    user = await verifier.verify(token)
    await verifier.close()

    assert user.id == 'user-123'
    assert user.role == 'authenticated'


@pytest.mark.asyncio
async def test_expired_jwt_is_rejected(rsa_keypair) -> None:
    private_key, jwk = rsa_keypair
    settings = Settings(
        supabase_jwks_url='https://supabase.test/auth/v1/.well-known/jwks.json',
        supabase_jwt_issuer='https://supabase.test/auth/v1',
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'keys': [jwk]})

    verifier = SupabaseJWTVerifier(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    token = jwt.encode(
        {'sub': 'user-123', 'aud': 'authenticated', 'iss': settings.jwt_issuer, 'exp': int(time.time()) - 1},
        private_key,
        algorithm='RS256',
        headers={'kid': 'test-key'},
    )

    with pytest.raises(Exception):
        await verifier.verify(token)
    await verifier.close()
