"""Support channels by plan and their opening hours.

Business rules:

| Channel | Plans | Hours |
|---------|-------|-------|
| Help center (``https://help.acme-cloud.example``) | all | always |
| Email (``support@acme-cloud.example``) | all | always (answered per SLA) |
| In-app live chat | Pro and above | Monday to Friday, 08:00 to 18:00 US Central Time |
| Phone | Business and Enterprise | business hours; any time for an Enterprise P1 |

- Enterprise has 24/7 support for P1 incidents and a named Customer
  Success Manager.
- A request on a channel the plan does not include is refused with
  ``ERR_PLAN_REQUIRED``.
"""

from __future__ import annotations

from datetime import datetime

from acme_cloud.accounts.plans import has_feature, require_feature
from acme_cloud.common.clock import is_business_time
from acme_cloud.common.enums import Plan
from acme_cloud.support.models import Channel, Priority, to_central

HELP_CENTER_URL = "https://help.acme-cloud.example"
SUPPORT_EMAIL = "support@acme-cloud.example"
STATUS_PAGE_URL = "https://status.acme-cloud.example"

LIVE_CHAT_DAYS = "Monday to Friday"
LIVE_CHAT_OPEN_HOUR = 8
LIVE_CHAT_CLOSE_HOUR = 18

#: Channel -> feature key in ``acme_cloud.accounts.plans`` (None = all plans).
CHANNEL_FEATURE: dict[Channel, str | None] = {
    Channel.HELP_CENTER: None,
    Channel.EMAIL: None,
    Channel.CHAT: "live_chat",
    Channel.PHONE: "phone_support",
}


def plan_has_channel(plan: Plan, channel: Channel) -> bool:
    """True when ``plan`` includes ``channel``."""
    feature = CHANNEL_FEATURE[channel]
    return feature is None or has_feature(plan, feature)


def channels_for(plan: Plan) -> list[Channel]:
    """Channels a customer on ``plan`` can use, in the order shown in the dashboard."""
    return [channel for channel in Channel if plan_has_channel(plan, channel)]


def require_channel(plan: Plan, channel: Channel) -> None:
    """Raise PlanRequiredError when ``plan`` does not include ``channel``."""
    feature = CHANNEL_FEATURE[channel]
    if feature is not None:
        require_feature(plan, feature)


def has_24x7_p1_support(plan: Plan) -> bool:
    """24/7 cover for P1 incidents is Enterprise only."""
    return has_feature(plan, "support_24x7")


def has_customer_success_manager(plan: Plan) -> bool:
    """A named Customer Success Manager is Enterprise only."""
    return plan is Plan.ENTERPRISE


def is_live_chat_open(plan: Plan, now: datetime) -> bool:
    """True when in-app chat is staffed for this plan at ``now`` (UTC).

    Chat needs Pro or higher and is open Monday to Friday, 08:00 to
    18:00 US Central Time (18:00 itself is closed).
    """
    return plan_has_channel(plan, Channel.CHAT) and is_business_time(to_central(now))


def is_channel_open(plan: Plan, channel: Channel, now: datetime,
                    priority: Priority | None = None) -> bool:
    """True when a customer on ``plan`` can reach support on ``channel`` at ``now`` (UTC).

    The help center and email accept requests at any time. Chat and
    phone follow business hours, except that an Enterprise customer can
    phone about a P1 at any time.
    """
    if not plan_has_channel(plan, channel):
        return False
    if channel in (Channel.HELP_CENTER, Channel.EMAIL):
        return True
    if channel is Channel.PHONE and priority is Priority.P1 and has_24x7_p1_support(plan):
        return True
    return is_business_time(to_central(now))
