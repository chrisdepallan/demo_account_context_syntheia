"""Login service that combines passwords, lockout, MFA, SSO and sessions.

``AuthService.login`` runs these checks in order:

1. Unknown email -> ``ERR_UNAUTHENTICATED`` (same message as a wrong password).
2. Lockout -> ``ERR_LOCKED_OUT`` (5 failures in 15 minutes lock for 15
   minutes; 10 in 1 hour lock for 1 hour and email the user).
3. Enforce SSO -> password login is refused for the verified domain,
   except for the Owner (break-glass).
4. Password check. A failure is counted and audited (``login.failed``).
5. MFA. Enrolled users must give a code or a backup code. The Owner
   break-glass login always needs MFA. With the Require MFA policy,
   users without MFA get a 7-day grace period from this login.
6. A session is created (web 14 days, mobile 90 days of inactivity) and
   ``login.succeeded`` is audited.

Password reset: the link is valid 60 minutes and single use; redeeming
it signs out all sessions and clears the lockout.

Users, plans and policies are kept in memory; this is sample code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from acme_cloud.auth.lockout import LockoutTracker
from acme_cloud.auth.mfa import MfaManager
from acme_cloud.auth.passwords import (
    PasswordRecord, PasswordResetManager, is_password_expired, set_password, verify_password,
)
from acme_cloud.auth.policies import DEFAULT_POLICY, SecurityPolicy, validate_policy
from acme_cloud.auth.sessions import Device, Session, SessionManager
from acme_cloud.auth.sso import SamlAssertion, SsoService
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan, Role
from acme_cloud.common.errors import (
    ConflictError, NotFoundError, PermissionDeniedError, UnauthenticatedError,
)
from acme_cloud.common.ids import IdGenerator

INVALID_CREDENTIALS = "Invalid email or password"


@dataclass
class User:
    id: str
    email: str
    role: Role
    account_id: str
    workspace_id: str
    password: PasswordRecord


@dataclass(frozen=True)
class LoginResult:
    """Outcome of a successful login."""

    user: User
    session: Session
    #: Set while the user is inside the 7-day Require MFA grace period.
    mfa_setup_deadline: datetime | None = None
    #: True when the password expiry policy says the password must be changed.
    password_expired: bool = False


class AuthService:
    """In-memory authentication service for the sample."""

    def __init__(self, clock: Clock, ids: IdGenerator | None = None, *,
                 notifier: object | None = None, audit: object | None = None) -> None:
        self._clock = clock
        self._ids = ids or IdGenerator()
        self._notifier = notifier
        self._audit = audit
        self.lockout = LockoutTracker(clock, notifier, audit)
        self.mfa = MfaManager(clock, audit)
        self.sessions = SessionManager(clock, self._ids)
        self.sso = SsoService(clock, self._ids, audit)
        self.resets = PasswordResetManager(clock)
        self._users: dict[str, User] = {}          # by lower-case email
        self._plans: dict[str, Plan] = {}          # by workspace ID
        self._policies: dict[str, SecurityPolicy] = {}

    # -- setup -----------------------------------------------------------

    def configure_workspace(self, workspace_id: str, plan: Plan,
                            policy: SecurityPolicy = DEFAULT_POLICY) -> None:
        """Set the plan and security policy of a workspace (plan checks apply)."""
        validate_policy(policy, plan)
        self._plans[workspace_id] = plan
        self._policies[workspace_id] = policy

    def policy_for(self, workspace_id: str) -> SecurityPolicy:
        return self._policies.get(workspace_id, DEFAULT_POLICY)

    def register_user(self, email: str, password: str, role: Role, account_id: str,
                      workspace_id: str) -> User:
        """Create a user with a password that meets the password rules."""
        key = email.lower()
        if key in self._users:
            raise ConflictError("A user with this email already exists")
        record = set_password(None, password, email, self._clock.now())
        user = User(self._ids.new("usr"), key, role, account_id, workspace_id, record)
        self._users[key] = user
        return user

    def get_user(self, email: str) -> User:
        user = self._users.get(email.lower())
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _record(self, event: str, user: User, **metadata: object) -> None:
        if self._audit is not None:
            self._audit.record(event, user.id, user.account_id, user.workspace_id, **metadata)

    # -- login -----------------------------------------------------------

    def _fail(self, user: User, reason: str) -> None:
        self.lockout.record_failure(user.id, user.email, user.account_id, user.workspace_id)
        self._record("login.failed", user, reason=reason)

    def login(self, email: str, password: str, mfa_code: str | None = None,
              device: Device = Device.WEB) -> LoginResult:
        """Log in with email and password (plus MFA code when enrolled)."""
        user = self._users.get(email.lower())
        if user is None:
            raise UnauthenticatedError(INVALID_CREDENTIALS)
        self.lockout.check(user.id)

        policy = self.policy_for(user.workspace_id)
        sso = self.sso.connection_or_none(user.workspace_id)
        sso_enforced = sso is not None and sso.enforced
        if not self.sso.password_login_allowed(user.workspace_id, user.email, user.role):
            raise PermissionDeniedError("Your workspace requires single sign-on", sso_required=True)

        if not verify_password(password, user.password.current):
            self._fail(user, "bad_password")
            raise UnauthenticatedError(INVALID_CREDENTIALS)

        deadline = None
        if self.mfa.is_enrolled(user.id):
            if mfa_code is None:
                raise UnauthenticatedError("MFA code required", mfa_required=True)
            if not self.mfa.verify(user.id, mfa_code):
                self._fail(user, "bad_mfa_code")
                raise UnauthenticatedError("Invalid MFA code", mfa_required=True)
        elif sso_enforced and user.role is Role.OWNER:
            raise PermissionDeniedError(
                "Break-glass login needs password and MFA", mfa_enrollment_required=True)
        elif policy.require_mfa:
            deadline = self.mfa.check_requirement(user.id)

        session = self.sessions.create(user.id, device)
        self._record("login.succeeded", user, method="password", device=device.value)
        expired = is_password_expired(user.password, policy.password_expiry_days,
                                      self._clock.now())
        return LoginResult(user, session, deadline, expired)

    def login_with_sso(self, workspace_id: str, assertion: SamlAssertion,
                       device: Device = Device.WEB) -> LoginResult:
        """Log in with a response from the workspace's identity provider."""
        connection = self.sso.get(workspace_id)
        if connection.status.value != "enabled":
            raise UnauthenticatedError("SSO is not enabled for this workspace")
        email = self.sso.validate_assertion(workspace_id, assertion)
        user = self._users.get(email)
        if user is None or user.workspace_id != workspace_id:
            raise UnauthenticatedError("No user for this SSO identity")
        session = self.sessions.create(user.id, device)
        self._record("login.succeeded", user, method="sso", device=device.value)
        return LoginResult(user, session)

    # -- password reset --------------------------------------------------

    def request_password_reset(self, email: str) -> str | None:
        """Email a reset link (``password_reset``) and return the token.

        Returns ``None`` for an unknown email, without raising, so the
        form does not reveal which emails have accounts.
        """
        user = self._users.get(email.lower())
        if user is None:
            return None
        token = self.resets.issue(user.id)
        if self._notifier is not None:
            self._notifier.send("password_reset", [user.email], token=token, valid_minutes=60)
        return token

    def reset_password(self, token: str, new_password: str) -> User:
        """Set a new password with a reset token.

        The token is consumed only when the new password is accepted.
        Afterwards all sessions are signed out and the lockout is cleared.
        """
        user_id = self.resets.peek(token)
        user = next(u for u in self._users.values() if u.id == user_id)
        user.password = set_password(user.password, new_password, user.email, self._clock.now())
        self.resets.redeem(token)
        self.sessions.sign_out_all(user.id)
        self.lockout.reset(user.id)
        self._record("password.reset", user)
        return user
