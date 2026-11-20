# Settings → Security

Owners and Admins see this page. Personal security for every user is under **Profile → Security** (see `login-and-profile.md`).

## How do I set up SAML SSO?

Business and Enterprise only.

1. Go to **Settings → Security → SSO → Add SAML connection**.
2. Copy these values into the identity provider:
   - ACS URL: `https://auth.acme-cloud.example/saml/acs/{workspace_id}`
   - Entity ID: `https://auth.acme-cloud.example/saml/{workspace_id}`
   - NameID format: `emailAddress`
3. Upload the provider's metadata XML, or paste its SSO URL and X.509 certificate.
4. Verify the email domain by adding the DNS TXT record shown on screen.
5. Select **Test connection**, then **Enable**.

Any SAML 2.0 or OIDC provider works. Guides exist for Okta, Microsoft Entra ID, Google Workspace, OneLogin and JumpCloud.

## How do I force everyone to use SSO?

After SSO is enabled and the domain verified, turn on **Enforce SSO**. Password login is then disabled for everyone on the verified domain except the Owner, who keeps password + MFA as a break-glass login.

## How do I fix "SAML response signature invalid"?

The identity provider rotated its certificate. Upload the new certificate in **Settings → Security → SSO**.

## How do I require MFA for everyone?

Turn on **Settings → Security → Require MFA** (Pro and above). Users without MFA must set it up at their next login, with a **7-day** grace period.

## What other security policies can I set?

- **Password expiry** – off by default; can be set to 30, 60 or 90 days.
- **Web session length** – Business and Enterprise can shorten it to between 1 hour and 14 days.
- **Require key expiry** – blocks API keys set to never expire (see `settings-api-keys.md`).

Source: `services/auth/docs/sso.md`, `services/auth/docs/passwords-and-mfa.md` in `demo_account_context`.

Last reviewed: 2026-11-20
