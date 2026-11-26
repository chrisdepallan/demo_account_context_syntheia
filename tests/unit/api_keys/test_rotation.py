"""Rotation (24-hour grace), revocation (within 60 seconds) and the 14-day expiry warning."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.api_keys import rotation
from acme_cloud.api_keys.rotation import KeyCache, needs_expiry_warning, revocation_effective_by
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    ConflictError, PermissionDeniedError, UnauthenticatedError, ValidationError,
)

OWNER = dict(plan=Plan.PRO, actor_id="usr_OWNER001", actor_role=Role.OWNER)


def test_constants_match_the_facts_sheet():
    assert rotation.KEY_CACHE_TTL_SECONDS == 60   # fixed in code since INC-2026-006
    assert rotation.ROTATION_GRACE_HOURS == 24
    assert rotation.EXPIRY_WARNING_DAYS == 14


def test_rotation_issues_a_new_key_with_the_same_name_scopes_and_expiry_length(create, service):
    old, old_full = create(name="Deploy bot", scopes=["files:read"], expires_in_days=180)
    new, new_full = service.rotate(old.id, **OWNER)
    assert new.id != old.id and new_full != old_full
    assert (new.name, new.scopes) == ("Deploy bot", frozenset({"files:read"}))
    assert new.expires_at - new.created_at == timedelta(days=180)
    assert old.replaced_by == new.id
    assert service.authenticate(new_full) == frozenset({"files:read"})


@pytest.mark.parametrize("elapsed, works", [
    (timedelta(hours=23, minutes=59), True),
    (timedelta(hours=24), False),
    (timedelta(hours=24, minutes=1), False),
])
def test_old_key_works_for_24_hours_after_rotation(create, service, clock, elapsed, works):
    old, old_full = create()
    service.rotate(old.id, **OWNER)
    clock.advance(seconds=elapsed.total_seconds())
    if works:
        assert service.authenticate(old_full)
    else:
        with pytest.raises(UnauthenticatedError):
            service.authenticate(old_full)


def test_rotation_works_at_the_25_key_limit(create, service):
    keys = [create(name=f"key {number}")[0] for number in range(25)]
    service.rotate(keys[0].id, **OWNER)
    assert len(service.list_keys("ws_TEST01", active_only=True)) == 25


def test_a_rotated_or_revoked_key_cannot_be_rotated_again(create, service):
    old, _ = create()
    service.rotate(old.id, **OWNER)
    with pytest.raises(ConflictError):
        service.rotate(old.id, **OWNER)


def test_rotating_a_never_expiring_key_is_blocked_by_require_key_expiry(create, service):
    old, _ = create(expires_in_days=None)
    with pytest.raises(ValidationError):
        service.rotate(old.id, require_key_expiry=True, **OWNER)
    assert old.rotated_at is None


def test_members_cannot_rotate_or_revoke(create, service):
    key, _ = create()
    with pytest.raises(PermissionDeniedError):
        service.rotate(key.id, Plan.PRO, "usr_MEMBER01", Role.MEMBER)
    with pytest.raises(PermissionDeniedError):
        service.revoke(key.id, Plan.PRO, "usr_MEMBER01", Role.MEMBER)


def test_revoked_key_that_no_node_has_cached_fails_at_once(create, service):
    key, full_key = create()
    service.revoke(key.id, **OWNER)
    with pytest.raises(UnauthenticatedError):
        service.authenticate(full_key)


@pytest.mark.parametrize("seconds, may_still_work", [(59, True), (60, False), (61, False)])
def test_revocation_takes_effect_within_60_seconds_even_when_cached(create, service, clock,
                                                                    seconds, may_still_work):
    key, full_key = create()
    service.authenticate(full_key)          # an API node caches the lookup
    service.revoke(key.id, **OWNER)
    assert revocation_effective_by(key) == clock.now() + timedelta(seconds=60)
    clock.advance(seconds=seconds)
    if may_still_work:
        assert service.authenticate(full_key)
    else:
        with pytest.raises(UnauthenticatedError):
            service.authenticate(full_key)


def test_cache_entries_live_for_60_seconds_and_are_not_refreshed_by_reads(clock):
    cache = KeyCache(clock)
    cache.put("hash", "key_TEST0001", frozenset({"files:read"}))
    clock.advance(seconds=40)
    assert cache.get("hash").key_id == "key_TEST0001"
    clock.advance(seconds=20)
    assert cache.get("hash") is None


def test_rotate_and_revoke_write_audit_events(create, service, audit):
    old, _ = create()
    new, _ = service.rotate(old.id, **OWNER)
    service.revoke(new.id, **OWNER)
    service.revoke(new.id, **OWNER)  # revoking twice is a no-op
    assert audit.types() == ["api_key.created", "api_key.rotated", "api_key.revoked"]
    assert audit.events[1][4] == {"key_id": old.id, "new_key_id": new.id}


@pytest.mark.parametrize("days_before_expiry, warned", [(15, False), (14, True), (1, True)])
def test_owner_is_warned_14_days_before_a_key_expires(create, service, clock, notifier,
                                                      days_before_expiry, warned):
    key, _ = create(expires_in_days=30)
    clock.advance(days=30 - days_before_expiry)
    assert needs_expiry_warning(key, clock.now()) is warned
    sent = service.send_expiry_warnings("ws_TEST01", "owner@example.com")
    assert [k.id for k in sent] == ([key.id] if warned else [])
    if warned:
        template, to, context = notifier.sent[0]
        assert (template, to, context["key_id"]) == ("key_expiring", ["owner@example.com"], key.id)


def test_expiry_warning_is_sent_once_and_never_for_inactive_or_non_expiring_keys(
        create, service, clock, notifier):
    expiring, _ = create(name="expiring", expires_in_days=30)
    revoked, _ = create(name="revoked", expires_in_days=30)
    create(name="never", expires_in_days=None)
    service.revoke(revoked.id, **OWNER)
    clock.advance(days=20)
    assert [k.id for k in service.send_expiry_warnings("ws_TEST01", "owner@example.com")] == [expiring.id]
    assert service.send_expiry_warnings("ws_TEST01", "owner@example.com") == []
    assert len(notifier.sent) == 1
