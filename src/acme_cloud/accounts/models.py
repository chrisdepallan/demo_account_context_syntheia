"""Data models of the accounts package.

An **account** is the paying customer: it has one plan, one lifecycle state,
a number of paid seats and a list of members. Business rules that shape the
models:

- Exactly one member has the ``owner`` role; ``Account.owner_id`` points at it.
- Every role except ``guest`` uses one paid seat. Guests are free, up to
  5 guests per paid seat (5 in total on Free).
- New accounts start in ``trialing`` on Pro; ``trial_ends_at`` is 14 days
  after creation.
- A closed account remembers ``closed_at`` and ``state_before_close`` so the
  Owner can restore it to the previous state within 30 days.
- An invitation is valid for 7 days. An ownership transfer request must be
  accepted by the chosen Admin within 7 days.

The models hold data and small read-only helpers. The rules live in the
sibling modules (``members``, ``invitations``, ``ownership``,
``state_machine``) and ``AccountService`` ties them together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from acme_cloud.common.enums import AccountState, Plan, Role
from acme_cloud.common.errors import NotFoundError

#: Status values of an ownership transfer request.
TRANSFER_PENDING = "pending"
TRANSFER_ACCEPTED = "accepted"
TRANSFER_EXPIRED = "expired"
TRANSFER_CANCELLED = "cancelled"


@dataclass
class Member:
    """A person who belongs to an account, with exactly one role."""

    user_id: str
    email: str
    role: Role
    joined_at: datetime
    mfa_enrolled: bool = False
    invited_by: str | None = None

    @property
    def uses_seat(self) -> bool:
        """Guests do not use a paid seat; every other role does."""
        return self.role.uses_seat


@dataclass
class Invitation:
    """An emailed invitation to join an account. Valid for 7 days."""

    id: str
    account_id: str
    email: str
    role: Role
    invited_by: str
    created_at: datetime
    expires_at: datetime
    last_sent_at: datetime
    accepted_at: datetime | None = None
    resend_count: int = 0

    def is_expired(self, now: datetime) -> bool:
        """True once the 7 days have passed without the invitation being accepted."""
        return self.accepted_at is None and now >= self.expires_at

    def is_pending(self, now: datetime) -> bool:
        """True while the invitation can still be accepted."""
        return self.accepted_at is None and now < self.expires_at


@dataclass
class OwnershipTransfer:
    """A request by the Owner to hand the account to an existing Admin."""

    id: str
    account_id: str
    from_user_id: str
    to_user_id: str
    requested_at: datetime
    expires_at: datetime
    status: str = TRANSFER_PENDING
    completed_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        """True when the 7-day acceptance window has passed."""
        return self.status == TRANSFER_EXPIRED or (
            self.status == TRANSFER_PENDING and now >= self.expires_at
        )


@dataclass
class Account:
    """A customer account: plan, lifecycle state, seats and members."""

    id: str
    name: str
    owner_id: str
    plan: Plan
    state: AccountState
    created_at: datetime
    seats: int = 1
    trial_ends_at: datetime | None = None
    closed_at: datetime | None = None
    state_before_close: AccountState | None = None
    state_changed_at: datetime | None = None
    storage_packs: int = 0
    trial_reminder_sent: bool = False
    members: dict[str, Member] = field(default_factory=dict)
    invitations: dict[str, Invitation] = field(default_factory=dict)
    pending_transfer: OwnershipTransfer | None = None
    #: content item ID -> user ID of the member who owns it.
    content_owners: dict[str, str] = field(default_factory=dict)

    def member(self, user_id: str) -> Member:
        """Return the member with ``user_id`` or raise NotFoundError."""
        try:
            return self.members[user_id]
        except KeyError:
            raise NotFoundError(f"{user_id} is not a member of {self.id}", user_id=user_id) from None

    def find_member_by_email(self, email: str) -> Member | None:
        """Return the member with this email address (case-insensitive), if any."""
        wanted = email.strip().lower()
        return next((m for m in self.members.values() if m.email.lower() == wanted), None)

    @property
    def owner(self) -> Member:
        """The single Owner of the account."""
        return self.member(self.owner_id)

    @property
    def seat_member_count(self) -> int:
        """Members that use a paid seat (everyone except guests)."""
        return sum(1 for m in self.members.values() if m.uses_seat)

    @property
    def guest_count(self) -> int:
        """Guests on the account. Guests do not use seats."""
        return sum(1 for m in self.members.values() if m.role is Role.GUEST)

    def emails_for_roles(self, *roles: Role) -> list[str]:
        """Email addresses of all members holding one of ``roles`` (for notifications)."""
        return [m.email for m in self.members.values() if m.role in roles]
