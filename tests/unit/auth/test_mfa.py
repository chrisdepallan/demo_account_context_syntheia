"""MFA: methods by plan and role, RFC 6238 TOTP, backup codes, Require MFA grace period."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from acme_cloud.auth import mfa
from acme_cloud.auth.mfa import MfaManager, MfaMethod, available_methods, totp_code, verify_totp
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import NotFoundError, PermissionDeniedError, ValidationError

USER = "usr_TEST0001"
#: The shared secret of the RFC 6238 Appendix B test vectors, base32 encoded.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


@pytest.mark.parametrize("plan, role, sms_offered", [
    (Plan.FREE, Role.OWNER, True),
    (Plan.PRO, Role.ADMIN, True),
    (Plan.BUSINESS, Role.MEMBER, True),
    (Plan.BUSINESS, Role.BILLING_ADMIN, True),
    (Plan.BUSINESS, Role.ADMIN, False),
    (Plan.BUSINESS, Role.OWNER, False),
    (Plan.ENTERPRISE, Role.ADMIN, False),
    (Plan.ENTERPRISE, Role.OWNER, False),
])
def test_sms_is_hidden_for_admins_and_owners_on_business_and_enterprise(plan, role, sms_offered):
    methods = available_methods(plan, role)
    assert MfaMethod.TOTP in methods and MfaMethod.WEBAUTHN in methods
    assert (MfaMethod.SMS in methods) is sms_offered


@pytest.mark.parametrize("unix_time, expected", [
    (59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037"),
])
def test_totp_matches_the_rfc_6238_test_vectors(unix_time, expected):
    assert totp_code(RFC_SECRET, unix_time) == expected


def test_totp_accepts_one_step_of_drift_but_not_two():
    now = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
    assert verify_totp(RFC_SECRET, totp_code(RFC_SECRET, now), now)
    assert verify_totp(RFC_SECRET, totp_code(RFC_SECRET, now - timedelta(seconds=30)), now)
    assert not verify_totp(RFC_SECRET, totp_code(RFC_SECRET, now - timedelta(seconds=90)), now)


def test_enrolling_gives_10_backup_codes_stored_only_as_hashes(clock):
    manager = MfaManager(clock)
    enrollment, codes = manager.enroll(USER, MfaMethod.TOTP, Plan.PRO, Role.MEMBER)
    assert mfa.BACKUP_CODE_COUNT == 10
    assert len(codes) == 10 and len(set(codes)) == 10
    assert not set(codes) & enrollment.backup_code_hashes


def test_login_code_from_the_authenticator_app_is_accepted(clock):
    manager = MfaManager(clock)
    enrollment, _ = manager.enroll(USER, MfaMethod.TOTP, Plan.PRO, Role.MEMBER)
    assert manager.verify(USER, totp_code(enrollment.credential, clock.now()))
    assert not manager.verify(USER, "not-a-code")


def test_backup_code_works_only_once(clock):
    manager = MfaManager(clock)
    _, codes = manager.enroll(USER, MfaMethod.TOTP, Plan.PRO, Role.MEMBER)
    assert manager.verify(USER, codes[0])
    assert not manager.verify(USER, codes[0])
    assert manager.verify(USER, codes[1])


def test_generating_new_backup_codes_invalidates_the_old_ones(clock):
    manager = MfaManager(clock)
    _, old_codes = manager.enroll(USER, MfaMethod.TOTP, Plan.PRO, Role.MEMBER)
    new_codes = manager.regenerate_backup_codes(USER)
    assert len(new_codes) == 10
    assert not any(manager.verify(USER, code) for code in old_codes)
    assert manager.verify(USER, new_codes[0])


def test_admin_on_business_cannot_enroll_sms(clock):
    manager = MfaManager(clock)
    with pytest.raises(ValidationError):
        manager.enroll(USER, MfaMethod.SMS, Plan.BUSINESS, Role.ADMIN)
    manager.enroll(USER, MfaMethod.SMS, Plan.BUSINESS, Role.MEMBER)
    assert manager.is_enrolled(USER)


def test_security_key_is_verified_by_its_credential(clock):
    manager = MfaManager(clock)
    manager.enroll(USER, MfaMethod.WEBAUTHN, Plan.ENTERPRISE, Role.OWNER, credential="cred-abc")
    assert manager.verify(USER, "cred-abc")
    assert not manager.verify(USER, "cred-xyz")


@pytest.mark.parametrize("days_later, allowed", [(0, True), (6, True), (7, False), (8, False)])
def test_require_mfa_gives_a_7_day_grace_period_from_the_next_login(clock, days_later, allowed):
    manager = MfaManager(clock)
    deadline = manager.check_requirement(USER)  # the user's next login starts the grace period
    assert deadline == clock.now() + timedelta(days=7)
    clock.advance(days=days_later)
    if allowed:
        assert manager.check_requirement(USER) == deadline  # later logins do not extend it
    else:
        with pytest.raises(PermissionDeniedError) as error:
            manager.check_requirement(USER)
        assert error.value.details["mfa_enrollment_required"] is True


def test_enrolled_users_have_no_grace_deadline(clock):
    manager = MfaManager(clock)
    manager.check_requirement(USER)
    manager.enroll(USER, MfaMethod.TOTP, Plan.PRO, Role.MEMBER)
    clock.advance(days=30)
    assert manager.check_requirement(USER) is None


@pytest.mark.parametrize("actor_role, allowed", [
    (Role.OWNER, True), (Role.ADMIN, True), (Role.BILLING_ADMIN, False), (Role.MEMBER, False),
])
def test_only_owners_and_admins_can_reset_a_members_mfa(clock, audit, actor_role, allowed):
    manager = MfaManager(clock, audit)
    manager.enroll(USER, MfaMethod.TOTP, Plan.PRO, Role.MEMBER, account_id="acc_TEST0001")
    if allowed:
        manager.admin_reset(USER, "usr_ADMIN001", actor_role, "acc_TEST0001")
        assert not manager.is_enrolled(USER)
        assert audit.types() == ["mfa.enrolled", "mfa.reset"]
        assert audit.events[-1][4] == {"target_user_id": USER}
    else:
        with pytest.raises(PermissionDeniedError):
            manager.admin_reset(USER, "usr_OTHER001", actor_role)
        assert manager.is_enrolled(USER)


def test_resetting_a_user_without_mfa_is_not_found(clock):
    with pytest.raises(NotFoundError):
        MfaManager(clock).admin_reset(USER, "usr_ADMIN001", Role.ADMIN)
