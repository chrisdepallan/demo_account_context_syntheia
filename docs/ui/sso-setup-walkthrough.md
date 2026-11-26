# SSO Setup Walkthrough

A step-by-step guide to single sign-on. The short version is in `settings-security.md`. SSO is on **Business and Enterprise** only, and only **Owners** and **Admins** can set it up.

## What do I need before I start?

- A **Business** or **Enterprise** plan. On other plans **Settings → Security → SSO** shows an upgrade notice (`ERR_PLAN_REQUIRED`).
- The **Owner** or **Admin** role in Acme Cloud.
- Administrator access to your identity provider (IdP).
- Access to the DNS settings of your email domain, to add one TXT record.
- The Owner must have a password and MFA set up. This is the break-glass login if SSO fails.
- Every user's email address in the IdP must match their Acme Cloud email address.

## Should I choose SAML or OIDC?

Both work and both give the same result. **SAML 2.0** has been available longest. **OIDC** was added in release **2026.8**. Use the one your IdP team prefers. A workspace has one active SSO connection; its ID looks like `sso_7Q3W9E`.

## How do I add a SAML connection?

1. Go to **Settings → Security → SSO → Add SAML connection**.
2. Copy these values into a new SAML application in your IdP:
   - ACS URL: `https://auth.acme-cloud.example/saml/acs/{workspace_id}`
   - Entity ID: `https://auth.acme-cloud.example/saml/{workspace_id}`
   - NameID format: `emailAddress`
3. In the IdP, set the NameID value to the user's email address and make sure the response is signed.
4. Back in Acme Cloud, upload the IdP's **metadata XML**, or paste its **SSO URL** and **X.509 certificate**.
5. Select **Save**. The connection is saved as a draft; nobody's login changes yet.

`{workspace_id}` is filled in on screen with your own ID, for example `ws_4H8P2L`.

## How do I add an OIDC connection?

1. Go to **Settings → Security → SSO → Add OIDC connection**.
2. In your IdP, create a web application with this redirect URI: `https://auth.acme-cloud.example/oidc/callback/{workspace_id}`.
3. Back in Acme Cloud, enter the **Issuer URL**, **Client ID** and **Client secret** from the IdP.
4. Leave the scopes as `openid email profile`. The `email` claim must hold the user's email address.
5. Select **Save**.

The client secret is never shown again after saving. To change it, enter a new one.

## How do I verify my email domain?

1. In **Settings → Security → SSO → Domains**, select **Add domain** and enter the domain, for example `example.com`.
2. Copy the TXT record shown on screen. It has the form `acme-verify=<token>`.
3. Add it as a TXT record on the root of the domain at your DNS host.
4. Return to the page and select **Verify domain**.

DNS changes can take up to **48 hours** to spread, though it is usually minutes. Leave the TXT record in place after verification. You can verify more than one domain.

## How do I test the connection?

Select **Test connection**. A new window opens your IdP's login. Sign in as yourself. The result panel shows **Passed**, or the error and the email address the IdP returned.

The test changes nothing for other users. **Enable** stays greyed out until a test has passed and at least one domain is verified.

## How do I turn SSO on?

Select **Enable**. From now on the login page offers **Sign in with SSO** to users on the verified domain. Password login still works at this stage. The audit log records `sso.enabled`.

Ask two or three colleagues to sign in through SSO before you go further.

## Does SSO create users automatically?

No. A person must already be a member or have a pending invitation. SSO only changes how they sign in. On **Enterprise**, SCIM provisioning can create and remove members from the IdP.

## How do I enforce SSO?

Turn on **Settings → Security → SSO → Enforce SSO** and confirm. Password login is then disabled for everyone on the verified domain, except the Owner. The audit log records `sso.enforced`, and the `sso.enforced` webhook event is sent.

Guests and members on other email domains still sign in with a password.

## What is the Owner break-glass login?

When **Enforce SSO** is on, the **Owner** can still sign in at `https://app.acme-cloud.example/login` with **password + MFA**. Use it when the IdP is down or the connection is broken, then fix the connection or turn off **Enforce SSO**. Keep the Owner's MFA device and backup codes safe. Admins do not have a break-glass login.

