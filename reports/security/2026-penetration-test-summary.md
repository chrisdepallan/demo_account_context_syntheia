# Penetration Test Summary 2026

This is a summary of the external penetration test of Acme Cloud carried out in September 2026. It lists the scope, the method and the findings with their severity, status and the release that fixed them. Descriptions are kept at a summary level on purpose; technical detail is in the full report, which is held by the Platform team and is not part of this repository. All data is fictional sample data.

## What were the key facts of the test?

| Item | Value |
|------|-------|
| Type of test | External penetration test by an independent security firm |
| Testing period | 2026-09-14 to 2026-09-25 (10 working days) |
| Final report received | 2026-10-09 |
| Retest | 2026-11-17 |
| Findings | 8: no critical, 1 high, 3 medium, 4 low |
| Status on 2026-11-26 | 7 fixed and confirmed by the retest; 1 low finding open |

The test found no critical issue. It found 1 high, 3 medium and 4 low findings. Seven of the eight are fixed. The high finding was fixed during the test, before the affected feature became generally available.

## What was in scope?

- The dashboard at `https://app.acme-cloud.example`, including login, password reset, MFA and all Settings pages.
- The auth service at `https://auth.acme-cloud.example`, including SAML SSO.
- The REST API at `https://api.acme-cloud.example/v1` and the sandbox API at `https://sandbox.api.acme-cloud.example/v1`, including API keys, scopes and rate limits.
- Webhooks, tested on the release candidate of 2026.7 before general availability on 2026-09-29.
- The internal admin console at `https://admin.acme-cloud.example`, tested with a staff test account.
- The help center at `https://help.acme-cloud.example`.

Tests ran against the staging environments of all three regions (`us-east`, `eu-central` and `ap-south`), which are built from the same code and the same kind of config as production.

## What was out of scope?

- The payment processor and the identity providers of customers.
- Denial-of-service attacks and load tests.
- Social engineering of staff or customers, and physical access.
- Production customer data. No real customer account was used.
- OIDC SSO and the new ownership transfer flow. Both shipped in release 2026.8, after the test. They will be in scope in 2027.

## How was the test done?

- **Approach:** grey-box. The testers had documentation and test accounts but no source code.
- **Accounts:** one test account per plan (Free, Starter, Pro, Business and Enterprise) and one test user per role (`owner`, `admin`, `billing_admin`, `member` and `guest`), plus API keys with different scopes.
- **Focus areas:** access control between roles and between accounts, authentication and session handling, API key handling, input handling, webhook delivery, and configuration of the public endpoints.
- **Team:** two testers for 10 working days.
- **Severity scale:** critical, high, medium, low. Severity combines how easy a weakness is to use with the damage it could do.
- **Communication:** high or critical findings were to be reported within one business day. This happened once (finding PT-2026-01, reported on 2026-09-16).

## What did the test find?

| ID | Severity | Area | Finding (summary) | Status | Fixed in |
|----|----------|------|-------------------|--------|----------|
| PT-2026-01 | High | Webhooks | A webhook endpoint URL could point to an address inside the internal network | Fixed, confirmed by retest | Release 2026.7 (2026-09-29) |
| PT-2026-02 | Medium | API keys | A revoked API key was accepted for longer than 60 seconds in the `ap-south` environment | Fixed, confirmed by retest | Release 2026.8 (2026-11-10) |
| PT-2026-03 | Medium | Admin console | Staff sessions in the admin console had no idle timeout | Fixed, confirmed by retest | Release 2026.8 (2026-11-10) |
| PT-2026-04 | Medium | Login | The lockout counter was kept per auth node, so more than 5 failed attempts were possible before a lockout | Fixed, confirmed by retest | Release 2026.8 (2026-11-10) |
| PT-2026-05 | Low | Audit log | Values in the audit log CSV download were not protected against being read as formulas by a spreadsheet | Fixed, confirmed by retest | Release 2026.8 (2026-11-10) |
| PT-2026-06 | Low | Help center | Some recommended browser security headers were missing on the help center | Fixed, confirmed by retest | Configuration change on 2026-10-06 |
| PT-2026-07 | Low | Sandbox API | The sandbox API still accepted an outdated encryption setting for connections | Fixed, confirmed by retest | Configuration change on 2026-10-06 |
| PT-2026-08 | Low | Password reset | The password reset form answered slightly faster for unknown email addresses, which could reveal whether an address has an account | Open | Planned for the first release of 2027 |

By severity: 0 critical, 1 high, 3 medium and 4 low. By status: 7 fixed and 1 open. Four findings were fixed in release 2026.8, one in release 2026.7 and two by configuration changes.

## What was the high finding, and how was it fixed?

