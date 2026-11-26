"""Per-key REST API rate limiting.

Business rules:

| Plan | Requests per minute, per key |
|------|------------------------------|
| Free | No API |
| Starter | 60 |
| Pro | 300 |
| Business | 1,000 |
| Enterprise | 5,000 |

- The limit is counted per API key in fixed one-minute windows. A window
  starts with the key's first request and lasts 60 seconds.
- Over the limit the API answers **HTTP 429** (``ERR_RATE_LIMITED``) with
  a ``Retry-After`` header: the seconds until the window ends.
- The numbers come from ``acme_cloud.accounts.plans`` and are not
  repeated here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from acme_cloud.accounts.plans import limits_for, require_feature
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import RateLimitedError

RATE_LIMIT_WINDOW_SECONDS = 60


def requests_per_minute(plan: Plan) -> int:
    """Requests per minute allowed for one key on ``plan`` (0 on Free)."""
    return limits_for(plan).api_requests_per_minute


@dataclass(frozen=True)
class RateLimitStatus:
    """Values for the ``RateLimit-*`` response headers."""

    limit: int
    remaining: int
    reset_at: datetime


@dataclass
class _Window:
    started_at: datetime
    count: int = 0


class RateLimiter:
    """Fixed-window limiter with one counter per API key."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._windows: dict[str, _Window] = {}

    def _window(self, key_id: str) -> _Window:
        now = self._clock.now()
        window = self._windows.get(key_id)
        if window is None or now - window.started_at >= timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS):
            window = _Window(started_at=now)
            self._windows[key_id] = window
        return window

    def check(self, key_id: str, plan: Plan) -> RateLimitStatus:
        """Count one request for ``key_id``.

        Raises PlanRequiredError on Free (no API) and RateLimitedError,
        with ``retry_after`` in whole seconds (at least 1), when the key
        has used up its requests for the current minute.
        """
        require_feature(plan, "api_keys")
        limit = requests_per_minute(plan)
        window = self._window(key_id)
        reset_at = window.started_at + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
        if window.count >= limit:
            wait = (reset_at - self._clock.now()).total_seconds()
            raise RateLimitedError(
                f"Rate limit of {limit} requests per minute exceeded",
                retry_after=max(1, math.ceil(wait)), limit=limit,
            )
        window.count += 1
        return RateLimitStatus(limit=limit, remaining=limit - window.count, reset_at=reset_at)

    def reset(self, key_id: str) -> None:
        """Forget the counter of a key (for example after it is revoked)."""
        self._windows.pop(key_id, None)
