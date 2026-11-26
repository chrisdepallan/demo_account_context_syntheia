"""Sessions: web 14 days, mobile 90 days of inactivity; custom web length on Business+."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.auth import sessions
from acme_cloud.auth.sessions import (
    Device, SessionManager, inactivity_limit, validate_web_session_hours,
)
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PlanRequiredError, UnauthenticatedError, ValidationError
from acme_cloud.common.ids import is_valid_id

USER = "usr_TEST0001"


def test_constants_match_the_facts_sheet():
    assert sessions.WEB_SESSION_INACTIVITY_DAYS == 14
    assert sessions.MOBILE_SESSION_INACTIVITY_DAYS == 90
    assert sessions.MIN_WEB_SESSION_HOURS == 1
    assert sessions.MAX_WEB_SESSION_HOURS == 14 * 24


def test_session_ids_use_the_ses_prefix(clock, ids):
    session = SessionManager(clock, ids).create(USER)
    assert is_valid_id(session.id, "ses")
    assert session.device is Device.WEB


@pytest.mark.parametrize("device, idle, active", [
    (Device.WEB, timedelta(days=13, hours=23), True),
    (Device.WEB, timedelta(days=14), False),
    (Device.MOBILE, timedelta(days=89, hours=23), True),
    (Device.MOBILE, timedelta(days=90), False),
])
def test_sessions_end_after_14_days_web_or_90_days_mobile_of_inactivity(clock, ids, device,
                                                                        idle, active):
    manager = SessionManager(clock, ids)
    session = manager.create(USER, device)
    clock.advance(seconds=idle.total_seconds())
    assert manager.is_active(session) is active


def test_activity_restarts_the_inactivity_timer(clock, ids):
    manager = SessionManager(clock, ids)
    session = manager.create(USER)
    clock.advance(days=13)
    manager.touch(session.id)
    clock.advance(days=13)
    assert manager.touch(session.id).id == session.id  # 26 days old, but never idle for 14


def test_expired_session_is_refused_with_unauthenticated(clock, ids):
    manager = SessionManager(clock, ids)
    session = manager.create(USER)
    clock.advance(days=14)
    with pytest.raises(UnauthenticatedError) as error:
        manager.touch(session.id)
    assert error.value.http_status == 401


@pytest.mark.parametrize("hours, accepted", [(0, False), (1, True), (336, True), (337, False)])
def test_business_can_set_web_sessions_between_1_hour_and_14_days(hours, accepted):
    if accepted:
        validate_web_session_hours(Plan.BUSINESS, hours)
    else:
        with pytest.raises(ValidationError):
            validate_web_session_hours(Plan.BUSINESS, hours)


@pytest.mark.parametrize("plan, allowed", [
    (Plan.FREE, False), (Plan.STARTER, False), (Plan.PRO, False),
    (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_web_session_length_setting_needs_business_or_enterprise(plan, allowed):
    validate_web_session_hours(plan, None)  # the default is fine on every plan
    if allowed:
        validate_web_session_hours(plan, 8)
    else:
        with pytest.raises(PlanRequiredError):
            validate_web_session_hours(plan, 8)


def test_custom_web_length_applies_to_web_but_not_mobile(clock, ids):
    manager = SessionManager(clock, ids)
    web = manager.create(USER, Device.WEB)
    mobile = manager.create(USER, Device.MOBILE)
    assert inactivity_limit(Device.MOBILE, web_session_hours=1) == timedelta(days=90)

    clock.advance(minutes=59)
    assert manager.is_active(web, web_session_hours=1)
    clock.advance(minutes=1)
    assert not manager.is_active(web, web_session_hours=1)
    assert manager.is_active(mobile, web_session_hours=1)


def test_sign_out_ends_one_session(clock, ids):
    manager = SessionManager(clock, ids)
    first, second = manager.create(USER), manager.create(USER)
    manager.sign_out(first.id)
    assert [s.id for s in manager.active_sessions(USER)] == [second.id]
    with pytest.raises(UnauthenticatedError):
        manager.touch(first.id)


def test_sign_out_all_ends_every_session_of_the_user_only(clock, ids):
    manager = SessionManager(clock, ids)
    manager.create(USER, Device.WEB)
    manager.create(USER, Device.MOBILE)
    other = manager.create("usr_TEST0002")
    assert manager.sign_out_all(USER) == 2
    assert manager.active_sessions(USER) == []
    assert manager.is_active(other)


def test_sign_out_all_can_keep_the_current_session(clock, ids):
    manager = SessionManager(clock, ids)
    current, _ = manager.create(USER), manager.create(USER)
    assert manager.sign_out_all(USER, except_session_id=current.id) == 1
    assert [s.id for s in manager.active_sessions(USER)] == [current.id]
