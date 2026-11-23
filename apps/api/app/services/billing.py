from __future__ import annotations

from typing import Any
from uuid import UUID

from app.billing.base import BillingNotConfigured, BillingProvider
from app.repositories.billing import BillingRepository
from app.schemas.billing import CheckoutRequest


class BillingService:
    def __init__(
        self,
        repository: BillingRepository,
        provider: BillingProvider,
        *,
        success_url: str | None,
        cancel_url: str | None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.success_url = success_url
        self.cancel_url = cancel_url

    async def plans(self, access_token: str) -> list[dict[str, Any]]:
        return await self.repository.list_plans(access_token)

    async def subscription(self, access_token: str, organization_id: UUID) -> dict[str, Any]:
        subscription = await self.repository.get_subscription(access_token, organization_id)
        if subscription is None:
            return {'organization_id': organization_id, 'plan_id': None, 'status': None, 'provider': None}
        return subscription

    async def invoices(self, access_token: str, organization_id: UUID) -> list[dict[str, Any]]:
        return await self.repository.list_invoices(access_token, organization_id)

    async def checkout(self, access_token: str, organization_id: UUID, payload: CheckoutRequest) -> dict[str, Any]:
        if not self.success_url or not self.cancel_url:
            raise BillingNotConfigured('billing return URLs are not configured')
        session = await self.provider.create_checkout_session(
            organization_id=organization_id,
            plan_id=payload.plan_id,
            customer_email=None,
            success_url=self.success_url,
            cancel_url=self.cancel_url,
        )
        return {'url': session.url, 'provider': self.provider.name}
