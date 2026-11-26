"""SSO: Business+ only, domain verification, test then enable, Enforce SSO, 3-minute skew."""

from __future__ import annotations

from datetime import timedelta

import pytest

from acme_cloud.auth import sso
from acme_cloud.auth.sso import (
    SamlAssertion, SsoProtocol, SsoService, SsoStatus, acs_url, certificate_fingerprint,
    entity_id,
)
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    ConflictError, PlanRequiredError, UnauthenticatedError, ValidationError,
)
from acme_cloud.common.ids import is_valid_id

WS = "ws_TEST01"
OLD_CERT = "-----BEGIN CERTIFICATE-----\nSAMPLE-OLD\n-----END CERTIFICATE-----"
NEW_CERT = "-----BEGIN CERTIFICATE-----\nSAMPLE-NEW\n-----END CERTIFICATE-----"


def make_assertion(clock, email="dana@example.com", cert=OLD_CERT, starts_in=timedelta(0),
                   ends_in=timedelta(minutes=5)) -> SamlAssertion:
    now = clock.now()
    return SamlAssertion(email, now + starts_in, now + ends_in, certificate_fingerprint(cert))


def make_connection(service: SsoService, plan: Plan = Plan.BUSINESS,
                    protocol: SsoProtocol = SsoProtocol.SAML):
    return service.create_connection(WS, plan, protocol, "https://idp.example.com/sso",
                                     OLD_CERT, "example.com")


def enabled_service(clock, ids, audit=None) -> SsoService:
    service = SsoService(clock, ids, audit)
    connection = make_connection(service)
    service.verify_domain(WS, [connection.dns_txt_record])
    service.test_connection(WS, make_assertion(clock))
    service.enable(WS, "usr_OWNER001", "acc_TEST0001")
    return service


def test_acs_url_entity_id_and_nameid_format():
    assert acs_url(WS) == "https://auth.acme-cloud.example/saml/acs/ws_TEST01"
    assert entity_id(WS) == "https://auth.acme-cloud.example/saml/ws_TEST01"
    assert sso.NAMEID_FORMAT == "emailAddress"
    assert sso.SAML_CLOCK_SKEW == timedelta(minutes=3)


@pytest.mark.parametrize("plan, allowed", [
    (Plan.FREE, False), (Plan.STARTER, False), (Plan.PRO, False),
    (Plan.BUSINESS, True), (Plan.ENTERPRISE, True),
])
def test_sso_needs_business_or_enterprise(clock, ids, plan, allowed):
    service = SsoService(clock, ids)
    if allowed:
        connection = make_connection(service, plan, SsoProtocol.OIDC)
        assert is_valid_id(connection.id, "sso")
        assert connection.status is SsoStatus.DRAFT
    else:
        with pytest.raises(PlanRequiredError):
            make_connection(service, plan)


def test_a_workspace_has_one_connection(clock, ids):
    service = SsoService(clock, ids)
    make_connection(service)
    with pytest.raises(ConflictError):
        make_connection(service)


def test_domain_is_verified_with_the_acme_verify_txt_record(clock, ids):
    service = SsoService(clock, ids)
    connection = make_connection(service)
    assert connection.dns_txt_record == f"acme-verify={connection.verification_token}"
    with pytest.raises(ValidationError):
        service.verify_domain(WS, ["v=spf1 -all", "acme-verify=wrong-token"])
    assert not connection.domain_verified
    service.verify_domain(WS, ["v=spf1 -all", connection.dns_txt_record])
    assert connection.domain_verified


def test_enable_needs_a_verified_domain_and_a_passed_test(clock, ids, audit):
    service = SsoService(clock, ids, audit)
    connection = make_connection(service)
    with pytest.raises(ConflictError, match="Verify the email domain"):
        service.enable(WS, "usr_OWNER001", "acc_TEST0001")
    service.verify_domain(WS, [connection.dns_txt_record])
    with pytest.raises(ConflictError, match="Test the connection"):
        service.enable(WS, "usr_OWNER001", "acc_TEST0001")
    service.test_connection(WS, make_assertion(clock))
    assert service.enable(WS, "usr_OWNER001", "acc_TEST0001").status is SsoStatus.ENABLED
    assert audit.types() == ["sso.enabled"]


def test_enforce_needs_an_enabled_connection(clock, ids, audit):
    service = SsoService(clock, ids, audit)
    make_connection(service)
    with pytest.raises(ConflictError):
        service.enforce(WS, "usr_OWNER001", "acc_TEST0001")
    service = enabled_service(clock, ids, audit)
    assert service.enforce(WS, "usr_OWNER001", "acc_TEST0001").enforced
    assert audit.types()[-1] == "sso.enforced"


@pytest.mark.parametrize("email, role, password_allowed", [
    ("member@example.com", Role.MEMBER, False),
    ("admin@example.com", Role.ADMIN, False),
    ("owner@example.com", Role.OWNER, True),          # break-glass
    ("guest@partner.example.org", Role.GUEST, True),  # not on the verified domain
])
def test_enforce_sso_disables_password_login_for_the_verified_domain_except_the_owner(
        clock, ids, email, role, password_allowed):
    service = enabled_service(clock, ids)
    assert service.password_login_allowed(WS, email, role)  # enabled but not enforced
    service.enforce(WS, "usr_OWNER001", "acc_TEST0001")
    assert service.password_login_allowed(WS, email, role) is password_allowed


@pytest.mark.parametrize("drift, accepted", [
    (timedelta(minutes=2, seconds=59), True),
    (timedelta(minutes=3), True),
    (timedelta(minutes=3, seconds=1), False),
    (timedelta(minutes=4), False),   # the drift in INC-2026-003
])
def test_assertions_may_be_up_to_3_minutes_ahead_of_our_clock(clock, ids, drift, accepted):
    service = enabled_service(clock, ids)
    assertion = make_assertion(clock, starts_in=drift, ends_in=drift + timedelta(minutes=5))
    if accepted:
        assert service.validate_assertion(WS, assertion) == "dana@example.com"
    else:
        with pytest.raises(UnauthenticatedError, match="SAML response signature invalid") as error:
            service.validate_assertion(WS, assertion)
        assert error.value.details["reason"] == "clock_skew"


@pytest.mark.parametrize("expired_for, accepted", [
    (timedelta(minutes=2, seconds=59), True), (timedelta(minutes=3), False),
])
def test_expired_assertions_get_the_same_3_minute_allowance(clock, ids, expired_for, accepted):
    service = enabled_service(clock, ids)
    assertion = make_assertion(clock, starts_in=-timedelta(minutes=10), ends_in=-expired_for)
    if accepted:
        service.validate_assertion(WS, assertion)
    else:
        with pytest.raises(UnauthenticatedError):
            service.validate_assertion(WS, assertion)


def test_certificate_rotation_fails_until_the_new_certificate_is_uploaded(clock, ids):
    service = enabled_service(clock, ids)
    rotated = make_assertion(clock, cert=NEW_CERT)
    with pytest.raises(UnauthenticatedError, match="SAML response signature invalid") as error:
        service.validate_assertion(WS, rotated)
    assert error.value.details["reason"] == "certificate_mismatch"
    service.upload_certificate(WS, NEW_CERT)
    assert service.validate_assertion(WS, rotated) == "dana@example.com"


def test_assertion_for_another_domain_is_rejected(clock, ids):
    service = enabled_service(clock, ids)
    with pytest.raises(UnauthenticatedError):
        service.validate_assertion(WS, make_assertion(clock, email="eve@other.example.net"))