## How do I rotate the IdP certificate?

1. Before the old certificate expires, go to **Settings → Security → SSO**, open the connection and select **Add certificate**.
2. Upload the new X.509 certificate. A connection can hold **two** certificates at once, and a response signed by either is accepted.
3. Switch the IdP to the new certificate.
4. Select **Test connection**, then remove the old certificate.

If the IdP has already switched and logins fail, upload the new certificate straight away. The Owner can get in with the break-glass login.

## How do I fix "SAML response signature invalid"?

The response was signed with a certificate Acme Cloud does not have. Almost always the IdP rotated its certificate. Upload the new one in **Settings → Security → SSO**. Also check that you copied the certificate of the right IdP application, and that the IdP signs the response.

If nothing changed on your side, check `https://status.acme-cloud.example`. In incident **INC-2026-003** this error was caused by clock drift on Acme Cloud's servers, and no customer action was needed.

## How do I fix an error about the assertion time?

The message is "SAML assertion is expired or not yet valid". Acme Cloud allows a clock skew of **3 minutes**. If the IdP server's clock is more than 3 minutes off, every login is rejected. Sync the IdP server's clock (NTP) and test again. Hosted IdPs keep their own clocks correct; this mostly affects self-hosted ones.

## What other SSO errors might I see?

| Message | Cause | Fix |
|---------|-------|-----|
| "Domain not verified" | TXT record missing, wrong or not yet visible | Check the record is exactly `acme-verify=<token>` on the root domain, wait, then **Verify domain** |
| "Audience mismatch" | Entity ID in the IdP is not the one shown on screen | Copy the Entity ID again, including the workspace ID |
| "Recipient mismatch" | ACS URL is wrong | Copy the ACS URL again |
| "NameID is not an email address" | NameID format is not `emailAddress` | Change the format and map it to the user's email |
| "User is not a member of this workspace" | No member or invitation with that email | Invite the user in **Settings → Members** |
| "Email domain does not match" | The user's email is on a domain you have not verified | Verify that domain too |
| "Invalid client" (OIDC) | Wrong Client ID or Client secret | Enter them again |
| "Redirect URI mismatch" (OIDC) | Redirect URI in the IdP differs | Copy the redirect URI again |

## What should I know for Okta?

Create a **SAML 2.0** app integration (or **OIDC – Web Application**). The ACS URL goes in "Single sign-on URL" and the Entity ID in "Audience URI". Set "Name ID format" to EmailAddress and "Application username" to Email. Assign the users or groups to the app, or they get an Okta error before reaching Acme Cloud.

## What should I know for Microsoft Entra ID?

Create an **Enterprise application** (non-gallery) and choose SAML. The Entity ID goes in "Identifier" and the ACS URL in "Reply URL". Set the unique user identifier claim to the user's mail attribute, not the object ID. Download "Federation Metadata XML" and upload it. Assign users to the application.

## What should I know for Google Workspace?

Add a **custom SAML app** in the Google Admin console. Set "Name ID format" to EMAIL and "Name ID" to the primary email. Turn the app **on** for the right organisational units; it is off for everyone by default. Changes can take a while to reach all users.

## What should I know for OneLogin?

Use the **SAML Custom Connector (Advanced)** app. The Entity ID goes in "Audience", the ACS URL in both "Recipient" and "ACS (Consumer) URL". Set the SAML nameID format to Email. Give users access through a role.

## What should I know for JumpCloud?

Create a **Custom SAML App**. The Entity ID goes in "SP Entity ID" and the ACS URL in "ACS URL". Set "SAMLSubject NameID" to email and the format to `emailAddress`. Tick "Sign Assertion", and bind the app to a user group.

Source: `docs/reference/constants-and-glossary.md` ("What are the authentication rules?"); release 2026.8 and incident INC-2026-003 in `docs/reference/release-and-incident-index.md`.

Last reviewed: 2026-11-26
