"""Single sign-on (SAML 2.0 and OIDC) connections.

Business rules:

- SSO is available on **Business and Enterprise** only. One connection
  per workspace, with an ID such as ``sso_7Q3W9E``.
- Values copied into the identity provider: ACS URL
  ``https://auth.acme-cloud.example/saml/acs/{workspace_id}``, Entity ID
  ``https://auth.acme-cloud.example/saml/{workspace_id}``, NameID format
  ``emailAddress``.
- The email domain must be verified with a DNS TXT record
  ``acme-verify=<token>``. Setup order: verify domain, **Test
  connection**, then **Enable**.
- **Enforce SSO** disables password login for everyone on the verified
  domain except the Owner, who keeps password + MFA as a break-glass login.
- SAML assertions may be up to **3 minutes** off our clock. A larger
  drift is rejected (INC-2026-003: two auth nodes drifted 4 minutes and
  38 workspaces could not log in).
- When the identity provider rotates its certificate, logins fail with
  "SAML response signature invalid" until the new certificate is
  uploaded. The signature check is modelled as a certificate fingerprint
  match.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from acme_cloud.accounts.plans import require_feature
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    ConflictError, NotFoundError, UnauthenticatedError, ValidationError,
)
from acme_cloud.common.ids import IdGenerator

AUTH_BASE_URL = "https://auth.acme-cloud.example"
NAMEID_FORMAT = "emailAddress"
DNS_TXT_PREFIX = "acme-verify="
#: Allowed clock skew on SAML assertions (see INC-2026-003).
SAML_CLOCK_SKEW = timedelta(minutes=3)
SAML_SIGNATURE_INVALID = "SAML response signature invalid"


class SsoProtocol(str, Enum):
    SAML = "saml"
    OIDC = "oidc"


class SsoStatus(str, Enum):
    DRAFT = "draft"
    TESTED = "tested"
    ENABLED = "enabled"


def acs_url(workspace_id: str) -> str:
    """Assertion Consumer Service URL for a workspace."""
    return f"{AUTH_BASE_URL}/saml/acs/{workspace_id}"


def entity_id(workspace_id: str) -> str:
    """SAML Entity ID (audience) for a workspace."""
    return f"{AUTH_BASE_URL}/saml/{workspace_id}"


def certificate_fingerprint(certificate: str) -> str:
    """SHA-256 fingerprint of an X.509 certificate, ignoring whitespace."""
    return hashlib.sha256("".join(certificate.split()).encode("utf-8")).hexdigest()


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


@dataclass
class SsoConnection:
    id: str
    workspace_id: str
    protocol: SsoProtocol
    sso_url: str
    certificate_fingerprint: str
    domain: str
    verification_token: str
    domain_verified: bool = False
    status: SsoStatus = SsoStatus.DRAFT
    enforced: bool = False

    @property
    def dns_txt_record(self) -> str:
        """The TXT record the customer adds to their DNS: ``acme-verify=<token>``."""
        return f"{DNS_TXT_PREFIX}{self.verification_token}"


@dataclass(frozen=True)
class SamlAssertion:
    """The parts of an identity-provider response that this sample checks."""

    email: str
    not_before: datetime
    not_on_or_after: datetime
    #: Fingerprint of the certificate that signed the response.
    signing_fingerprint: str


class SsoService:
    """Creates, verifies, enables and enforces SSO connections."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None,
                 audit: object | None = None) -> None:
        self._clock = clock
        self._ids = ids or IdGenerator()
        self._audit = audit
        self._by_workspace: dict[str, SsoConnection] = {}

    def create_connection(self, workspace_id: str, plan: Plan, protocol: SsoProtocol,
                          sso_url: str, certificate: str, domain: str) -> SsoConnection:
        """Add a draft connection. Needs Business or Enterprise."""
        require_feature(plan, "sso")
        if workspace_id in self._by_workspace:
            raise ConflictError("Workspace already has an SSO connection")
        if not sso_url.startswith("https://"):
            raise ValidationError("SSO URL must use https")
        connection = SsoConnection(
            id=self._ids.new("sso"), workspace_id=workspace_id, protocol=protocol,
            sso_url=sso_url, certificate_fingerprint=certificate_fingerprint(certificate),
            domain=domain.lower(), verification_token=secrets.token_hex(16),
        )
        self._by_workspace[workspace_id] = connection
        return connection

    def get(self, workspace_id: str) -> SsoConnection:
        if workspace_id not in self._by_workspace:
            raise NotFoundError("Workspace has no SSO connection", workspace_id=workspace_id)
        return self._by_workspace[workspace_id]

    def connection_or_none(self, workspace_id: str) -> SsoConnection | None:
        return self._by_workspace.get(workspace_id)

    def verify_domain(self, workspace_id: str, txt_records: list[str]) -> SsoConnection:
        """Mark the domain verified when its DNS TXT records include our token."""
        connection = self.get(workspace_id)
        if connection.dns_txt_record not in [record.strip() for record in txt_records]:
            raise ValidationError("DNS TXT record not found", expected=connection.dns_txt_record)
        connection.domain_verified = True
        return connection

    def upload_certificate(self, workspace_id: str, certificate: str) -> SsoConnection:
        """Replace the stored certificate after the identity provider rotated it."""
        connection = self.get(workspace_id)
        connection.certificate_fingerprint = certificate_fingerprint(certificate)
        return connection

    def validate_assertion(self, workspace_id: str, assertion: SamlAssertion) -> str:
        """Check signature, time window and domain; return the user's email.

        Both a certificate mismatch and a clock drift above 3 minutes are
        reported as "SAML response signature invalid" (``details["reason"]``
        tells them apart for the runbook).
        """
        connection = self.get(workspace_id)
        if assertion.signing_fingerprint != connection.certificate_fingerprint:
            raise UnauthenticatedError(SAML_SIGNATURE_INVALID, reason="certificate_mismatch")
        now = self._clock.now()
        if (now < assertion.not_before - SAML_CLOCK_SKEW
                or now >= assertion.not_on_or_after + SAML_CLOCK_SKEW):
            raise UnauthenticatedError(SAML_SIGNATURE_INVALID, reason="clock_skew")
        if email_domain(assertion.email) != connection.domain:
            raise UnauthenticatedError("Email domain does not match the SSO connection",
                                       reason="domain_mismatch")
        return assertion.email.lower()

    def test_connection(self, workspace_id: str, assertion: SamlAssertion) -> SsoConnection:
        """Run **Test connection** with a sample response from the provider."""
        connection = self.get(workspace_id)
        self.validate_assertion(workspace_id, assertion)
        if connection.status is SsoStatus.DRAFT:
            connection.status = SsoStatus.TESTED
        return connection

    def enable(self, workspace_id: str, actor_id: str, account_id: str) -> SsoConnection:
        """Turn SSO on. The domain must be verified and the test must have passed."""
        connection = self.get(workspace_id)
        if not connection.domain_verified:
            raise ConflictError("Verify the email domain before enabling SSO")
        if connection.status is SsoStatus.DRAFT:
            raise ConflictError("Test the connection before enabling SSO")
        connection.status = SsoStatus.ENABLED
        if self._audit is not None:
            self._audit.record("sso.enabled", actor_id, account_id, workspace_id,
                               connection_id=connection.id, protocol=connection.protocol.value)
        return connection

    def enforce(self, workspace_id: str, actor_id: str, account_id: str) -> SsoConnection:
        """Turn on **Enforce SSO**. Needs an enabled connection with a verified domain."""
        connection = self.get(workspace_id)
        if connection.status is not SsoStatus.ENABLED or not connection.domain_verified:
            raise ConflictError("Enable SSO and verify the domain before enforcing it")
        connection.enforced = True
        if self._audit is not None:
            self._audit.record("sso.enforced", actor_id, account_id, workspace_id,
                               connection_id=connection.id, domain=connection.domain)
        return connection

    def password_login_allowed(self, workspace_id: str, email: str, role: Role) -> bool:
        """False when Enforce SSO blocks password login for this user.

        Blocked: everyone on the verified domain except the Owner
        (break-glass). Users on other domains, such as guests, keep
        password login.
        """
        connection = self._by_workspace.get(workspace_id)
        if connection is None or not connection.enforced:
            return True
        if role is Role.OWNER:
            return True
        return email_domain(email) != connection.domain
