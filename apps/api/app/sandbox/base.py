from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


class SandboxError(RuntimeError):
    """Raised when a sandbox cannot be created or reached."""


class SandboxUnavailable(SandboxError):
    """The container runtime is missing or refused the request."""


class SandboxLimitError(SandboxError):
    """The requested resources exceed what the deployment allows."""


@dataclass(frozen=True)
class SandboxLimits:
    cpus: float = 1.0
    memory_mb: int = 1024
    pids: int = 256
    disk_mb: int = 2048
    timeout_seconds: int = 3600

    def validate(self) -> None:
        if self.cpus <= 0:
            raise SandboxLimitError('cpus must be positive')
        if self.memory_mb < 128:
            raise SandboxLimitError('memory_mb must be at least 128')
        if self.pids < 16:
            raise SandboxLimitError('pids must be at least 16')
        if self.disk_mb < 64:
            raise SandboxLimitError('disk_mb must be at least 64')
        if self.timeout_seconds < 60:
            raise SandboxLimitError('timeout_seconds must be at least 60')


@dataclass(frozen=True)
class SandboxSpec:
    organization_id: UUID
    run_id: UUID
    image: str
    limits: SandboxLimits = field(default_factory=SandboxLimits)
    network: str = 'cortex-sandboxes'
    env: dict[str, str] = field(default_factory=dict)
    command: tuple[str, ...] = ()


@dataclass(frozen=True)
class Sandbox:
    """A provisioned, isolated execution environment."""

    id: str
    run_id: UUID
    organization_id: UUID
    workspace: str
    api_url: str | None = None
    # Per-sandbox Agent Server key: the server only binds a routable address
    # when one is configured, and every request must carry it.
    session_api_key: str | None = None
    image: str = ''


class SandboxProvider(Protocol):
    async def provision(self, spec: SandboxSpec) -> Sandbox: ...
    async def stop(self, sandbox: Sandbox) -> None: ...
    async def inspect(self, sandbox: Sandbox) -> dict: ...
    async def reap(self, older_than_seconds: int) -> list[str]: ...
    async def aclose(self) -> None: ...
