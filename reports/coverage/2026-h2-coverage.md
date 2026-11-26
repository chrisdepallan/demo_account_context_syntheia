# Test Coverage Report: Second Half of 2026

This report shows how much of the Acme Cloud code in `src/acme_cloud/` was exercised by the automated tests on 2026-11-03. It was measured on commit `e19a5d8`, the code freeze for release 2026.8, with 523 automated tests. It follows the first-half report in `reports/coverage/2026-h1-coverage.md`. All data is fictional sample data.

## What are the coverage targets?

The targets did not change in 2026: **90% line coverage** for `billing` and `auth`, and **85% line coverage** for the other seven packages. Branch coverage is reported without a target.

## Did each package meet its target on 2026-11-03?

| Package | Owner | Lines | Lines covered | Line coverage | Target | Met? | Branch coverage |
|---------|-------|-------|---------------|---------------|--------|------|-----------------|
| `common` | Platform team | 440 | 424 | 96.4% | 85% | Yes | 92.0% |
| `accounts` | Accounts team | 890 | 821 | 92.2% | 85% | Yes | 86.1% |
| `workspaces` | Accounts team | 760 | 670 | 88.2% | 85% | Yes | 82.8% |
| `billing` | Billing team | 1,530 | 1,426 | 93.2% | 90% | Yes | 87.3% |
| `auth` | Identity team | 1,480 | 1,350 | 91.2% | 90% | Yes | 84.5% |
| `api_keys` | Identity team | 580 | 545 | 94.0% | 85% | Yes | 88.7% |
| `support` | Support Tools team | 640 | 566 | 88.4% | 85% | Yes | 81.9% |
| `notifications` | Platform team | 910 | 763 | 83.8% | 85% | **No** | 76.3% |
| `audit` | Platform team | 560 | 507 | 90.5% | 85% | Yes | 85.6% |
| **All packages** | | **7,790** | **7,072** | **90.8%** | | | **84.7%** |

Eight of nine packages met their line coverage target. The two packages that missed in the first half, `workspaces` and `auth`, now meet it. One package, `notifications`, fell below its target: 83.8% against 85%. Overall line coverage rose to 90.8% and overall branch coverage to 84.7%.

## How did coverage change since 2026-06-30?

| Package | Line coverage 2026-06-30 | Line coverage 2026-11-03 | Change (percentage points) | Target met in H1? | Target met in H2? |
|---------|--------------------------|--------------------------|----------------------------|-------------------|-------------------|
| `common` | 96.2% | 96.4% | +0.2 | Yes | Yes |
| `accounts` | 91.4% | 92.2% | +0.8 | Yes | Yes |
| `workspaces` | 81.7% | 88.2% | +6.5 | No | Yes |
| `billing` | 92.6% | 93.2% | +0.6 | Yes | Yes |
| `auth` | 88.9% | 91.2% | +2.3 | No | Yes |
| `api_keys` | 93.1% | 94.0% | +0.9 | Yes | Yes |
| `support` | 87.5% | 88.4% | +0.9 | Yes | Yes |
| `notifications` | 86.3% | 83.8% | -2.5 | Yes | No |
| `audit` | 88.9% | 90.5% | +1.6 | Yes | Yes |
| **All packages** | **89.7%** | **90.8%** | **+1.1** | | |

Eight packages improved and one got worse. The largest gain was `workspaces`, up 6.5 percentage points. The only loss was `notifications`, down 2.5 percentage points.

## How did `workspaces` and `auth` reach their targets?

**`workspaces`: 81.7% to 88.2%.** After INC-2026-004 on 2026-07-22 (exports stuck in `running` for 9 hours 40 minutes), the Accounts team wrote the tests that were missing in June.

- A worker that stops in the middle of a job: another worker takes over the lease.
- An export that runs longer than 24 hours is marked `failed`. An export at exactly 24 hours is still `running`.
- A `failed` export does not block a new export for the same workspace.
- The package went from 41 to 48 tests, and the export worker module went from 61.3% to 89.5% line coverage.

**`auth`: 88.9% to 91.2%.** The Identity team removed the two skipped passkey tests from the skip list on the updated CI image, and added tests for each reason a SAML assertion can be refused. OIDC, added in release 2026.8, arrived with its tests: the package went from 73 to 88 tests while it grew by 220 lines.

Both packages met their targets from release 2026.6 onwards and stayed above them at every later freeze.

## Why did `notifications` fall below its target?

Webhook delivery became generally available in release 2026.7 and its code lives in the `notifications` package. The package grew from 540 to 910 lines, the largest growth of any package in the second half.

