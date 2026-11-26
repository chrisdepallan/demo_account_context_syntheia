# Manual Test Suite: Security and SSO

Covers the login page, **Profile → Security**, and **Settings → Security**: passwords, lockout, MFA, policies and SSO (SAML and OIDC). Run in a sandbox. SSO cases use a test tenant at an identity provider (IdP) and a test domain whose DNS the tester controls. Time is moved with **Sandbox tools → Advance clock** in the admin console. Never write real passwords or MFA codes into results.

## TC-SEC-001: Password length is limited to 12 to 128 characters

**Preconditions:** A user on the reset form after **Forgot password**.

**Steps:**
1. Enter a password of **11** characters and submit.
2. Enter **12** characters and submit.
3. Repeat the reset and try **129**, then **128** characters.

**Expected result:** 11 and 129 characters are refused with `ERR_VALIDATION`. 12 and 128 characters are accepted.

**Priority:** High

## TC-SEC-002: A password with the email address or a recent password is refused

**Preconditions:** User `tester@example.com` who has changed password five times; the five old values are known to the tester.

**Steps:**
1. On the reset form, enter a 20-character password that contains `tester@example.com`.
2. Enter the oldest of the last **5** passwords.
3. Enter a password used before those five.

**Expected result:** Steps 1 and 2 are refused with `ERR_VALIDATION`. Step 3 is accepted.

**Priority:** Medium

## TC-SEC-003: A reset link is valid for 60 minutes and works once

**Preconditions:** A user signed in on two browsers.

**Steps:**
1. On the login page, select **Forgot password** and request two links, one after the other.
2. Advance the clock **61 minutes** and open the first link.
3. Request a new link, open it within 60 minutes and set a new password.
4. Open the same link again.

**Expected result:** Step 2 shows that the link has expired. Step 3 succeeds, writes `password.reset` to the audit log and signs out both other sessions. Step 4 is refused because the link is single use.

**Priority:** High

## TC-SEC-004: Five failed attempts lock login for 15 minutes

**Preconditions:** A user with a known password and no lock.

**Steps:**
1. Enter a wrong password **4** times within 15 minutes, then the right one.
2. Sign out. Enter a wrong password **5** times within 15 minutes, then the right one.
3. Select **Forgot password** and complete a reset.

**Expected result:** Step 1 signs in. Step 2 is refused with `ERR_LOCKED_OUT` for **15 minutes**, and the audit log shows `login.locked`. No email is sent for this lock. After step 3 the user can sign in at once.

**Priority:** High

## TC-SEC-005: Ten failed attempts in an hour lock login for 1 hour

**Preconditions:** A user with no lock.

**Steps:**
1. Make **10** failed attempts within 1 hour, waiting out the 15-minute lock in between.
2. Try the right password after 59 minutes, then after 61 minutes.

**Expected result:** After the tenth failure login is locked for **1 hour** and the user gets the `login_locked` email. The attempt at 59 minutes fails with `ERR_LOCKED_OUT`; the attempt at 61 minutes succeeds.

**Priority:** High

## TC-SEC-006: Setting up an authenticator app shows 10 backup codes

**Preconditions:** A Member with no MFA.

**Steps:**
1. Go to **Profile → Security** and add an authenticator app.
2. Scan the code and enter the 6-digit code from the app.

**Expected result:** The method is listed as active. The screen shows **10** backup codes once. The audit log shows `mfa.enrolled`. The next login asks for a code.

**Priority:** High

## TC-SEC-007: New backup codes invalidate the old ones

**Preconditions:** A user with MFA and a saved set of backup codes.

**Steps:**
1. Sign in with one old backup code, sign out, and try the same code again.
2. Go to **Profile → Security** and generate new backup codes.
3. Sign out and try an unused code from the old set, then one from the new set.

**Expected result:** A code works once only. After step 2, every old code is refused and the new code works. There are **10** new codes.

**Priority:** Medium

## TC-SEC-008: SMS is hidden for Admins on Business

**Preconditions:** Business account. One Admin and one Member, both without MFA.

**Steps:**
1. As the Member, go to **Profile → Security** and read the list of methods.
2. As the Admin, do the same.

**Expected result:** The Member is offered authenticator app, security key or passkey, and SMS. The Admin is offered authenticator app and security key or passkey only.

**Priority:** Medium

## TC-SEC-009: Require MFA gives a 7-day grace period

**Preconditions:** Pro account. Member A has no MFA. Signed in as an Admin.

**Steps:**
1. Turn on **Settings → Security → Require MFA**.
2. Sign in as Member A and skip the setup prompt.
3. Advance the clock **6 days** and sign in again; then advance **2 more days** and sign in.

**Expected result:** The audit log shows `policy.changed`. Member A sees the prompt at each login and can skip it for **7 days** from the first login after the change. On day 8 Member A cannot continue without setting up MFA.

**Priority:** High

## TC-SEC-010: Require MFA is not offered on Starter

**Preconditions:** Starter account. Signed in as the Owner.

**Steps:**
1. Open **Settings → Security**.

**Expected result:** The **Require MFA** toggle is absent or shown locked with an upgrade notice. A direct request to turn it on returns `ERR_PLAN_REQUIRED`. Users can still set up their own MFA in **Profile → Security**.

