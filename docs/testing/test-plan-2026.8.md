# Test Plan for Release 2026.8

Release **2026.8** shipped on **2026-11-10**. This is the plan that was approved before testing started. It follows `test-strategy.md`; only what is specific to this release is written here. Results are in `reports/test-runs/` and the release report is `reports/releases/2026.8.md`.

## What is in release 2026.8?

| Change | Owning team | Summary |
|--------|-------------|---------|
| Ownership transfer needs acceptance | Accounts team | The chosen Admin must accept within **7 days**. Until then the Owner does not change. An unanswered request expires. |
| OIDC SSO | Identity team | **Settings → Security → SSO → Add OIDC connection**, next to the existing SAML option. Business and Enterprise. |
| Key cache TTL fixed in code | Identity team | Follow-up to **INC-2026-006**: the key cache TTL is **60 seconds** in code, not in per-region config. |

## What is in scope?

**Ownership transfer**

- Request from **Settings → Account → Transfer ownership**; only Admins are offered as targets.
- `ownership_transfer` email to the new Owner; accept link valid **7 days**.
- Accept: the Admin becomes Owner, the previous Owner becomes Admin, exactly one Owner at every moment.
- Expiry at 7 days; boundary just before and just after.
- Audit events `ownership.transfer_requested` and `ownership.transferred`.
- Admins, Billing admins, Members and Guests cannot start a transfer.

**OIDC SSO**

- Create, test and enable an OIDC connection; connection ID format `sso_` + 6.
- Domain verification with the TXT record `acme-verify=<token>` is shared with SAML.
- **Enforce SSO** with an OIDC connection; Owner break-glass login with password + MFA.
- Plan gate: not offered below Business (`ERR_PLAN_REQUIRED`).
- Audit events `sso.enabled`, `sso.enforced`; webhook `sso.enforced`.
- Regression of SAML: setup, certificate rotation, the **3-minute** clock skew.

**Key revocation**

- A revoked key is rejected within **60 seconds** in `us-east`, `eu-central` and `ap-south`.
- A rotated key still works for **24 hours**.

## What is out of scope?

- SCIM provisioning (Enterprise). No change in this release.
- Billing, refunds and dunning logic. Covered by the automated suites only, plus a billing smoke set.
- Webhook delivery and retries, apart from the `sso.enforced` event.
- The support process for an unreachable Owner. It does not use the new acceptance flow.
- Mobile apps. Mobile sessions (90 days) are not changed.
- Performance and load testing. Run each quarter by the Platform team, not per release.
- Testing against every identity provider. See the risk table for the two that are used.

## What are the risks?

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| An account ends with no Owner or two Owners during a transfer | Low | High | Unit tests on the state change; `TC-ACCT-012` and `TC-ACCT-013`; a check query after each sandbox run |
| Requests created before the release never expire | Medium | Medium | Migration gives each open request a 7-day expiry from the release date; checked in sandbox with seeded old requests |
| OIDC misconfiguration locks a workspace out when **Enforce SSO** is on | Medium | High | **Enable** needs a passed **Test connection**; `TC-SEC-014` proves the Owner break-glass login |
| OIDC change breaks SAML logins | Low | High | Full SAML regression: `TC-SEC-011`, `TC-SEC-015`, `TC-SEC-016` |
| Clock drift again rejects SSO logins (as in INC-2026-003) | Low | High | Clock drift alert at 30 seconds stays in place; `TC-SEC-015` in every region |
| Key cache differs per region again (as in INC-2026-006) | Low | Medium | `TC-KEY-011` is run in all three regional sandboxes |
| Only two identity providers are tested for OIDC | Medium | Low | Okta and Microsoft Entra ID test tenants cover most customers; other providers are tested on request after release |

## Which environments are used?

One sandbox per region. Each has its own database, auth service and key cache, and uses the payment processor in test mode.

| Environment | Region | Used for |
|-------------|--------|----------|
| Sandbox `us-east` | Virginia | All automated suites; all manual suites in scope |
| Sandbox `eu-central` | Frankfurt | Manual High-priority cases; `TC-KEY-011`; `TC-SEC-015` |
| Sandbox `ap-south` | Mumbai | Manual High-priority cases; `TC-KEY-011`; `TC-SEC-015` |

