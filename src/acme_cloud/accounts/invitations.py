"""Member invitations.

Rules implemented here:

- Owners and Admins (``members.manage``) invite people by email from
  Settings -> Members -> Invite.
- A batch holds **1 to 50** email addresses. Batch 51 is rejected with
  ``ERR_VALIDATION`` and nothing is sent.
- An invitation **expires after 7 days**. It can be **resent**, which starts
  a new 7-day window (also for an invitation that already expired) and sends
  the ``invitation`` email again.
- Pending invitations reserve their place: members plus pending invitations
  may not exceed the plan's member limit (Free 3, Starter 10, Pro 100,
  Business 500), and pending guest invitations count toward the guest limit
  (5 per paid seat).
- Nobody can be invited as Owner. An address that is already a member or
  already has a pending invitation is rejected with ``ERR_CONFLICT``.
- Accepting an invitation creates the member with the invited role. An
  expired or already accepted invitation cannot be accepted.

A batch is all-or-nothing: if any address fails, no invitation is created.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from acme_cloud.accounts import members, permissions
from acme_cloud.accounts.models import Account, Invitation, Member
from acme_cloud.accounts.state_machine import require_editable
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Role
from acme_cloud.common.errors import ConflictError, NotFoundError, ValidationError
from acme_cloud.common.ids import IdGenerator

#: Largest number of email addresses in one invitation batch.
MAX_INVITATIONS_PER_BATCH = 50
#: Days an invitation stays valid after it is sent or resent.
INVITATION_TTL_DAYS = 7


def normalize_email(email: str) -> str:
    """Trim and lower-case an address; raise ValidationError if it is not one."""
    cleaned = email.strip().lower()
    local, sep, domain = cleaned.partition("@")
    if not sep or not local or "." not in domain or " " in cleaned:
        raise ValidationError(f"not an email address: {email!r}", email=email)
    return cleaned


def pending_invitations(account: Account, now: datetime) -> list[Invitation]:
    """Invitations that are neither accepted nor expired."""
    return [inv for inv in account.invitations.values() if inv.is_pending(now)]


def get_invitation(account: Account, invitation_id: str) -> Invitation:
    """Return the invitation or raise NotFoundError."""
    try:
        return account.invitations[invitation_id]
    except KeyError:
        raise NotFoundError(f"invitation {invitation_id} not found") from None


def invite_batch(
    account: Account, actor_id: str, emails: Iterable[str], role: Role,
    clock: Clock, ids: IdGenerator,
) -> list[Invitation]:
    """Create one invitation per address (1 to 50) and return them.

    Duplicate addresses inside the batch are sent once.
    """
    require_editable(account)
    permissions.require(account.member(actor_id).role, permissions.MEMBERS_MANAGE)
    if role is Role.OWNER:
        raise ValidationError("nobody can be invited as Owner; use an ownership transfer")
    raw = list(emails)
    if not raw:
        raise ValidationError("enter at least one email address")
    if len(raw) > MAX_INVITATIONS_PER_BATCH:
        raise ValidationError(
            f"a batch holds at most {MAX_INVITATIONS_PER_BATCH} invitations",
            maximum=MAX_INVITATIONS_PER_BATCH, received=len(raw),
        )
    addresses = list(dict.fromkeys(normalize_email(e) for e in raw))

    now = clock.now()
    pending = pending_invitations(account, now)
    pending_emails = {inv.email for inv in pending}
    for address in addresses:
        if account.find_member_by_email(address) is not None:
            raise ConflictError(f"{address} is already a member", email=address)
        if address in pending_emails:
            raise ConflictError(f"{address} already has a pending invitation", email=address)

    if role is Role.GUEST:
        reserved = sum(1 for inv in pending if inv.role is Role.GUEST)
        members.check_guest_capacity(account, extra=len(addresses), reserved=reserved)
    else:
        reserved = sum(1 for inv in pending if inv.role is not Role.GUEST)
        members.check_member_capacity(account, extra=len(addresses), reserved=reserved)

    created = []
    for address in addresses:
        invitation = Invitation(
            id=ids.new("inv"), account_id=account.id, email=address, role=role,
            invited_by=actor_id, created_at=now,
            expires_at=now + timedelta(days=INVITATION_TTL_DAYS), last_sent_at=now,
        )
        account.invitations[invitation.id] = invitation
        created.append(invitation)
    return created


def resend(account: Account, actor_id: str, invitation_id: str, clock: Clock) -> Invitation:
    """Resend an invitation and restart its 7-day window."""
    require_editable(account)
    permissions.require(account.member(actor_id).role, permissions.MEMBERS_MANAGE)
    invitation = get_invitation(account, invitation_id)
    if invitation.accepted_at is not None:
        raise ConflictError("this invitation was already accepted")
    now = clock.now()
    invitation.last_sent_at = now
    invitation.expires_at = now + timedelta(days=INVITATION_TTL_DAYS)
    invitation.resend_count += 1
    return invitation


def accept(account: Account, invitation_id: str, user_id: str, clock: Clock) -> Member:
    """Accept an invitation: the invitee joins with the invited role."""
    invitation = get_invitation(account, invitation_id)
    now = clock.now()
    if invitation.accepted_at is not None:
        raise ConflictError("this invitation was already accepted")
    if invitation.is_expired(now):
        raise ConflictError(
            f"this invitation expired after {INVITATION_TTL_DAYS} days; ask for a resend",
            expired_at=invitation.expires_at.isoformat(),
        )
    member = members.add_member(
        account, user_id, invitation.email, invitation.role, clock,
        invited_by=invitation.invited_by,
    )
    invitation.accepted_at = now
    return member
