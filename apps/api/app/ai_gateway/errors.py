"""Provider-neutral errors for the Cortex AI Gateway."""


class GatewayError(Exception):
    """Base class for every gateway error."""


class ProviderNotConfigured(GatewayError):
    """The provider has no endpoint/credentials yet and must not be called."""


class CapabilityNotSupported(GatewayError):
    """The provider/model does not support the requested capability."""


class NoAvailableModel(GatewayError):
    """No model satisfies the routing constraints."""


class ProviderError(GatewayError):
    """A provider call failed.

    ``retryable`` states whether trying another provider (or retrying) is safe.
    Callers must not retry non-idempotent operations blindly.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.detail = detail


class ProviderTimeout(ProviderError):
    def __init__(self, message: str = 'provider request timed out', *, detail: str | None = None) -> None:
        super().__init__(message, retryable=True, detail=detail)
