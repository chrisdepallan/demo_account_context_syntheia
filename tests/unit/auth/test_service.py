"""AuthService.login: password, lockout, MFA, Enforce SSO, and password reset."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.auth.mfa import MfaMethod, totp_code
from acme_cloud.auth.policies import SecurityPolicy
from acme_cloud.auth.service import AuthService
from acme_cloud.auth.sso import SamlAssertion, SsoProtocol, certificate_fingerprint
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    LockedOutError, PermissionDeniedError, UnauthenticatedError, ValidationError,
)

WS, ACCOUNT = "ws_TEST01", "acc_TEST0001"
PASSWORD = "first-good-password"
CERT = "SAMPLE-CERTIFICATE"


@pytest.fixture
def service(clock, ids, notifier, audit) -> AuthService:
    svc = AuthService(clock, ids, notifier=notifier, audit=audit)
    svc.configure_workspace(WS, Plan.BUSINESS)
    for name, role in [("owner", Role.OWNER), ("admin", Role.ADMIN), ("member", Role.MEMBER)]:
        svc.register_user(f"{name}@example.com", PASSWORD, role, ACCOUNT, WS)
    svc.register_user("guest@partner.example.org", PASSWORD, Role.GUEST, ACCOUNT, WS)
    return svc


def enroll_totp(service: AuthService, email: str) -> tuple[str, list[str]]:
    user = service.get_user(email)
    enrollment, codes = service.mfa.enroll(user.id, MfaMethod.TOTP, Plan.BUSINESS, user.role)
    return enrollment.credential, codes


def enforce_sso(service: AuthService, clock) -> SamlAssertion:
    connection = service.sso.create_connection(
        WS, Plan.BUSINESS, SsoProtocol.SAML, "https://idp.example.com/sso", CERT, "example.com")
    assertion = SamlAssertion("member@example.com", clock.now(),
                              clock.now() + timedelta(minutes=5), certificate_fingerprint(CERT))
    service.sso.verify_domain(WS, [connection.dns_txt_record])
    service.sso.test_connection(WS, assertion)
    service.sso.enable(WS, "usr_OWNER001", ACCOUNT)
    service.sso.enforce(WS, "usr_OWNER001", ACCOUNT)
    return assertion


def test_login_with_the_right_password_starts_a_session(service, audit):
    result = service.login("Member@Example.com", PASSWORD)
    assert result.user.email == "member@example.com"
    assert service.sessions.is_active(result.session)
    assert audit.types() == ["login.succeeded"]


def test_wrong_password_and_unknown_email_give_the_same_error(service, audit):
    with pytest.raises(UnauthenticatedError) as wrong:
        service.login("member@example.com", "not-the-password")
    with pytest.raises(UnauthenticatedError) as unknown:
        service.login("nobody@example.com", PASSWORD)
    assert wrong.value.message == unknown.value.message == "Invalid email or password"
    assert audit.types() == ["login.failed"]


def test_five_wrong_passwords_lock_login_even_for_the_right_password(service, clock, audit):
    for _ in range(4):
        with pytest.raises(UnauthenticatedError):
            service.login("member@example.com", "not-the-password")
    service.login("member@example.com", PASSWORD)  # four failures: still allowed

    with pytest.raises(UnauthenticatedError):
        service.login("member@example.com", "not-the-password")
    with pytest.raises(LockedOutError):
        service.login("member@example.com", PASSWORD)
    assert "login.locked" in audit.types()

    clock.advance(minutes=15)
    assert service.login("member@example.com", PASSWORD).session is not None


def test_password_reset_unlocks_signs_out_sessions_and_is_single_use(service, notifier, audit):
    old_session = service.login("member@example.com", PASSWORD).session
    for _ in range(5):
        with pytest.raises(UnauthenticatedError):
            service.login("member@example.com", "not-the-password")

    token = service.request_password_reset("member@example.com")
    assert notifier.templates() == ["password_reset"]
    service.reset_password(token, "second-good-password")

    assert not service.sessions.is_active(old_session)
    assert service.login("member@example.com", "second-good-password")  # unlocked at once
    assert "password.reset" in audit.types()
    with pytest.raises(ValidationError):
        service.reset_password(token, "third-good-password")


def test_reset_token_survives_a_rejected_new_password(service):
    token = service.request_password_reset("member@example.com")
    with pytest.raises(ValidationError):
        service.reset_password(token, "too-short")
    with pytest.raises(ValidationError):
        service.reset_password(token, PASSWORD)  # matches one of the last 5
    service.reset_password(token, "second-good-password")


def test_reset_request_for_an_unknown_email_sends_nothing(service, notifier):
    assert service.request_password_reset("nobody@example.com") is None
    assert notifier.sent == []


def test_enrolled_user_needs_a_totp_or_backup_code(service, clock):
    secret, backup_codes = enroll_totp(service, "member@example.com")
    with pytest.raises(UnauthenticatedError) as error:
        service.login("member@example.com", PASSWORD)
    assert error.value.details["mfa_required"] is True
    with pytest.raises(UnauthenticatedError):
        service.login("member@example.com", PASSWORD, "000000x")

    assert service.login("member@example.com", PASSWORD, totp_code(secret, clock.now()))
    assert service.login("member@example.com", PASSWORD, backup_codes[0])
    with pytest.raises(UnauthenticatedError):
        service.login("member@example.com", PASSWORD, backup_codes[0])  # single use


def test_enforce_sso_blocks_password_login_for_the_verified_domain(service, clock):
    assertion = enforce_sso(service, clock)
    for email in ("member@example.com", "admin@example.com"):
        with pytest.raises(PermissionDeniedError) as error:
            service.login(email, PASSWORD)
        assert error.value.details["sso_required"] is True
    assert service.login("guest@partner.example.org", PASSWORD)  # other domain
    assert service.login_with_sso(WS, assertion).user.email == "member@example.com"


def test_owner_break_glass_login_needs_password_and_mfa(service, clock):
    enforce_sso(service, clock)
    with pytest.raises(PermissionDeniedError) as error:
        service.login("owner@example.com", PASSWORD)  # no MFA set up
    assert error.value.details["mfa_enrollment_required"] is True

    secret, _ = enroll_totp(service, "owner@example.com")
    with pytest.raises(UnauthenticatedError):
        service.login("owner@example.com", PASSWORD)  # password alone
    assert service.login("owner@example.com", PASSWORD, totp_code(secret, clock.now()))


def test_require_mfa_gives_7_days_from_the_next_login(service, clock):
    service.configure_workspace(WS, Plan.BUSINESS, SecurityPolicy(require_mfa=True))
    clock.advance(days=20)  # the policy was on for a while; the grace starts at login
    first = service.login("member@example.com", PASSWORD)
    assert first.mfa_setup_deadline == clock.now() + timedelta(days=7)

    clock.advance(days=6)
    assert service.login("member@example.com", PASSWORD).mfa_setup_deadline == first.mfa_setup_deadline
    clock.advance(days=1)
    with pytest.raises(PermissionDeniedError):
        service.login("member@example.com", PASSWORD)


def test_password_expiry_policy_flags_an_old_password(service, clock):
    service.configure_workspace(WS, Plan.BUSINESS, SecurityPolicy(password_expiry_days=30))
    clock.advance(days=29)
    assert service.login("member@example.com", PASSWORD).password_expired is False
    clock.advance(days=1)
    assert service.login("member@example.com", PASSWORD).password_expired is True