**Priority:** Medium

## TC-SEC-011: A SAML connection can be created, tested and enabled

**Preconditions:** Business account, no SSO. A SAML app in the test IdP. Signed in as an Admin.

**Steps:**
1. Go to **Settings → Security → SSO → Add SAML connection**.
2. Copy the ACS URL, Entity ID and NameID format into the IdP.
3. Upload the IdP metadata XML and save.
4. Verify the test domain, select **Test connection**, then **Enable**.

**Expected result:** The ACS URL is `https://auth.acme-cloud.example/saml/acs/{workspace_id}` with the real workspace ID, and the NameID format is `emailAddress`. The test passes. The connection has an ID like `sso_7Q3W9E`. The audit log shows `sso.enabled`, and the login page offers **Sign in with SSO**.

**Priority:** High

## TC-SEC-012: Enable is blocked until the domain is verified

**Preconditions:** A saved SAML connection; the domain has no TXT record yet.

**Steps:**
1. In **Settings → Security → SSO → Domains**, add the domain and select **Verify domain**.
2. Try **Enable**.
3. Add the TXT record `acme-verify=<token>` shown on screen, wait for DNS, and select **Verify domain** again.

**Expected result:** Step 1 shows "Domain not verified". **Enable** stays unavailable in step 2. After step 3 the domain is verified and **Enable** becomes available once the test has passed.

**Priority:** High

## TC-SEC-013: An OIDC connection can be created, tested and enabled

**Preconditions:** Business account, no SSO, verified domain. An OIDC web application in the test IdP.

**Steps:**
1. Go to **Settings → Security → SSO → Add OIDC connection**.
2. Enter the Issuer URL, Client ID and Client secret, and save.
3. Select **Test connection**, then **Enable**.
4. Sign out and select **Sign in with SSO**.

**Expected result:** The redirect URI shown is `https://auth.acme-cloud.example/oidc/callback/{workspace_id}`. The test passes and login through the IdP works. The client secret is not displayed after saving. The audit log shows `sso.enabled`.

**Priority:** High

## TC-SEC-014: Enforce SSO keeps the Owner's break-glass login

**Preconditions:** SSO enabled, domain verified. Owner and Admin A both have a password and MFA.

**Steps:**
1. As the Owner, turn on **Settings → Security → SSO → Enforce SSO**.
2. As Admin A, try to sign in with email and password.
3. As the Owner, sign in with email, password and MFA.

**Expected result:** The audit log shows `sso.enforced` and the `sso.enforced` webhook is delivered. Admin A is told to use SSO; password login is refused. The Owner signs in with **password + MFA**.

**Priority:** High

## TC-SEC-015: A SAML assertion more than 3 minutes off is rejected

**Preconditions:** SAML enabled. A test IdP whose clock can be shifted.

**Steps:**
1. Shift the IdP clock **2 minutes 50 seconds** ahead and sign in with SSO.
2. Shift it **3 minutes 10 seconds** ahead and sign in again.

**Expected result:** Step 1 succeeds. Step 2 is refused with "SAML assertion is expired or not yet valid" and the audit log shows `login.failed`. The allowed skew is **3 minutes**.

**Priority:** High

## TC-SEC-016: A rotated IdP certificate causes "SAML response signature invalid" until uploaded

**Preconditions:** SAML enabled. The IdP can issue a second signing certificate.

**Steps:**
1. Switch the IdP to the new certificate and sign in with SSO.
2. As an Admin, open the connection in **Settings → Security → SSO**, select **Add certificate** and upload the new certificate.
3. Sign in with SSO again.

**Expected result:** Step 1 fails with "SAML response signature invalid". After step 2 the connection holds two certificates and step 3 succeeds.

**Priority:** Medium

## TC-SEC-017: SSO is not available on Pro

**Preconditions:** Pro account. Signed in as the Owner.

**Steps:**
1. Open **Settings → Security → SSO**.

**Expected result:** The section shows an upgrade notice instead of **Add SAML connection** and **Add OIDC connection**. A direct request to create a connection returns `ERR_PLAN_REQUIRED`.

**Priority:** High

## TC-SEC-018: Web session length accepts 1 hour to 14 days on Business

**Preconditions:** Business account. Signed in as an Admin.

**Steps:**
1. In **Settings → Security**, set **Web session length** to **1 hour** and save.
2. Leave a Member's session idle for 61 minutes, then click.
3. Try to save **30 minutes**, then **15 days**.

**Expected result:** Step 1 saves and writes `policy.changed`. Step 2: the Member must sign in again. Both values in step 3 are refused with `ERR_VALIDATION`. The setting is not shown on Pro.

**Priority:** Medium

## TC-SEC-019: A Member cannot open Settings → Security

**Preconditions:** Signed in as a Member.

**Steps:**
1. Open the Settings menu.
2. Open the address of **Settings → Security** directly.

**Expected result:** **Security** is not in the menu and the direct address shows `ERR_PERMISSION_DENIED`. **Profile → Security** is still available to the Member.

**Priority:** High

Last reviewed: 2026-11-26
