"""Webhook endpoints, signatures and the retry schedule (ADR 0009).

Business rules:

- Endpoints per workspace: Free 0, Starter 2, Pro 5, Business 20,
  Enterprise 50. Endpoint IDs look like ``wh_8C2V6B4N``.
- Events: ``account.state_changed``, ``member.invited``,
  ``member.removed``, ``invoice.paid``, ``invoice.payment_failed``,
  ``refund.succeeded``, ``api_key.created``, ``api_key.revoked``,
  ``export.ready``, ``sso.enforced``.
- Every delivery is signed with **HMAC-SHA256** using the endpoint's
  secret. The ``Acme-Signature`` header has the form
  ``t=<unix time>,v1=<hex digest>`` and the signed text is
  ``<unix time>.<raw body>``.
- The receiver must answer within **10 seconds**.
- A failed delivery is retried **6 times** over 24 hours: 1 minute,
  5 minutes, 30 minutes, 2 hours, 8 hours and 24 hours after the first
  attempt.
- An endpoint is disabled after **3 days** of continuous failures.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from acme_cloud.accounts.plans import limits_for, require_feature
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import LimitExceededError, NotFoundError, ValidationError
from acme_cloud.common.ids import IdGenerator

WEBHOOK_EVENTS = (
    "account.state_changed", "member.invited", "member.removed", "invoice.paid",
    "invoice.payment_failed", "refund.succeeded", "api_key.created", "api_key.revoked",
    "export.ready", "sso.enforced",
)
SIGNATURE_HEADER = "Acme-Signature"
WEBHOOK_TIMEOUT_SECONDS = 10
#: Delay of each retry, measured from the first (failed) attempt.
RETRY_SCHEDULE = (
    timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30),
    timedelta(hours=2), timedelta(hours=8), timedelta(hours=24),
)
MAX_RETRIES = len(RETRY_SCHEDULE)  # 6
DISABLE_AFTER_FAILING_DAYS = 3
#: Receivers should reject signatures whose timestamp is older than this.
SIGNATURE_TOLERANCE_SECONDS = 300


def sign_payload(secret: str, payload: bytes, timestamp: int) -> str:
    """Return the ``Acme-Signature`` header value for ``payload``."""
    signed = f"{timestamp}.".encode("ascii") + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_signature(secret: str, payload: bytes, header: str, now: datetime | None = None,
                     tolerance_seconds: int = SIGNATURE_TOLERANCE_SECONDS) -> bool:
    """Check an ``Acme-Signature`` header the way a receiver should.

    Returns False for a malformed header, a wrong digest, or (when ``now``
    is given) a timestamp more than ``tolerance_seconds`` away from now.
    """
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    if "t" not in parts or "v1" not in parts or not parts["t"].isdigit():
        return False
    timestamp = int(parts["t"])
    if not hmac.compare_digest(sign_payload(secret, payload, timestamp), f"t={timestamp},v1={parts['v1']}"):
        return False
    return now is None or abs(now.timestamp() - timestamp) <= tolerance_seconds


def retry_time(first_attempt_at: datetime, retry_number: int) -> datetime | None:
    """When retry ``retry_number`` (1 to 6) is due; ``None`` after the sixth."""
    if retry_number < 1:
        raise ValueError("retry_number starts at 1")
    if retry_number > MAX_RETRIES:
        return None
    return first_attempt_at + RETRY_SCHEDULE[retry_number - 1]


def max_endpoints(plan: Plan) -> int:
    """Webhook endpoints a workspace may have on ``plan``."""
    return limits_for(plan).max_webhook_endpoints


@dataclass
class WebhookEndpoint:
    id: str
    workspace_id: str
    url: str
    events: frozenset[str]
    secret: str
    created_at: datetime
    enabled: bool = True
    #: Start of the current run of failed deliveries, if any.
    failing_since: datetime | None = None
    disabled_at: datetime | None = None


class WebhookRegistry:
    """Stores webhook endpoints and tracks their delivery health."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None) -> None:
        self._clock = clock
        self._ids = ids or IdGenerator()
        self._endpoints: dict[str, WebhookEndpoint] = {}

    def list_endpoints(self, workspace_id: str) -> list[WebhookEndpoint]:
        return [e for e in self._endpoints.values() if e.workspace_id == workspace_id]

    def get(self, endpoint_id: str) -> WebhookEndpoint:
        if endpoint_id not in self._endpoints:
            raise NotFoundError("Webhook endpoint not found", endpoint_id=endpoint_id)
        return self._endpoints[endpoint_id]

    def add_endpoint(self, workspace_id: str, plan: Plan, url: str,
                     events: list[str]) -> WebhookEndpoint:
        """Register an https endpoint for one or more events.

        Raises PlanRequiredError on Free and LimitExceededError at the
        plan's endpoint limit (disabled endpoints count until removed).
        """
        require_feature(plan, "api_keys")
        if not url.startswith("https://"):
            raise ValidationError("Webhook URL must use https")
        unknown = sorted(set(events) - set(WEBHOOK_EVENTS))
        if unknown or not events:
            raise ValidationError("Choose one or more known webhook events", events=unknown)
        if len(self.list_endpoints(workspace_id)) >= max_endpoints(plan):
            raise LimitExceededError("Webhook endpoint limit reached", limit=max_endpoints(plan))
        endpoint = WebhookEndpoint(
            id=self._ids.new("wh"), workspace_id=workspace_id, url=url,
            events=frozenset(events), secret="whsec_" + secrets.token_hex(24),
            created_at=self._clock.now(),
        )
        self._endpoints[endpoint.id] = endpoint
        return endpoint

    def remove_endpoint(self, endpoint_id: str) -> None:
        self.get(endpoint_id)
        del self._endpoints[endpoint_id]

    def endpoints_for(self, workspace_id: str, event: str) -> list[WebhookEndpoint]:
        """Enabled endpoints of a workspace that subscribed to ``event``."""
        return [e for e in self.list_endpoints(workspace_id) if e.enabled and event in e.events]

    def record_delivery(self, endpoint_id: str, succeeded: bool) -> WebhookEndpoint:
        """Record a delivery result (a timeout after 10 seconds is a failure).

        A success ends the failure run. When failures have continued for
        3 days the endpoint is disabled.
        """
        endpoint = self.get(endpoint_id)
        now = self._clock.now()
        if succeeded:
            endpoint.failing_since = None
        elif endpoint.failing_since is None:
            endpoint.failing_since = now
        elif endpoint.enabled and now - endpoint.failing_since >= timedelta(days=DISABLE_AFTER_FAILING_DAYS):
            endpoint.enabled = False
            endpoint.disabled_at = now
        return endpoint

    def enable(self, endpoint_id: str) -> WebhookEndpoint:
        """Turn a disabled endpoint back on and clear its failure run."""
        endpoint = self.get(endpoint_id)
        endpoint.enabled, endpoint.failing_since, endpoint.disabled_at = True, None, None
        return endpoint