- Well covered: the retry schedule (6 retries, counted from the first failure: 1 minute, 5 minutes, 30 minutes, 2 hours, 8 hours and 24 hours), the `Acme-Signature` header, and the endpoint limit per plan.
- Poorly covered: the code that disables an endpoint after 3 days of continuous failures, the code that re-enables it, and the handling of network errors other than a timeout (name lookup failures, refused connections, certificate errors).
- The package is 1.2 percentage points under its target. It needs 11 more covered lines (774 of 910).

The merge block introduced in July did not stop this, because the Platform team lead approved an exception on 2026-09-10 so that webhooks could ship in release 2026.7. The exception ends on 2026-12-15.

## Which modules were least covered?

| Module | Package | Line coverage | Main untested area |
|--------|---------|---------------|--------------------|
| `notifications/webhook_endpoints.py` | `notifications` | 71.4% | Disable after 3 days of failures; re-enable |
| `notifications/webhook_delivery.py` | `notifications` | 78.9% | Network errors other than a timeout |
| `support/escalation.py` | `support` | 82.3% | Review deadline when a team lead is reassigned |
| `auth/oidc.py` | `auth` | 84.0% | Provider key rotation, unusual claim formats |
| `billing/payment_methods.py` | `billing` | 85.2% | UPI mandates; ACH and SEPA (still tested by hand) |
| `audit/csv_export.py` | `audit` | 86.1% | Downloads above 100,000 rows |

The two least-covered modules are both part of webhook delivery. The export worker, the weakest module in the first-half report, is no longer in the list.

## What was added since the last report?

- **95 new tests** between 2026-06-30 and 2026-11-03 (428 to 523).
- `audit`: 16 more tests for filters, CSV download and retention per plan (Pro 90 days, Business 1 year, Enterprise 7 years), from release 2026.6.
- `notifications`: 19 more tests, almost all for webhooks.
- `auth`: 15 more tests for OIDC and SAML refusal reasons, plus a shared lockout counter test (5 failed attempts within 15 minutes lock for 15 minutes on any auth node).
- `accounts`: 11 more tests, mostly for ownership transfer with acceptance within 7 days.
- `api_keys`: 7 more tests. Five of them came from INC-2026-006 and check that a revoked key is refused within 60 seconds and that the cache lifetime cannot be changed by config.
- Integration: 9 more tests. Three run against all three staging regions (`us-east`, `eu-central`, `ap-south`): key revocation, replica promotion and SAML clock skew.

## Which items of the first-half plan were done?

| Plan item from the first-half report | Status on 2026-11-03 |
|--------------------------------------|----------------------|
| Export worker failure tests and an upper time limit | Done in release 2026.6 |
| Run the two skipped passkey tests | Done in release 2026.6 |
| One test per SAML refusal reason | Done in release 2026.7 |
| Local fakes for UPI, ACH and SEPA | Not done; UPI fake in progress, bank transfers not started |
| Review error paths in the export code | Done; branch coverage of `workspaces` rose from 72.5% to 82.8% |
| Integration tests against all three staging regions | Partly done; three tests exist, a full regional suite does not |

Four of six items are done, one is partly done and one is not done.

## What are the gaps, and what is the plan?

| Gap | Risk | Plan | Owner | Target |
|-----|------|------|-------|--------|
| `notifications` is at 83.8% | An endpoint is disabled too early, or never | Tests for disable, re-enable and each network error type | Platform team | 2026-12-15, when the exception ends |
| UPI, ACH and SEPA are tested by hand | Payment bugs found late | Finish the UPI fake; start the bank-transfer fake | Billing team | First release of 2027 |
| Only three tests run in every region | A setting can differ per region, as in INC-2026-006 | A regional suite of at least 20 integration tests | Platform team | First quarter of 2027 |
| Branch coverage of `notifications` is 76.3% | Error paths not exercised | Covered by the first item | Platform team | 2026-12-15 |
| Large audit CSV downloads are untested | Slow or failed downloads on big accounts | A test with 250,000 rows | Platform team | First release of 2027 |

The plan has five items. The first one closes the only missed target.

## What should a reader take from this report?

- Overall line coverage passed 90% for the first time: 90.8%, up from 89.7% in June and 88.4% in January.
- The pattern from the first half repeated: the package that received the largest new feature (`notifications`, webhooks) is the one below target.
- Coverage numbers do not show configuration problems. INC-2026-006 came from a per-region config value, in a package (`api_keys`) with 93.1% line coverage at the time.

Last reviewed: 2026-11-26
