"""Webhooks: endpoint limits, Acme-Signature (HMAC-SHA256), six retries, 3-day disable."""

from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta

import pytest

from acme_cloud.api_keys import webhooks
from acme_cloud.api_keys.webhooks import (
    WebhookRegistry, max_endpoints, retry_time, sign_payload, verify_signature,
)
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import LimitExceededError, PlanRequiredError, ValidationError
from acme_cloud.common.ids import is_valid_id

WS = "ws_TEST01"
URL = "https://hooks.example.com/acme"
SECRET = "whsec_example_secret_for_tests"
PAYLOAD = b'{"event":"invoice.paid","id":"INV-2026-000001"}'


def test_constants_match_the_facts_sheet():
    assert webhooks.SIGNATURE_HEADER == "Acme-Signature"
    assert webhooks.WEBHOOK_TIMEOUT_SECONDS == 10
    assert webhooks.MAX_RETRIES == 6
    assert webhooks.DISABLE_AFTER_FAILING_DAYS == 3
    assert webhooks.WEBHOOK_EVENTS == (
        "account.state_changed", "member.invited", "member.removed", "invoice.paid",
        "invoice.payment_failed", "refund.succeeded", "api_key.created", "api_key.revoked",
        "export.ready", "sso.enforced",
    )


def test_signature_is_hmac_sha256_over_timestamp_and_body(clock):
    timestamp = int(clock.now().timestamp())
    expected = hmac.new(SECRET.encode(), f"{timestamp}.".encode() + PAYLOAD, hashlib.sha256)
    header = sign_payload(SECRET, PAYLOAD, timestamp)
    assert header == f"t={timestamp},v1={expected.hexdigest()}"
    assert verify_signature(SECRET, PAYLOAD, header, clock.now())


def test_tampered_body_wrong_secret_or_malformed_header_fail_verification(clock):
    header = sign_payload(SECRET, PAYLOAD, int(clock.now().timestamp()))
    assert not verify_signature(SECRET, PAYLOAD + b" ", header)
    assert not verify_signature("whsec_other", PAYLOAD, header)
    assert not verify_signature(SECRET, PAYLOAD, "v1=abc")
    assert not verify_signature(SECRET, PAYLOAD, "")


def test_old_signatures_are_rejected_to_stop_replays(clock):
    header = sign_payload(SECRET, PAYLOAD, int(clock.now().timestamp()))
    assert verify_signature(SECRET, PAYLOAD, header, clock.now() + timedelta(minutes=5))
    assert not verify_signature(SECRET, PAYLOAD, header, clock.now() + timedelta(minutes=6))


@pytest.mark.parametrize("retry_number, delay", [
    (1, timedelta(minutes=1)), (2, timedelta(minutes=5)), (3, timedelta(minutes=30)),
    (4, timedelta(hours=2)), (5, timedelta(hours=8)), (6, timedelta(hours=24)),
])
def test_retry_schedule_is_1m_5m_30m_2h_8h_24h_after_the_first_attempt(clock, retry_number, delay):
    assert retry_time(clock.now(), retry_number) == clock.now() + delay


def test_there_is_no_seventh_retry(clock):
    assert retry_time(clock.now(), 7) is None
    with pytest.raises(ValueError):
        retry_time(clock.now(), 0)


@pytest.mark.parametrize("plan, limit", [
    (Plan.FREE, 0), (Plan.STARTER, 2), (Plan.PRO, 5), (Plan.BUSINESS, 20), (Plan.ENTERPRISE, 50),
])
def test_endpoint_limit_by_plan(clock, ids, plan, limit):
    assert max_endpoints(plan) == limit
    registry = WebhookRegistry(clock, ids)
    if plan is Plan.FREE:
        with pytest.raises(PlanRequiredError):
            registry.add_endpoint(WS, plan, URL, ["invoice.paid"])
        return
    for number in range(limit):
        registry.add_endpoint(WS, plan, f"{URL}/{number}", ["invoice.paid"])
    with pytest.raises(LimitExceededError):
        registry.add_endpoint(WS, plan, f"{URL}/one-too-many", ["invoice.paid"])
    registry.add_endpoint("ws_TEST02", plan, URL, ["invoice.paid"])  # limit is per workspace


def test_endpoint_has_a_wh_id_and_its_own_signing_secret(clock, ids):
    registry = WebhookRegistry(clock, ids)
    first = registry.add_endpoint(WS, Plan.PRO, URL, ["invoice.paid", "export.ready"])
    second = registry.add_endpoint(WS, Plan.PRO, URL + "/2", ["invoice.paid"])
    assert is_valid_id(first.id, "wh")
    assert first.secret.startswith("whsec_") and first.secret != second.secret
    assert first.enabled


@pytest.mark.parametrize("url, events", [
    ("http://hooks.example.com/acme", ["invoice.paid"]),   # not https
    (URL, ["invoice.created"]),                            # unknown event
    (URL, []),                                             # no events
])
def test_invalid_endpoints_are_rejected(clock, ids, url, events):
    with pytest.raises(ValidationError):
        WebhookRegistry(clock, ids).add_endpoint(WS, Plan.PRO, url, events)


def test_events_go_only_to_enabled_endpoints_that_subscribed(clock, ids):
    registry = WebhookRegistry(clock, ids)
    paid = registry.add_endpoint(WS, Plan.PRO, URL, ["invoice.paid"])
    registry.add_endpoint(WS, Plan.PRO, URL + "/exports", ["export.ready"])
    assert [e.id for e in registry.endpoints_for(WS, "invoice.paid")] == [paid.id]
    assert registry.endpoints_for(WS, "member.invited") == []
    registry.remove_endpoint(paid.id)
    assert registry.endpoints_for(WS, "invoice.paid") == []


@pytest.mark.parametrize("failing_for, disabled", [
    (timedelta(days=2, hours=23), False), (timedelta(days=3), True),
])
def test_endpoint_is_disabled_after_3_days_of_continuous_failures(clock, ids, failing_for, disabled):
    registry = WebhookRegistry(clock, ids)
    endpoint = registry.add_endpoint(WS, Plan.PRO, URL, ["invoice.paid"])
    registry.record_delivery(endpoint.id, succeeded=False)
    clock.advance(seconds=failing_for.total_seconds())
    registry.record_delivery(endpoint.id, succeeded=False)
    assert endpoint.enabled is not disabled
    assert (endpoint.disabled_at == clock.now()) is disabled
    assert bool(registry.endpoints_for(WS, "invoice.paid")) is not disabled


def test_a_success_ends_the_failure_run(clock, ids):
    registry = WebhookRegistry(clock, ids)
    endpoint = registry.add_endpoint(WS, Plan.PRO, URL, ["invoice.paid"])
    registry.record_delivery(endpoint.id, succeeded=False)
    clock.advance(days=2)
    registry.record_delivery(endpoint.id, succeeded=True)
    clock.advance(days=2)
    registry.record_delivery(endpoint.id, succeeded=False)  # a new run starts here
    assert endpoint.enabled and endpoint.failing_since == clock.now()


def test_a_disabled_endpoint_can_be_enabled_again(clock, ids):
    registry = WebhookRegistry(clock, ids)
    endpoint = registry.add_endpoint(WS, Plan.PRO, URL, ["invoice.paid"])
    registry.record_delivery(endpoint.id, succeeded=False)
    clock.advance(days=3)
    registry.record_delivery(endpoint.id, succeeded=False)
    assert not endpoint.enabled
    registry.enable(endpoint.id)
    assert endpoint.enabled and endpoint.failing_since is None and endpoint.disabled_at is None
