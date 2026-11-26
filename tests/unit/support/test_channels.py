"""Support channels by plan; live chat Monday to Friday 08:00 to 18:00 Central."""

from __future__ import annotations

import pytest

from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PlanRequiredError
from acme_cloud.support import channels
from acme_cloud.support.channels import (
    channels_for, has_24x7_p1_support, has_customer_success_manager, is_channel_open,
    is_live_chat_open, require_channel,
)
from acme_cloud.support.models import Channel, Priority

BASIC = [Channel.HELP_CENTER, Channel.EMAIL]


@pytest.mark.parametrize("plan, expected", [
    (Plan.FREE, BASIC),
    (Plan.STARTER, BASIC),
    (Plan.PRO, BASIC + [Channel.CHAT]),
    (Plan.BUSINESS, BASIC + [Channel.CHAT, Channel.PHONE]),
    (Plan.ENTERPRISE, BASIC + [Channel.CHAT, Channel.PHONE]),
])
def test_channels_by_plan(plan, expected):
    assert channels_for(plan) == expected


def test_support_addresses():
    assert channels.HELP_CENTER_URL == "https://help.acme-cloud.example"
    assert channels.SUPPORT_EMAIL == "support@acme-cloud.example"
    assert channels.STATUS_PAGE_URL == "https://status.acme-cloud.example"
    assert (channels.LIVE_CHAT_OPEN_HOUR, channels.LIVE_CHAT_CLOSE_HOUR) == (8, 18)


@pytest.mark.parametrize("plan, channel", [
    (Plan.FREE, Channel.CHAT), (Plan.STARTER, Channel.CHAT),
    (Plan.STARTER, Channel.PHONE), (Plan.PRO, Channel.PHONE),
])
def test_using_a_channel_the_plan_lacks_is_plan_required(plan, channel):
    with pytest.raises(PlanRequiredError) as error:
        require_channel(plan, channel)
    assert error.value.code == "ERR_PLAN_REQUIRED"


def test_email_and_help_center_need_no_plan():
    for plan in Plan:
        require_channel(plan, Channel.EMAIL)
        require_channel(plan, Channel.HELP_CENTER)


@pytest.mark.parametrize("day, hour, minute, is_open", [
    (5, 7, 59, False),    # Monday, one minute before opening
    (5, 8, 0, True),      # Monday 08:00
    (7, 12, 30, True),    # Wednesday lunchtime
    (9, 17, 59, True),    # Friday, last minute
    (9, 18, 0, False),    # Friday 18:00 is closed
    (10, 10, 0, False),   # Saturday
    (11, 10, 0, False),   # Sunday
])
def test_live_chat_is_open_monday_to_friday_0800_to_1800_central(at_central, day, hour, minute,
                                                                  is_open):
    assert is_live_chat_open(Plan.PRO, at_central(day, hour, minute)) is is_open


@pytest.mark.parametrize("plan, has_chat", [
    (Plan.FREE, False), (Plan.STARTER, False), (Plan.PRO, True),
    (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_live_chat_needs_pro_or_higher(at_central, plan, has_chat):
    assert is_live_chat_open(plan, at_central(5, 10)) is has_chat


@pytest.mark.parametrize("plan, expected", [
    (Plan.FREE, False), (Plan.PRO, False), (Plan.BUSINESS, False), (Plan.ENTERPRISE, True),
])
def test_24x7_p1_support_and_named_csm_are_enterprise_only(plan, expected):
    assert has_24x7_p1_support(plan) is expected
    assert has_customer_success_manager(plan) is expected


def test_email_and_help_center_take_requests_at_any_time(at_central):
    saturday_night = at_central(10, 23)
    assert is_channel_open(Plan.FREE, Channel.EMAIL, saturday_night)
    assert is_channel_open(Plan.FREE, Channel.HELP_CENTER, saturday_night)
    assert not is_channel_open(Plan.FREE, Channel.CHAT, at_central(5, 10))  # not on the plan


def test_phone_follows_business_hours_except_enterprise_p1(at_central):
    monday_morning, saturday_night = at_central(5, 10), at_central(10, 23)
    assert is_channel_open(Plan.BUSINESS, Channel.PHONE, monday_morning)
    assert not is_channel_open(Plan.BUSINESS, Channel.PHONE, saturday_night, Priority.P1)
    assert is_channel_open(Plan.ENTERPRISE, Channel.PHONE, saturday_night, Priority.P1)
    assert not is_channel_open(Plan.ENTERPRISE, Channel.PHONE, saturday_night, Priority.P2)
    assert not is_channel_open(Plan.PRO, Channel.PHONE, monday_morning)
