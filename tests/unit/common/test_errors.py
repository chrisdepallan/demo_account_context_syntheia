"""Error codes and HTTP statuses match the error table in the facts sheet."""

from __future__ import annotations

import pytest

from acme_cloud.common import errors
from acme_cloud.common.errors import AcmeError, RateLimitedError

ERROR_TABLE = [
    (errors.ValidationError, "ERR_VALIDATION", 400),
    (errors.UnauthenticatedError, "ERR_UNAUTHENTICATED", 401),
    (errors.PaymentFailedError, "ERR_PAYMENT_FAILED", 402),
    (errors.PermissionDeniedError, "ERR_PERMISSION_DENIED", 403),
    (errors.PlanRequiredError, "ERR_PLAN_REQUIRED", 403),
    (errors.NotFoundError, "ERR_NOT_FOUND", 404),
    (errors.ConflictError, "ERR_CONFLICT", 409),
    (errors.LimitExceededError, "ERR_LIMIT_EXCEEDED", 409),
    (errors.AccountReadOnlyError, "ERR_ACCOUNT_READ_ONLY", 423),
    (errors.LockedOutError, "ERR_LOCKED_OUT", 423),
    (errors.RateLimitedError, "ERR_RATE_LIMITED", 429),
    (errors.AcmeError, "ERR_INTERNAL", 500),
]


@pytest.mark.parametrize(("error_class", "code", "http_status"), ERROR_TABLE)
def test_code_and_http_status(error_class, code, http_status):
    assert error_class.code == code
    assert error_class.http_status == http_status


@pytest.mark.parametrize("error_class", [row[0] for row in ERROR_TABLE])
def test_every_error_is_an_acme_error(error_class):
    assert issubclass(error_class, AcmeError)
    assert issubclass(error_class, Exception)


def test_error_codes_are_unique():
    codes = [row[1] for row in ERROR_TABLE]
    assert len(set(codes)) == len(codes) == 12


def test_message_defaults_to_the_code():
    error = errors.NotFoundError()
    assert error.message == "ERR_NOT_FOUND"
    assert str(error) == "ERR_NOT_FOUND"
    assert error.details == {}


def test_details_are_kept_for_the_api_response():
    error = errors.LimitExceededError("the free plan allows 3 members", limit=3, current=3)
    assert error.details == {"limit": 3, "current": 3}
    assert error.to_dict() == {
        "error": {
            "code": "ERR_LIMIT_EXCEEDED",
            "message": "the free plan allows 3 members",
            "details": {"limit": 3, "current": 3},
        }
    }


def test_errors_can_be_caught_by_the_base_class():
    with pytest.raises(AcmeError) as caught:
        raise errors.ConflictError("an export is already running")
    assert caught.value.code == "ERR_CONFLICT"


def test_rate_limited_carries_retry_after_seconds():
    """HTTP 429 answers include ``Retry-After`` in seconds."""
    error = RateLimitedError("slow down", retry_after=17)
    assert error.retry_after == 17
    assert error.details["retry_after"] == 17
    assert RateLimitedError().retry_after == 60
