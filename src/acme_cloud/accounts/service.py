"""``AccountService``: in-memory facade over the account rules.

What the service does, with the numbers that matter:

- **Sign-up**: a new account starts in ``trialing`` on **Pro for 14 days**
  with one seat; the person who signs up is the Owner.
- **Trial**: the Owner gets the ``trial_ending`` email **3 days** before the
  end. When the first charge succeeds the account becomes ``active``. When
  the trial ends with no payment method the account moves to **Free** and
  is ``active``.
- **Downgrade to Free** (trial end, cancellation, or dunning day 44): the
  plan becomes Free and members over the Free limit of **3** become guests.
  The Owner is kept first, then Admins, Billing admins and Members, longest
  membership first. Storage packs are dropped (paid plans only).
- **Close**: Owner only, after typing the account name. The Owner gets the
  ``account_closed`` email with the **30-day** restore link.
- **Restore**: Owner only, within 30 days, back to the previous state.
- **Purge**: on **day 31** after closure the account becomes ``deleted``
  and its data is removed for good.

Emails go through an optional ``notifier`` (``send(template_key, to,
**context)``) and audit events through an optional ``audit``
(``record(event_type, actor_id, account_id, workspace_id=None,
**metadata)``). Both are skipped when ``None``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable

from acme_cloud.accounts import invitations, members, ownership, permissions, state_machine
from acme_cloud.accounts.models import Account, Invitation, Member, OwnershipTransfer
from acme_cloud.accounts.plans import limits_for
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import TRIAL_DAYS, TRIAL_PLAN, AccountState, Plan, Role
from acme_cloud.common.errors import ConflictError, NotFoundError, ValidationError
from acme_cloud.common.ids import IdGenerator

#: The ``trial_ending`` email is sent this many days before the trial ends.
TRIAL_REMINDER_DAYS = 3
#: Actor recorded on audit events for automatic jobs.
SYSTEM_ACTOR = "system"
RESTORE_URL = "https://app.acme-cloud.example/restore/{account_id}"

_KEEP_ORDER = {Role.OWNER: 0, Role.ADMIN: 1, Role.BILLING_ADMIN: 2, Role.MEMBER: 3}


class AccountService:
    """Creates accounts and applies lifecycle, member and ownership rules."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None,
                 notifier: Any = None, audit: Any = None) -> None:
        self.clock = clock
        self.ids = ids or IdGenerator()
        self.notifier = notifier
        self.audit = audit
        self.accounts: dict[str, Account] = {}

    # -- helpers ---------------------------------------------------------
    def _notify(self, template_key: str, to: list[str], **context: Any) -> None:
        if self.notifier is not None and to:
            self.notifier.send(template_key, to, **context)

    def _audit(self, event_type: str, actor_id: str, account: Account, **metadata: Any) -> None:
        if self.audit is not None:
            self.audit.record(event_type, actor_id, account.id, None, **metadata)

    def get(self, account_id: str) -> Account:
        """Return the account or raise NotFoundError."""
        if account_id not in self.accounts:
            raise NotFoundError(f"account {account_id} not found", account_id=account_id)
        return self.accounts[account_id]

    # -- sign-up and trial -----------------------------------------------
    def create_account(self, name: str, owner_email: str) -> Account:
        """Create an account in ``trialing`` on Pro for 14 days, with its Owner."""
        if not name.strip():
            raise ValidationError("the account name is required")
        email = invitations.normalize_email(owner_email)
        now = self.clock.now()
        owner = Member(user_id=self.ids.new("usr"), email=email, role=Role.OWNER, joined_at=now)
        account = Account(
            id=self.ids.new("acc"), name=name.strip(), owner_id=owner.user_id,
            plan=TRIAL_PLAN, state=AccountState.TRIALING, created_at=now, seats=1,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS), state_changed_at=now,
            members={owner.user_id: owner},
        )
        self.accounts[account.id] = account
        return account

    def convert_trial(self, account_id: str, plan: Plan = TRIAL_PLAN) -> Account:
        """The first charge succeeded: ``trialing`` -> ``active`` on a paid plan."""
        account = self.get(account_id)
        if not plan.is_paid:
            raise ValidationError("a trial converts to a paid plan")
        state_machine.transition(account, AccountState.ACTIVE, self.clock)
        if plan is not account.plan:
            self._audit("plan.changed", account.owner_id, account,
                        old_plan=account.plan.value, new_plan=plan.value)
            account.plan = plan
        return account

    def end_trial(self, account_id: str) -> Account:
        """The 14 days are over with no payment method: move to Free, ``active``."""
        account = self.get(account_id)
        if account.state is not AccountState.TRIALING:
            raise ConflictError("the account is not in a trial", state=account.state.value)
        if self.clock.now() < account.trial_ends_at:
            raise ConflictError("the trial has not ended yet",
                                trial_ends_at=account.trial_ends_at.isoformat())
        self.downgrade_to_free(account_id, reason="trial_ended")
        return account

    def send_trial_reminders(self) -> list[str]:
        """Email ``trial_ending`` to Owners whose trial ends within 3 days (once each)."""
        now, sent = self.clock.now(), []
        for account in self.accounts.values():
            if account.state is not AccountState.TRIALING or account.trial_reminder_sent:
                continue
            if now < account.trial_ends_at <= now + timedelta(days=TRIAL_REMINDER_DAYS):
                self._notify("trial_ending", [account.owner.email], account_id=account.id,
                             trial_ends_at=account.trial_ends_at.isoformat())
                account.trial_reminder_sent = True
                sent.append(account.id)
        return sent

    def expire_trials(self) -> list[str]:
        """End every trial whose 14 days have passed. Returns the account IDs."""
        now = self.clock.now()
        due = [a.id for a in self.accounts.values()
               if a.state is AccountState.TRIALING and now >= a.trial_ends_at]
        for account_id in due:
            self.end_trial(account_id)
        return due

    def downgrade_to_free(self, account_id: str, actor_id: str = SYSTEM_ACTOR,
                          reason: str = "downgrade") -> list[Member]:
        """Move the account to Free; members over the limit of 3 become guests.

        Returns the members that were turned into guests. A ``trialing`` or
        ``read_only`` account becomes ``active``.
        """
        account = self.get(account_id)
        if not account.state.can_log_in:
            raise ConflictError("a closed or deleted account cannot change plan")
        if account.plan is Plan.FREE:
            raise ConflictError("the account is already on Free")
        was_read_only = account.state is AccountState.READ_ONLY
        recipients = account.emails_for_roles(Role.OWNER, Role.BILLING_ADMIN)
        seat_users = sorted((m for m in account.members.values() if m.uses_seat),
                            key=lambda m: (_KEEP_ORDER[m.role], m.joined_at))
        demoted = seat_users[limits_for(Plan.FREE).max_members:]
        for member in demoted:
            self._audit("member.role_changed", actor_id, account, user_id=member.user_id,
                        old_role=member.role.value, new_role=Role.GUEST.value)
            member.role = Role.GUEST
        self._audit("plan.changed", actor_id, account, old_plan=account.plan.value,
                    new_plan=Plan.FREE.value, reason=reason)
        account.plan = Plan.FREE
        account.seats = account.seat_member_count
        account.storage_packs = 0
        if account.state in (AccountState.TRIALING, AccountState.READ_ONLY):
            state_machine.transition(account, AccountState.ACTIVE, self.clock)
        if was_read_only:
            self._notify("account_downgraded", recipients, account_id=account.id)
        return demoted

    # -- close, restore, purge -------------------------------------------
    def close_account(self, account_id: str, actor_id: str, confirm_name: str) -> Account:
        """Owner closes the account after typing its name; restorable for 30 days."""
        account = self.get(account_id)
        permissions.require(account.member(actor_id).role, permissions.ACCOUNT_CLOSE)
        if confirm_name != account.name:
            raise ValidationError("type the account name exactly to confirm closing")
        state_machine.close(account, self.clock)
        self._audit("account.closed", actor_id, account)
        self._notify("account_closed", [account.owner.email], account_id=account.id,
                     restore_url=RESTORE_URL.format(account_id=account.id),
                     restore_days=state_machine.RESTORE_WINDOW_DAYS)
        return account

    def restore_account(self, account_id: str, actor_id: str) -> Account:
        """Owner restores a closed account to its previous state within 30 days."""
        account = self.get(account_id)
        permissions.require(account.member(actor_id).role, permissions.ACCOUNT_CLOSE)
        state_machine.restore(account, self.clock)
        self._audit("account.restored", actor_id, account)
        return account

    def purge_deleted(self) -> list[str]:
        """Day 31 after closure: mark accounts ``deleted`` and drop their data."""
        purged = []
        for account in self.accounts.values():
            if state_machine.delete_if_due(account, self.clock):
                account.invitations.clear()
                account.content_owners.clear()
                account.pending_transfer = None
                purged.append(account.id)
        return purged

    # -- members and ownership -------------------------------------------
    def invite_members(self, account_id: str, actor_id: str, emails: Iterable[str],
                       role: Role = Role.MEMBER) -> list[Invitation]:
        """Invite up to 50 people; each gets the ``invitation`` email."""
        account = self.get(account_id)
        created = invitations.invite_batch(account, actor_id, emails, role, self.clock, self.ids)
        for inv in created:
            self._audit("member.invited", actor_id, account, email=inv.email, role=role.value)
            self._notify("invitation", [inv.email], account_id=account.id,
                         invitation_id=inv.id, expires_at=inv.expires_at.isoformat())
        return created

    def resend_invitation(self, account_id: str, actor_id: str, invitation_id: str) -> Invitation:
        """Resend an invitation; it is valid for another 7 days."""
        account = self.get(account_id)
        inv = invitations.resend(account, actor_id, invitation_id, self.clock)
        self._notify("invitation", [inv.email], account_id=account.id,
                     invitation_id=inv.id, expires_at=inv.expires_at.isoformat())
        return inv

    def accept_invitation(self, account_id: str, invitation_id: str,
                          user_id: str | None = None) -> Member:
        """The invitee joins; a user ID is created for people new to Acme Cloud."""
        account = self.get(account_id)
        return invitations.accept(account, invitation_id, user_id or self.ids.new("usr"),
                                  self.clock)

    def remove_member(self, account_id: str, actor_id: str, user_id: str) -> members.RemovalResult:
        """Remove a member; content goes to the remover, the seat is freed."""
        account = self.get(account_id)
        result = members.remove_member(account, actor_id, user_id, self.clock)
        self._audit("member.removed", actor_id, account, user_id=user_id,
                    seats_freed=result.seats_freed)
        if result.seats_freed:
            self._audit("seats.changed", actor_id, account, seats=account.seats)
        return result

    def change_member_role(self, account_id: str, actor_id: str, user_id: str,
                           new_role: Role) -> members.RoleChange:
        """Change a member's role (never to or from Owner)."""
        account = self.get(account_id)
        change = members.change_role(account, actor_id, user_id, new_role)
        self._audit("member.role_changed", actor_id, account, user_id=user_id,
                    old_role=change.old_role.value, new_role=change.new_role.value)
        return change

    def request_ownership_transfer(self, account_id: str, actor_id: str,
                                   target_user_id: str) -> OwnershipTransfer:
        """Owner asks an Admin to take over; the Admin has 7 days to accept."""
        account = self.get(account_id)
        transfer = ownership.request_transfer(account, actor_id, target_user_id,
                                              self.clock, self.ids)
        self._audit("ownership.transfer_requested", actor_id, account, to_user_id=target_user_id)
        self._notify("ownership_transfer", [account.member(target_user_id).email],
                     account_id=account.id, expires_at=transfer.expires_at.isoformat())
        return transfer

    def accept_ownership_transfer(self, account_id: str, user_id: str) -> OwnershipTransfer:
        """The Admin accepts and becomes Owner; the previous Owner becomes Admin."""
        account = self.get(account_id)
        transfer = ownership.accept_transfer(account, user_id, self.clock)
        self._audit("ownership.transferred", user_id, account,
                    from_user_id=transfer.from_user_id, to_user_id=transfer.to_user_id)
        return transfer
