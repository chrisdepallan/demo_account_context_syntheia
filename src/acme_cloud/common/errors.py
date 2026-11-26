"""Error types shared by all packages.

Every error carries a stable ``code`` (shown to API clients) and the HTTP
status the REST layer returns for it. The list matches the error table in
``docs/reference/constants-and-glossary.md``.
"""

from __future__ import annotations


class AcmeError(Exception):
    """Base class for every expected error raised by the sample modules."""

    code = "ERR_INTERNAL"
    http_status = 500

    def __init__(self, message: str = "", **details: object) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details

    def to_dict(self) -> dict:
        """Body the REST API returns for this error."""
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationError(AcmeError):
    """Input failed validation."""

    code = "ERR_VALIDATION"
    http_status = 400


class UnauthenticatedError(AcmeError):
    """Missing, invalid, expired or revoked credentials."""

    code = "ERR_UNAUTHENTICATED"
    http_status = 401


class PaymentFailedError(AcmeError):
    """The payment processor declined the charge."""

    code = "ERR_PAYMENT_FAILED"
    http_status = 402


class PermissionDeniedError(AcmeError):
    """The caller's role or key scope does not allow the action."""

    code = "ERR_PERMISSION_DENIED"
    http_status = 403


class PlanRequiredError(AcmeError):
    """The feature is not included in the account's plan."""

    code = "ERR_PLAN_REQUIRED"
    http_status = 403


class NotFoundError(AcmeError):
    """The resource does not exist."""

    code = "ERR_NOT_FOUND"
    http_status = 404


class ConflictError(AcmeError):
    """The action conflicts with the current state of the resource."""

    code = "ERR_CONFLICT"
    http_status = 409


class LimitExceededError(AcmeError):
    """A plan or resource limit is reached."""

    code = "ERR_LIMIT_EXCEEDED"
    http_status = 409


class AccountReadOnlyError(AcmeError):
    """The account is read_only, closed or deleted and cannot be edited."""

    code = "ERR_ACCOUNT_READ_ONLY"
    http_status = 423


class LockedOutError(AcmeError):
    """Login is temporarily locked after too many failed attempts."""

    code = "ERR_LOCKED_OUT"
    http_status = 423


class RateLimitedError(AcmeError):
    """Too many requests. ``retry_after`` is in seconds."""

    code = "ERR_RATE_LIMITED"
    http_status = 429

    def __init__(self, message: str = "", retry_after: int = 60, **details: object) -> None:
        super().__init__(message, retry_after=retry_after, **details)
        self.retry_after = retry_after
