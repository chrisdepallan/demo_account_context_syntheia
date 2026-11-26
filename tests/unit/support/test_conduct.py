"""Conduct rules: support never accepts secrets, never acts on email alone, never shares data."""

from __future__ import annotations

import pytest

from acme_cloud.common.errors import PermissionDeniedError
from acme_cloud.support import conduct
from acme_cloud.support.conduct import (
    REDACTED, may_share_data, redact, require_same_workspace,
    require_verification_beyond_email, screen_message,
)


def test_the_three_support_must_never_rules_are_listed():
    assert len(conduct.SUPPORT_MUST_NEVER) == 3
    text = " ".join(conduct.SUPPORT_MUST_NEVER).lower()
    for phrase in ("password", "full card number", "mfa code", "email alone", "same workspace"):
        assert phrase in text


@pytest.mark.parametrize("message, flag", [
    ("I can't log in, my password is sample-secret-value", "password"),
    ("Password: sample-secret-value", "password"),
    ("the passcode was sample-secret-value, please try it", "password"),
    ("My card number is 0000, can you check the charge?", "card_number"),
    ("Card no: 00 00", "card_number"),
    ("My MFA code is 000000", "mfa_code"),
    ("the verification code 000 000 just arrived", "mfa_code"),
    ("Here is a backup code: 00000000", "mfa_code"),
])
def test_messages_that_appear_to_contain_a_secret_are_flagged(message, flag):
    result = screen_message(message)
    assert result.flags == (flag,)
    assert not result.is_clean
    assert flag in result.agent_reminder


@pytest.mark.parametrize("message", [
    "My password is not working since this morning.",
    "The password is expired, how do I reset it?",
    "How do I change the card on file?",
    "Which card number format do invoices show? Only the last 4, I hope.",
    "I never received my verification code.",
    "The MFA code is rejected every time.",
    "Invoice INV-2026-000123 shows the wrong amount of 450 dollars.",
    "",
])
def test_ordinary_support_messages_are_clean(message):
    result = screen_message(message)
    assert result.is_clean
    assert result.flags == ()
    assert result.redacted_text == message
    assert result.agent_reminder is None


def test_secrets_are_removed_before_the_message_is_stored():
    result = screen_message("Hi, my password is sample-secret-value and my MFA code is 000000.")
    assert set(result.flags) == {"password", "mfa_code"}
    assert "sample-secret-value" not in result.redacted_text
    assert "000000" not in result.redacted_text
    assert result.redacted_text.count(REDACTED) == 2
    assert result.redacted_text.startswith("Hi, my password is ")


def test_redact_keeps_the_rest_of_the_message():
    assert redact("Card number: 0000 thanks") == f"Card number: {REDACTED} thanks"
    assert redact("Nothing secret here") == "Nothing secret here"


@pytest.mark.parametrize("action", ["mfa_reset", "owner_change"])
def test_mfa_reset_and_owner_change_are_never_based_on_email_alone(action):
    with pytest.raises(PermissionDeniedError):
        require_verification_beyond_email(action, ["email"])
    with pytest.raises(PermissionDeniedError):
        require_verification_beyond_email(action, [])
    require_verification_beyond_email(action, ["email", "officer_written_confirmation"])


def test_unknown_sensitive_action_is_a_programming_error():
    with pytest.raises(ValueError):
        require_verification_beyond_email("refund", ["email"])


@pytest.mark.parametrize("requester, data_owner, allowed", [
    ("ws_TEST01", "ws_TEST01", True),
    ("ws_TEST01", "ws_TEST02", False),
    ("", "ws_TEST01", False),
    ("", "", False),
])
def test_data_is_shared_only_inside_the_same_workspace(requester, data_owner, allowed):
    assert may_share_data(requester, data_owner) is allowed
    if allowed:
        require_same_workspace(requester, data_owner)
    else:
        with pytest.raises(PermissionDeniedError):
            require_same_workspace(requester, data_owner)
