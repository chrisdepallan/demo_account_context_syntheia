"""Dunning: what happens after a renewal or seat charge fails.

Timeline, counted in days from the first failed charge (ADR 0006):

- Day 0: the account becomes ``past_due``. Owner, Billing admins and billing
  contacts get the ``payment_failed`` email. Everything still works.
- Days 1, 3, 7 and 14: automatic retries (four retries). Each failed retry
  sends ``payment_failed`` again.
- Day 14: if the day-14 retry fails the account becomes ``read_only`` (users
  can log in but not edit) and ``account_read_only`` is sent.
- Day 44: the account is downgraded to Free and is ``active`` again;
  ``account_downgraded`` is sent. Members over the Free limit become guests.
- Whenever the balance is paid the account is ``active`` again and full
  access is restored within 5 minutes.

Processor outages (INC-2026-002): when the payment processor is down, a retry
gets the result ``unavailable``. That is not a decline. It is not counted as
a failure, sends no email and changes no state; the retry stays due and is
made again on the next run. An account is never set to ``read_only`` or
downgraded on the strength of an outage: the downgrade waits until the
pending retry has had a real answer.

``DunningProcess`` only decides. It returns a ``DunningAction`` (retry, new
account state, new plan, emails to send); the caller applies it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from acme_cloud.billing.models import ChargeOutcome
from acme_cloud.common.enums import AccountState, Plan
from acme_cloud.common.errors import ConflictError

#: Days after the first failure on which the charge is retried automatically.
DUNNING_RETRY_DAYS = (1, 3, 7, 14)

#: Day on which a still unpaid account becomes read_only.
READ_ONLY_DAY = 14

#: Day on which a still unpaid account is downgraded to Free (14 + 30).
DOWNGRADE_DAY = 44

#: Full access is restored within this many minutes after the balance is paid.
RESTORE_ACCESS_WITHIN_MINUTES = 5

#: Email template keys used by dunning.
EMAIL_PAYMENT_FAILED = "payment_failed"
EMAIL_ACCOUNT_READ_ONLY = "account_read_only"
EMAIL_ACCOUNT_DOWNGRADED = "account_downgraded"


@dataclass(frozen=True)
class DunningAction:
    """What the caller must do now. Empty fields mean "nothing"."""

    day: int
    retry: bool = False                    # attempt the charge, then call record_retry
    new_state: AccountState | None = None  # account state decision
    new_plan: Plan | None = None           # Plan.FREE on day 44
    emails: tuple[str, ...] = ()           # template keys to send
    counted_as_failure: bool = False
    finished: bool = False                 # dunning is over


@dataclass(frozen=True)
class DunningSchedule:
    """The fixed calendar of dunning: retry days, read-only day, downgrade day."""

    retry_days: tuple[int, ...] = DUNNING_RETRY_DAYS
    read_only_day: int = READ_ONLY_DAY
    downgrade_day: int = DOWNGRADE_DAY

    def is_retry_day(self, day: int) -> bool:
        return day in self.retry_days

    def next_retry_day(self, day: int) -> int | None:
        """First retry day after ``day``; None after day 14."""
        return next((d for d in self.retry_days if d > day), None)

    def expected_state(self, day: int) -> AccountState:
        """State on ``day`` when every retry is declined."""
        if day < self.read_only_day:
            return AccountState.PAST_DUE
        if day < self.downgrade_day:
            return AccountState.READ_ONLY
        return AccountState.ACTIVE  # downgraded to Free


DEFAULT_SCHEDULE = DunningSchedule()


class DunningProcess:
    """Dunning state for one unpaid invoice."""

    def __init__(self, started_at: datetime, schedule: DunningSchedule = DEFAULT_SCHEDULE) -> None:
        self.started_at = started_at
        self.schedule = schedule
        self.state = AccountState.PAST_DUE
        self.failed_attempts = 1   # the charge that started dunning
        self.outages = 0           # retries that hit a processor outage (not failures)
        self.finished = False
        self._answered: set[int] = set()

    def start(self) -> DunningAction:
        """Day 0: the account becomes past_due and ``payment_failed`` is sent."""
        return DunningAction(day=0, new_state=AccountState.PAST_DUE,
                             emails=(EMAIL_PAYMENT_FAILED,), counted_as_failure=True)

    def day_number(self, now: datetime) -> int:
        """Whole days since the first failed charge."""
        return (now - self.started_at).days

    def pending_retry_days(self, day: int) -> list[int]:
        """Retry days up to ``day`` that have no real answer yet."""
        return [d for d in self.schedule.retry_days if d <= day and d not in self._answered]

    def due(self, day: int) -> DunningAction:
        """What is due on ``day``: a retry, the day-44 downgrade, or nothing."""
        self._check_running()
        if self.pending_retry_days(day):
            return DunningAction(day=day, retry=True)
        if day >= self.schedule.downgrade_day:
            self.finished, self.state = True, AccountState.ACTIVE
            return DunningAction(day=day, new_state=AccountState.ACTIVE, new_plan=Plan.FREE,
                                 emails=(EMAIL_ACCOUNT_DOWNGRADED,), finished=True)
        return DunningAction(day=day)

    def record_retry(self, day: int, outcome: ChargeOutcome) -> DunningAction:
        """Record the result of a retry made on ``day`` and return the follow-up."""
        self._check_running()
        if outcome is ChargeOutcome.UNAVAILABLE:
            self.outages += 1
            return DunningAction(day=day, retry=True)  # still due; not a failure
        self._answered.update(d for d in self.schedule.retry_days if d <= day)
        if outcome is ChargeOutcome.SUCCEEDED:
            return self.payment_cleared(day)
        self.failed_attempts += 1
        emails, new_state = [EMAIL_PAYMENT_FAILED], None
        if day >= self.schedule.read_only_day and self.state is AccountState.PAST_DUE:
            self.state = new_state = AccountState.READ_ONLY
            emails.append(EMAIL_ACCOUNT_READ_ONLY)
        return DunningAction(day=day, new_state=new_state, emails=tuple(emails),
                             counted_as_failure=True)

    def payment_cleared(self, day: int = 0) -> DunningAction:
        """The balance was paid: the account is active again and dunning ends."""
        self._check_running()
        self.finished, self.state = True, AccountState.ACTIVE
        return DunningAction(day=day, new_state=AccountState.ACTIVE, finished=True)

    def _check_running(self) -> None:
        if self.finished:
            raise ConflictError("dunning has already finished for this invoice")
