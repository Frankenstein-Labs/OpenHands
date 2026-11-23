from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=('.env',),
        env_file_encoding='utf-8',
        extra='ignore',
    )

    app_name: str = 'OpenHands SaaS API'
    app_env: str = 'development'
    log_level: str = 'INFO'
    cors_origins: list[str] = ['http://localhost:5173']
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwks_url: str | None = None
    supabase_jwt_issuer: str | None = None
    supabase_jwt_audience: str = 'authenticated'
    supabase_jwt_secret: str | None = None
    supabase_timeout_seconds: float = 5.0
    redis_url: str | None = None

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(',') if origin.strip()]
        return value

    @property
    def jwt_issuer(self) -> str | None:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer.rstrip('/')
        if self.supabase_url:
            return f'{self.supabase_url.rstrip('/')}/auth/v1'
        return None

    @property
    def jwks_url(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f'{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json'
        return None

    @property
    def supabase_configured(self) -> bool:
        return bool(self.jwt_issuer and self.jwks_url)

    @property
    def supabase_api_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
