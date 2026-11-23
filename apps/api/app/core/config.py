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

    # Storage
    max_upload_bytes: int = 52428800  # 50 MiB, matches supabase/config.toml
    storage_signed_url_ttl_seconds: int = 600

    # AI Gateway: provider id -> server-only credential / endpoint override.
    ai_provider_credentials: dict[str, str] = {}
    ai_provider_base_urls: dict[str, str] = {}
    ai_gateway_timeout_seconds: float = 60.0
    ai_gateway_credits_per_1k_tokens: float = 1.0

    # GitHub App (server-only; no personal access token is shared across tenants)
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_private_key: str | None = None
    github_webhook_secret: str | None = None
    github_api_base_url: str = 'https://api.github.com'

    # Billing (provider-neutral; Stripe optional)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_ids: dict[str, str] = {}
    billing_success_url: str | None = None
    billing_cancel_url: str | None = None
    # Platform operators allowed to edit the global AI catalogue.
    platform_admin_user_ids: list[str] = []

    @field_validator('platform_admin_user_ids', mode='before')
    @classmethod
    def parse_platform_admin_user_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return value

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
