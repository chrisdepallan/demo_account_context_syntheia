"""Password rules: 12 to 128 characters, breached list, email, last 5, reset links."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.auth import passwords
from acme_cloud.auth.passwords import (
    PasswordResetManager, hash_password, is_password_expired, set_password,
    validate_expiry_days, validate_password, verify_password,
)
from acme_cloud.common.errors import ValidationError

EMAIL = "dana@example.com"


def make_password(length: int) -> str:
    """A password of exactly ``length`` characters that breaks no other rule."""
    return ("Zq7!mK2#" * 20)[:length]


def test_constants_match_the_facts_sheet():
    assert passwords.PASSWORD_MIN_LENGTH == 12
    assert passwords.PASSWORD_MAX_LENGTH == 128
    assert passwords.PASSWORD_HISTORY_SIZE == 5
    assert passwords.RESET_TOKEN_TTL_MINUTES == 60
    assert passwords.PASSWORD_EXPIRY_CHOICES_DAYS == (30, 60, 90)


@pytest.mark.parametrize("length, accepted", [(11, False), (12, True), (128, True), (129, False)])
def test_password_length_must_be_12_to_128_characters(length, accepted):
    if accepted:
        validate_password(make_password(length), EMAIL)
    else:
        with pytest.raises(ValidationError) as error:
            validate_password(make_password(length), EMAIL)
        assert error.value.code == "ERR_VALIDATION"


@pytest.mark.parametrize("candidate", ["password1234", "Password1234", "CHANGEME1234"])
def test_breached_passwords_are_rejected_in_any_case(candidate):
    with pytest.raises(ValidationError) as error:
        validate_password(candidate, EMAIL)
    assert error.value.details["rule"] == "breached"


def test_password_must_not_contain_the_email_address():
    with pytest.raises(ValidationError) as error:
        validate_password("xx-Dana@Example.com-yy", EMAIL)
    assert error.value.details["rule"] == "contains_email"


def test_hash_is_salted_and_never_holds_the_plain_password():
    first = hash_password("a-long-enough-password")
    second = hash_password("a-long-enough-password")
    assert first.salt != second.salt and first.digest != second.digest
    assert "a-long-enough-password" not in repr(first)
    assert verify_password("a-long-enough-password", first)
    assert not verify_password("a-long-enough-passw0rd", first)


def test_new_password_must_not_match_any_of_the_last_5(clock):
    record = None
    for number in range(1, 6):
        record = set_password(record, f"history-password-{number}", EMAIL, clock.now())
    assert len(record.history) == 5

    # Password 1 is the oldest of the last five: still blocked.
    with pytest.raises(ValidationError) as error:
        set_password(record, "history-password-1", EMAIL, clock.now())
    assert error.value.details["rule"] == "reused"

    # After a sixth password, password 1 has left the history and is allowed.
    record = set_password(record, "history-password-6", EMAIL, clock.now())
    record = set_password(record, "history-password-1", EMAIL, clock.now())
    assert len(record.history) == 5


@pytest.mark.parametrize("minutes, accepted", [(59, True), (60, False), (61, False)])
def test_reset_link_is_valid_for_60_minutes(clock, minutes, accepted):
    manager = PasswordResetManager(clock)
    token = manager.issue("usr_TEST0001")
    clock.advance(minutes=minutes)
    if accepted:
        assert manager.redeem(token) == "usr_TEST0001"
    else:
        with pytest.raises(ValidationError) as error:
            manager.redeem(token)
        assert error.value.details["reason"] == "expired"


def test_reset_link_works_only_once(clock):
    manager = PasswordResetManager(clock)
    token = manager.issue("usr_TEST0001")
    manager.redeem(token)
    with pytest.raises(ValidationError) as error:
        manager.redeem(token)
    assert error.value.details["reason"] == "used"


def test_unknown_reset_token_is_rejected(clock):
    with pytest.raises(ValidationError):
        PasswordResetManager(clock).redeem("not-a-real-token")


@pytest.mark.parametrize("days", [None, 30, 60, 90])
def test_password_expiry_policy_accepts_off_30_60_90(days):
    validate_expiry_days(days)


@pytest.mark.parametrize("days", [0, 45, 120])
def test_password_expiry_policy_rejects_other_values(days):
    with pytest.raises(ValidationError):
        validate_expiry_days(days)


def test_password_expires_only_when_the_policy_is_on(clock):
    record = set_password(None, "a-long-enough-password", EMAIL, clock.now())
    later = clock.now() + timedelta(days=400)
    assert not is_password_expired(record, None, later)  # off by default
    assert not is_password_expired(record, 30, clock.now() + timedelta(days=29))
    assert is_password_expired(record, 30, clock.now() + timedelta(days=30))
