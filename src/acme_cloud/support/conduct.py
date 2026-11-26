"""Support conduct rules: what support must never do.

Rules (from the internal admin console guide):

1. Never ask for or accept a customer's **password**, **full card
   number** or **MFA code**.
2. Never reset MFA or change the Owner **based on email alone**.
3. Never share one customer's data with another, unless both are in the
   **same workspace**.

``screen_message`` supports rule 1: it flags a customer message that
appears to contain a secret, and ``redact`` removes the secret before
the message is stored. Detection is by wording only (for example "my
password is ...", "card number: ...", "verification code 123456"); no
example secrets or card numbers are embedded in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from acme_cloud.common.errors import PermissionDeniedError

SUPPORT_MUST_NEVER = (
    "Ask for or accept a customer's password, full card number or MFA code.",
    "Reset MFA or change the Owner based on email alone.",
    "Share one customer's data with another unless they are in the same workspace.",
)

FLAG_PASSWORD = "password"
FLAG_CARD_NUMBER = "card_number"
FLAG_MFA_CODE = "mfa_code"

REDACTED = "[removed by support]"

#: Actions that need identity verification beyond an email message.
SENSITIVE_ACTIONS = ("mfa_reset", "owner_change")
EMAIL_EVIDENCE = "email"

# Each pattern has a "lead" group (kept) and a "secret" group (removed).
_PATTERNS: dict[str, re.Pattern[str]] = {
    FLAG_PASSWORD: re.compile(
        r"(?P<lead>\bpass(?:word|code|phrase)\s*(?:is|was|:|=)\s*)(?P<secret>\S+)", re.IGNORECASE),
    FLAG_CARD_NUMBER: re.compile(
        r"(?P<lead>\bcard\s*(?:number|no\.?|#)\s*(?:is|:|=)?\s*)(?P<secret>\d[\d \-]*\d|\d)",
        re.IGNORECASE),
    FLAG_MFA_CODE: re.compile(
        r"(?P<lead>\b(?:mfa|2fa|verification|authenticator|backup|security)\s*code\s*"
        r"(?:is|was|:|=)?\s*)(?P<secret>\d[\d \-]*\d)", re.IGNORECASE),
}


@dataclass(frozen=True)
class ScreenResult:
    """Outcome of screening one message."""

    flags: tuple[str, ...]
    #: The message with every detected secret replaced by ``REDACTED``.
    redacted_text: str

    @property
    def is_clean(self) -> bool:
        return not self.flags

    @property
    def agent_reminder(self) -> str | None:
        """Text shown to the agent when the customer sent a secret."""
        if self.is_clean:
            return None
        return ("The customer appears to have sent a secret (" + ", ".join(self.flags) + "). "
                "It was removed. Do not use it; tell the customer support never needs it.")


def redact(message: str) -> str:
    """Replace every detected secret in ``message`` with ``REDACTED``."""
    for pattern in _PATTERNS.values():
        message = pattern.sub(lambda match: match.group("lead") + REDACTED, message)
    return message


def screen_message(message: str) -> ScreenResult:
    """Flag a message that appears to contain a password, card number or MFA code."""
    flags = tuple(flag for flag, pattern in _PATTERNS.items() if pattern.search(message))
    return ScreenResult(flags=flags, redacted_text=redact(message) if flags else message)


def require_verification_beyond_email(action: str, evidence: Iterable[str]) -> None:
    """Refuse an MFA reset or Owner change that rests on email alone.

    ``evidence`` lists what the agent has, for example ``["email"]`` or
    ``["email", "officer_written_confirmation"]``. At least one item
    other than ``"email"`` is needed.
    """
    if action not in SENSITIVE_ACTIONS:
        raise ValueError(f"unknown sensitive action: {action}")
    if not set(evidence) - {EMAIL_EVIDENCE}:
        raise PermissionDeniedError(
            "Support never resets MFA or changes the Owner based on email alone",
            action=action)


def may_share_data(requester_workspace_id: str, data_workspace_id: str) -> bool:
    """True only when the requester belongs to the workspace that owns the data."""
    return bool(requester_workspace_id) and requester_workspace_id == data_workspace_id


def require_same_workspace(requester_workspace_id: str, data_workspace_id: str) -> None:
    """Raise PermissionDeniedError for a cross-customer data request."""
    if not may_share_data(requester_workspace_id, data_workspace_id):
        raise PermissionDeniedError(
            "Support never shares one customer's data with another customer")
