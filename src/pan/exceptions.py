"""Pan exception hierarchy.

All domain-specific exceptions inherit from PanError and include
structured context fields for structlog.
"""


class PanError(Exception):
    """Base exception for all Pan errors."""

    def __init__(self, message: str, **context: object) -> None:
        self.context = context
        super().__init__(message)


class ConfigError(PanError):
    """Invalid or missing configuration."""


class DatabaseError(PanError):
    """Database operation failure."""


class AgentError(PanError):
    """Agent execution failure."""


class AgentNotFoundError(AgentError):
    """Requested agent domain does not exist."""

    def __init__(self, domain: str) -> None:
        super().__init__(f"Agent not found: {domain}", domain=domain)


class ApprovalTimeoutError(AgentError):
    """Approval request expired without response."""

    def __init__(self, approval_id: str, timeout_seconds: int) -> None:
        super().__init__(
            f"Approval {approval_id} timed out after {timeout_seconds}s",
            approval_id=approval_id,
            timeout_seconds=timeout_seconds,
        )


class ToolExecutionError(AgentError):
    """A tool call failed during agent execution."""

    def __init__(self, tool_name: str, detail: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' failed: {detail}",
            tool_name=tool_name,
        )


class ExternalAPIError(PanError):
    """An external API returned an error."""

    def __init__(self, service: str, status_code: int, detail: str) -> None:
        super().__init__(
            f"{service} API error ({status_code}): {detail}",
            service=service,
            status_code=status_code,
        )


class PortainerError(ExternalAPIError):
    """Portainer API error."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(service="portainer", status_code=status_code, detail=detail)


class TenantNotFoundError(PanError):
    """Tenant lookup failed."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Tenant not found: {identifier}", identifier=identifier)


class RentCheckError(PanError):
    """Rent checking operation failed."""