The sandbox API is `https://sandbox.api.acme-cloud.example/v1` and accepts `acme_test_` keys only. Time-based cases (7-day expiry) use the sandbox clock control in the admin console instead of waiting.

Test accounts: one Business account and one Enterprise account per region, plus one Pro and one Starter account in `us-east` for the plan-gate cases. Each has an Owner, two Admins, a Billing admin, a Member and a Guest, all on `@example.com` addresses. No real customer data is used.

## What is the schedule?

| Date | Milestone |
|------|-----------|
| 2026-10-27 | Test plan approved |
| 2026-11-03 | **Code freeze**; release branch cut; sandbox `us-east` deployed |
| 2026-11-03 to 2026-11-05 | Automated suites on the release branch; manual pass in sandbox `us-east` |
| 2026-11-06 | Manual High-priority pass in sandboxes `eu-central` and `ap-south` |
| 2026-11-09 | Defect re-test; go/no-go meeting; test-run report filed |
| 2026-11-10 | **Release** to `us-east` |
| 2026-11-11 | Release to `eu-central` and `ap-south` (one business day later) |
| 2026-11-12 | Post-release smoke test in production, all regions |

After code freeze only fixes for P1 and P2 defects found in testing are merged. Each fix needs a re-run of the automated suites and of the manual cases it touches.

## Which automated suites run?

All of them, on every commit to the release branch, with `python -m pytest`:

- `tests/unit/` for all nine packages. New tests in this release sit in `tests/unit/accounts/` (transfer request, accept, expiry), `tests/unit/auth/` (OIDC connection, token checks) and `tests/unit/api_keys/` (cache TTL constant).
- `tests/integration/`, including transfer plus audit plus notification, and SSO enforcement plus login.

Coverage must stay at or above **90%** for `billing` and `auth` and **85%** elsewhere.

## Which manual suites run?

| Suite | Scope in this release | Cases |
|-------|-----------------------|-------|
| `account-and-members.md` | Full suite | All `TC-ACCT` cases; focus on `TC-ACCT-010` to `TC-ACCT-014` |
| `security-and-sso.md` | Full suite | All `TC-SEC` cases; focus on `TC-SEC-011` to `TC-SEC-017` |
| `api-keys.md` | Full suite | All `TC-KEY` cases; `TC-KEY-011` in every region |
| `billing.md` | Smoke set | High-priority cases only, including `TC-BILL-014` |
| `workspace-and-export.md` | Smoke set | High-priority cases only |
| `support-and-admin-console.md` | Smoke set | High-priority cases only |

The chatbot evaluation in `eval/test-questions.md` is re-run because `docs/ui/settings-account.md` and the SSO pages changed.

## What must pass before the release ships?

The exit criteria in `test-strategy.md`, plus three release-specific checks:

1. `TC-ACCT-012` and `TC-ACCT-013` pass in all three sandboxes.
2. `TC-SEC-013` passes against both the Okta and the Microsoft Entra ID test tenants.
3. `TC-KEY-011` shows rejection within **60 seconds** in all three sandboxes.

## Who signs off?

| Role | Signs off on |
|------|--------------|
| QA lead | Test results and exit criteria |
| Accounts team lead | Ownership transfer |
| Identity team lead | OIDC SSO and the key cache fix |
| Security reviewer | SSO enforcement and break-glass behaviour |
| Release manager | Go/no-go, schedule and rollback plan |
| On-call engineer (Platform team) | Deploy readiness and alerts for the release window |

All six must sign before the deploy to `us-east`. The release manager can stop the roll-out to `eu-central` and `ap-south` if the first day in `us-east` shows a P1 or P2 defect.

## What is the rollback plan?

Both features sit behind release flags. If a P1 defect appears, the on-call engineer turns the flag off: transfers return to the previous behaviour and **Add OIDC connection** is hidden. OIDC connections already enabled keep working, so no workspace is locked out by a rollback. The key cache change has no flag; it is rolled back by redeploying release 2026.7.

Last reviewed: 2026-11-26
