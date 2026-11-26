"""Authentication: passwords, lockout, MFA, sessions, SSO and security policies.

Owned by the Identity team. The numbers used here (12 to 128 character
passwords, 5 failures in 15 minutes, 10 backup codes, 14-day web
sessions, 3-minute SAML clock skew and so on) come from
``docs/reference/constants-and-glossary.md``.
"""

from acme_cloud.auth.lockout import LockoutTracker
from acme_cloud.auth.mfa import MfaEnrollment, MfaManager, MfaMethod, available_methods
from acme_cloud.auth.passwords import (
    PasswordHash, PasswordRecord, PasswordResetManager, hash_password, set_password,
    validate_password, verify_password,
)
from acme_cloud.auth.policies import DEFAULT_POLICY, SecurityPolicy, update_policy, validate_policy
from acme_cloud.auth.service import AuthService, LoginResult, User
from acme_cloud.auth.sessions import Device, Session, SessionManager
from acme_cloud.auth.sso import (
    SamlAssertion, SsoConnection, SsoProtocol, SsoService, SsoStatus, acs_url, entity_id,
)

__all__ = [
    "AuthService", "DEFAULT_POLICY", "Device", "LockoutTracker", "LoginResult",
    "MfaEnrollment", "MfaManager", "MfaMethod", "PasswordHash", "PasswordRecord",
    "PasswordResetManager", "SamlAssertion", "SecurityPolicy", "Session", "SessionManager",
    "SsoConnection", "SsoProtocol", "SsoService", "SsoStatus", "User", "acs_url",
    "available_methods", "entity_id", "hash_password", "set_password", "update_policy",
    "validate_password", "validate_policy", "verify_password",
]
