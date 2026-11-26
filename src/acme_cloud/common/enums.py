"""Enums shared by all packages: plans, roles, account states and regions."""

from __future__ import annotations

from enum import Enum


class Plan(str, Enum):
    """Subscription plans, lowest to highest."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"

    @property
    def rank(self) -> int:
        """Position in the plan ladder: Free is 0, Enterprise is 4."""
        return _PLAN_ORDER.index(self)

    def at_least(self, other: "Plan") -> bool:
        """True when this plan is the same as or higher than ``other``."""
        return self.rank >= other.rank

    @property
    def is_paid(self) -> bool:
        return self is not Plan.FREE


_PLAN_ORDER = [Plan.FREE, Plan.STARTER, Plan.PRO, Plan.BUSINESS, Plan.ENTERPRISE]

#: Plan given to every new account for the 14-day trial.
TRIAL_PLAN = Plan.PRO
TRIAL_DAYS = 14


class Role(str, Enum):
    """Member roles. Exactly one OWNER exists per account."""

    OWNER = "owner"
    ADMIN = "admin"
    BILLING_ADMIN = "billing_admin"
    MEMBER = "member"
    GUEST = "guest"

    @property
    def uses_seat(self) -> bool:
        """Guests do not use a paid seat; every other role does."""
        return self is not Role.GUEST


class AccountState(str, Enum):
    """Lifecycle states of an account."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    READ_ONLY = "read_only"
    CLOSED = "closed"
    DELETED = "deleted"

    @property
    def can_edit(self) -> bool:
        """Users can edit content only in these states."""
        return self in (AccountState.TRIALING, AccountState.ACTIVE, AccountState.PAST_DUE)

    @property
    def can_log_in(self) -> bool:
        """Users can log in unless the account is closed or deleted."""
        return self not in (AccountState.CLOSED, AccountState.DELETED)


class Region(str, Enum):
    """Data regions. A workspace's region is fixed when it is created."""

    US_EAST = "us-east"
    EU_CENTRAL = "eu-central"
    AP_SOUTH = "ap-south"

    @property
    def location(self) -> str:
        return {
            Region.US_EAST: "Virginia, USA",
            Region.EU_CENTRAL: "Frankfurt, Germany",
            Region.AP_SOUTH: "Mumbai, India",
        }[self]

    @property
    def minimum_plan(self) -> Plan:
        """Lowest plan that may create a workspace in this region."""
        return {
            Region.US_EAST: Plan.FREE,
            Region.EU_CENTRAL: Plan.BUSINESS,
            Region.AP_SOUTH: Plan.ENTERPRISE,
        }[self]


DEFAULT_REGION = Region.US_EAST
