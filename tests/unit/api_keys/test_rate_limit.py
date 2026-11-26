"""Rate limits: 60 / 300 / 1,000 / 5,000 requests per minute per key; 429 with Retry-After."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.api_keys.rate_limit import (
    RATE_LIMIT_WINDOW_SECONDS, RateLimiter, requests_per_minute,
)
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PlanRequiredError, RateLimitedError

KEY = "key_TEST0001"

PLAN_LIMITS = [
    (Plan.STARTER, 60), (Plan.PRO, 300), (Plan.BUSINESS, 1000), (Plan.ENTERPRISE, 5000),
]


def use_up(limiter: RateLimiter, plan: Plan, key_id: str = KEY) -> None:
    for _ in range(requests_per_minute(plan)):
        limiter.check(key_id, plan)


def test_the_window_is_one_minute():
    assert RATE_LIMIT_WINDOW_SECONDS == 60


@pytest.mark.parametrize("plan, limit", [(Plan.FREE, 0)] + PLAN_LIMITS)
def test_requests_per_minute_by_plan(plan, limit):
    assert requests_per_minute(plan) == limit


@pytest.mark.parametrize("plan, limit", PLAN_LIMITS)
def test_a_key_may_make_exactly_its_plan_limit_in_one_minute(clock, plan, limit):
    limiter = RateLimiter(clock)
    statuses = [limiter.check(KEY, plan) for _ in range(limit)]
    assert statuses[0].remaining == limit - 1
    assert statuses[-1].remaining == 0
    with pytest.raises(RateLimitedError) as error:
        limiter.check(KEY, plan)
    assert error.value.code == "ERR_RATE_LIMITED"
    assert error.value.http_status == 429
    assert error.value.details["limit"] == limit


def test_free_plan_has_no_api(clock):
    with pytest.raises(PlanRequiredError):
        RateLimiter(clock).check(KEY, Plan.FREE)


@pytest.mark.parametrize("seconds_into_window, retry_after", [(0, 60), (20, 40), (59, 1)])
def test_retry_after_is_the_seconds_until_the_window_ends(clock, seconds_into_window, retry_after):
    limiter = RateLimiter(clock)
    use_up(limiter, Plan.STARTER)
    clock.advance(seconds=seconds_into_window)
    with pytest.raises(RateLimitedError) as error:
        limiter.check(KEY, Plan.STARTER)
    assert error.value.retry_after == retry_after
    assert error.value.to_dict()["error"]["details"]["retry_after"] == retry_after


def test_retry_after_is_rounded_up_to_a_whole_second(clock):
    limiter = RateLimiter(clock)
    use_up(limiter, Plan.STARTER)
    clock.advance(seconds=59.5)
    with pytest.raises(RateLimitedError) as error:
        limiter.check(KEY, Plan.STARTER)
    assert error.value.retry_after == 1


def test_a_new_window_starts_after_60_seconds(clock):
    limiter = RateLimiter(clock)
    use_up(limiter, Plan.STARTER)
    clock.advance(seconds=60)
    status = limiter.check(KEY, Plan.STARTER)
    assert status.remaining == 59
    assert status.reset_at == clock.now() + timedelta(seconds=60)


def test_rejected_requests_do_not_extend_the_window(clock):
    limiter = RateLimiter(clock)
    use_up(limiter, Plan.STARTER)
    for _ in range(3):
        clock.advance(seconds=15)
        with pytest.raises(RateLimitedError):
            limiter.check(KEY, Plan.STARTER)
    clock.advance(seconds=15)
    assert limiter.check(KEY, Plan.STARTER).remaining == 59


def test_the_limit_is_counted_per_key(clock):
    limiter = RateLimiter(clock)
    use_up(limiter, Plan.STARTER)
    assert limiter.check("key_TEST0002", Plan.STARTER).remaining == 59


def test_reset_forgets_a_keys_counter(clock):
    limiter = RateLimiter(clock)
    use_up(limiter, Plan.STARTER)
    limiter.reset(KEY)
    assert limiter.check(KEY, Plan.STARTER).remaining == 59