**PT-2026-01.** When a customer registered a webhook endpoint, the URL was not checked well enough. A customer could have entered a URL that pointed to a system inside the Acme Cloud network, and the webhook sender would have made requests to it.

- Reported by the testers on 2026-09-16, the third day of the test.
- Fixed by the Platform team on 2026-09-18. Endpoint URLs must use HTTPS and must point to a public address; the check is repeated at every delivery, not only when the endpoint is created.
- Four automated tests were added before the code freeze for release 2026.7 on 2026-09-22.
- The feature was in preview during the test. A review of the preview period found no endpoint that pointed to an internal address.
- No customer data was exposed.

Because the fix shipped in release 2026.7, webhooks never ran in general availability with this weakness.

## Which finding became INC-2026-006?

**PT-2026-02**, the key revocation delay.

The rule is that a revoked API key stops working within 60 seconds. In the `ap-south` test environment the testers saw a revoked test key accepted for several minutes. In the other two regions revocation took effect within 60 seconds.

- Cause: the lifetime of the key cache was read from each region's config file, and nothing in the code limited it. The value for `ap-south` was wrong.
- Rated medium, not high: an attacker would first need a valid key, and the extra time was limited to minutes.
- While working on this finding after the final report, the Identity team compared the settings of all regions and found the wrong value in production `ap-south` as well: 900 seconds, so a revoked key could work for up to 15 minutes. This was opened as incident INC-2026-006 on 2026-10-15, priority P3, recorded with 5 days to detect. The incident report is `reports/incidents/INC-2026-006-key-revocation-delay.md`.
- Fix: since release 2026.8 the cache lifetime is fixed at 60 seconds in code and cannot be changed by config. The runbook `docs/runbooks/leaked-api-key.md` was updated.
- At the retest on 2026-11-17, a revoked key was refused in under 60 seconds in all three regions.

The lesson is wider than this one setting: a value that a security rule depends on should not differ between regions.

## What were the other medium findings?

**PT-2026-03, admin console sessions.** A staff session in the admin console stayed valid without any activity. A support agent who left a signed-in browser unattended left the console open. Since release 2026.8, a staff session ends after 30 minutes without activity, and issuing a refund asks the agent to sign in again if the last sign-in is more than 8 hours old. The first-half access review of console roles is a separate document: `reports/security/2026-h1-access-review.md`.

**PT-2026-04, lockout counter.** The login rule is that 5 failed attempts within 15 minutes lock the login for 15 minutes, and 10 failed attempts within 1 hour lock it for 1 hour. Each auth node kept its own count, so attempts spread across nodes could exceed 5 before the lock. Since release 2026.8 the count is shared by all nodes. The stricter rule (10 attempts in 1 hour) was already counted centrally, which limited the effect.

## What were the low findings?

- **PT-2026-05, audit log CSV.** A value that starts with a formula character, such as a member name typed that way on purpose, could be read as a formula when an Admin opened the CSV in a spreadsheet. Such values are now written as plain text. The CSV download itself was new in release 2026.6.
- **PT-2026-06, help center headers.** Missing browser security headers on a site that has no login. Added by a configuration change.
- **PT-2026-07, sandbox API.** The sandbox accepted an older encryption setting that production had already switched off. The sandbox now matches production.
- **PT-2026-08, password reset timing.** The form shows the same message for known and unknown email addresses, as intended, but the response time differed slightly. Using this would need many measurements, and the rate limit on the form makes that slow. The fix is planned for the first release of 2027; until then the risk is accepted by the Identity team lead.

## What did the test confirm as working well?

The testers recorded these checks as passed:

- A user with one role could not perform actions of a higher role. For example, an Admin could not open billing, and a Billing admin could not manage members or API keys.
- No test account could read or change data of another account or workspace.
- API keys are stored as a hash; the full key is shown only once and could not be recovered.
- Payment methods appear only as processor tokens such as `pm_9XK2M4QH7T`. No card number was found in any response, log sample or export.
- Password rules (12 to 128 characters, no breached passwords, not the last 5) were enforced on the server, not only in the form.
- Password reset links worked once and expired after 60 minutes.
- With **Enforce SSO** on, password login was refused for every user of the verified domain except the Owner.
- Rate limits returned HTTP 429 with a `Retry-After` header.

## What happens next?

1. Fix PT-2026-08 in the first release of 2027. Owner: Identity team.
2. Move every setting that a security rule depends on out of per-region config. Owner: Platform team, first quarter of 2027.
3. Include OIDC SSO, ownership transfer and webhooks in general availability in the 2027 test.
4. Keep the yearly rhythm: the next external test is planned for September 2027.

Last reviewed: 2026-11-26
