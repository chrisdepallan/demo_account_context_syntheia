# Login Page and Profile

## Where is the login page?

`https://app.acme-cloud.example/login`. Users can sign in with email and password (plus MFA if set up) or through SSO when their workspace has it enabled.

## How do I reset my password?

1. On the login page, select **Forgot password** and enter the account email.
2. Open the emailed reset link. It is valid for **60 minutes** and works once.
3. Set a new password. All other sessions are signed out.

Users who sign in only through SSO cannot reset their password in the dashboard; they reset it with their identity provider.

## What password does the form accept?

- **12 to 128 characters**.
- Not on known breached-password lists.
- Must not contain the user's email address.
- Must not match any of the last **5 passwords**.

## Why does the login page say my account is locked?

After **5 failed attempts within 15 minutes**, login is locked for **15 minutes**. After **10 failed attempts within an hour**, it is locked for **1 hour** and the user is emailed. Resetting the password unlocks it immediately.

## How do I set up MFA?

Go to **Profile → Security** and add a method:

- Authenticator app (TOTP), for example Google Authenticator, Microsoft Authenticator or 1Password
- Security key or passkey (FIDO2/WebAuthn), for example YubiKey
- SMS codes (hidden for Admins and Owners on Business and Enterprise)

After setup the screen shows **10 single-use backup codes**. Save them straight away.

## How do I get new backup codes?

**Profile → Security → generate new backup codes**. The old codes stop working at once.

## Why am I asked to set up MFA at login?

An Admin turned on **Settings → Security → Require MFA**. Users without MFA must set it up at their next login, with a **7-day** grace period.

## How long do I stay signed in?

Web sessions end after **14 days** of inactivity, mobile sessions after **90 days**. On Business and Enterprise, Admins can shorten the web limit to between 1 hour and 14 days.

Source: `services/auth/docs/passwords-and-mfa.md` in `demo_account_context`.

Last reviewed: 2026-11-20
