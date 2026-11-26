# Test Coverage Report: First Half of 2026

This report shows how much of the Acme Cloud code in `src/acme_cloud/` was exercised by the automated tests on 2026-06-30. It was measured on commit `c8e21a6`, the code freeze for release 2026.5, with 428 automated tests. All data is fictional sample data.

## What are the coverage targets?

- **90% line coverage** for the `billing` and `auth` packages. These handle money and logins, so the bar is higher.
- **85% line coverage** for every other package: `common`, `accounts`, `workspaces`, `api_keys`, `support`, `notifications` and `audit`.
- Branch coverage is measured and reported, but it has no target.

Line coverage counts the executable lines that ran at least once. Branch coverage counts the outcomes of each decision (for example both the "yes" and the "no" side of an `if`). Unit tests in `tests/unit/` and integration tests in `tests/integration/` are both counted.

## Did each package meet its target on 2026-06-30?

| Package | Owner | Lines | Lines covered | Line coverage | Target | Met? | Branch coverage |
|---------|-------|-------|---------------|---------------|--------|------|-----------------|
| `common` | Platform team | 420 | 404 | 96.2% | 85% | Yes | 90.6% |
| `accounts` | Accounts team | 780 | 713 | 91.4% | 85% | Yes | 84.3% |
| `workspaces` | Accounts team | 690 | 564 | 81.7% | 85% | **No** | 72.5% |
| `billing` | Billing team | 1,480 | 1,371 | 92.6% | 90% | Yes | 86.2% |
| `auth` | Identity team | 1,260 | 1,120 | 88.9% | 90% | **No** | 80.4% |
| `api_keys` | Identity team | 520 | 484 | 93.1% | 85% | Yes | 87.3% |
| `support` | Support Tools team | 610 | 534 | 87.5% | 85% | Yes | 79.7% |
| `notifications` | Platform team | 540 | 466 | 86.3% | 85% | Yes | 77.4% |
| `audit` | Platform team | 380 | 338 | 88.9% | 85% | Yes | 82.1% |
| **All packages** | | **6,680** | **5,994** | **89.7%** | | | **82.3%** |

Seven of nine packages met their line coverage target. Two missed: `workspaces` reached 81.7% against 85%, and `auth` reached 88.9% against 90%. Overall line coverage was 89.7% and overall branch coverage was 82.3%.

## Why did `workspaces` miss its target?

The workspace export was rewritten as a queued job for release 2026.5. The rewrite added about 240 lines to the package in six weeks, and the tests did not keep up.

- The queue and status code was tested well: `queued`, `running`, `ready` and `expired` were all reached by tests.
- The worker code was tested poorly. The paths for "the worker stops in the middle of a job" and "the job lease is lost" had no test at all.
- The `failed` status could be set by only one path (a storage error). There was no time limit, so there was no code to test for a job that never ends.

The `workspaces` package was 3.3 percentage points under its target. To reach 85% it needed 23 more covered lines (587 of 690).

This gap mattered. INC-2026-004 on 2026-07-22 was caused by exactly the untested path: an export worker lost its job lease, and exports stayed in `running` for 9 hours 40 minutes.

## Why did `auth` miss its target?

Release 2026.3 added passkeys (WebAuthn) as an MFA method. Part of the new code could not run on the CI runner until the runner image got a virtual authenticator on 2026-04-21. The two passkey tests that had been skipped at the 2026.3 freeze ran from that date, but few further tests were written for the sign-in path.

- Passkey registration was covered. Passkey sign-in with user verification was covered only in part.
- The rule that hides SMS for Admins and Owners on Business and Enterprise was covered on the server side.
- SAML error paths were weak. After INC-2026-003 (clock drift of 4 minutes on two auth nodes, above the 3-minute allowed skew), tests were added for the skew limit, but not for every other reason an assertion can be refused.

The `auth` package was 1.1 percentage points under its target. To reach 90% it needed 14 more covered lines (1,134 of 1,260).

## Which modules were least covered?

| Module | Package | Line coverage | Main untested area |
|--------|---------|---------------|--------------------|
| `workspaces/export_worker.py` | `workspaces` | 61.3% | Worker stop, lost lease, storage retry |
| `auth/webauthn.py` | `auth` | 74.8% | Sign-in with user verification, removal of the last passkey |
| `notifications/queue.py` | `notifications` | 76.5% | Retry after a provider error, queue restart |
| `auth/saml.py` | `auth` | 79.2% | Refused assertions other than clock skew |
| `support/escalation.py` | `support` | 80.1% | Team-lead review deadline across a weekend |
| `billing/payment_methods.py` | `billing` | 83.6% | UPI mandates, PayPal blocked for Enterprise and India |

The least-covered module was the export worker at 61.3%. Five of the six modules in this list belong to features that shipped in the first half of 2026.

## What was added since the start of the year?

The first measurement of 2026 was on 2026-01-13, at the freeze for release 2026.1, with 312 tests. Overall line coverage then was 88.4%.

- **116 new tests** between 2026-01-13 and 2026-06-30 (312 to 428).
- `notifications`: tests for the idempotency key on sends (template, recipient and object ID), written after INC-2026-001 sent invoice emails twice on 2026-02-11. The package rose from 81.9% to 86.3% and now meets its target.
- `billing`: tests for payment processor outages, written after INC-2026-002 on 2026-03-19. An outage no longer counts as a dunning failure. Proration rounding has boundary tests for a half cent.
- `api_keys`: tests for the **Require key expiry** policy and the 14-day `key_expiring` email from release 2026.2.
- `support`: tests for first-response deadlines that cross a weekend, after the Friday case failed in the 2026.3 freeze run.
- `auth`: tests for passkeys, and for the 3-minute clock skew limit on SAML assertions.
- `accounts` and `billing`: tests for the `ap-south` region (Enterprise only) and UPI payments from release 2026.4.

Overall line coverage rose by 1.3 percentage points in six months, from 88.4% to 89.7%, although the code base grew by about 900 lines.

## What are the gaps, and what is the plan?

| Gap | Risk | Plan | Owner | Target |
|-----|------|------|-------|--------|
| Export worker failure paths are untested | A stuck export is not noticed | Tests for a stopped worker and a lost lease; an upper time limit for exports | Accounts team | Release 2026.6 |
| Passkey sign-in has few tests | A sign-in bug could ship | Cover sign-in with user verification and removal of the last passkey | Identity team | Release 2026.6 |
| SAML refusal reasons are covered only for clock skew | Wrong error shown to Admins | One test per refusal reason, including an expired certificate | Identity team | Release 2026.7 |
| UPI and bank transfers are tested by hand | Payment bugs found late | Local fakes for UPI, ACH and SEPA | Billing team | End of 2026 |
| Branch coverage of `workspaces` is 72.5% | Error paths are not exercised | Review each `except` and each early return in the export code | Accounts team | Release 2026.6 |
| No test checks behaviour per region | A region can differ without notice | Integration tests that run against all three staging regions | Platform team | Release 2026.7 |

The plan has six items. The two that close the missed targets (export worker tests and passkey tests) are due in release 2026.6.

## How is coverage enforced?

- CI measures coverage on every merge to `main` and publishes the numbers per package.
- At the time of this report, a drop below target produced a warning but did not block the merge. That is how `workspaces` fell under 85% during the export rewrite without stopping any merge.
- Decision taken on 2026-07-02: from release 2026.6, a merge that lowers a package below its target is blocked unless the team lead of the owning team approves an exception with an end date.
- Files that contain only constants and type definitions, such as `common/enums.py`, are counted. Generated files are not.

## What should a reader take from this report?

- Overall coverage was good (89.7% of lines), but the average hid two weak spots.
- Both missed targets came from large new features: the export rewrite and passkeys.
- The weakest module, the export worker, was the cause of an incident three weeks after this measurement.

The next coverage report covers the second half of 2026 and is measured on 2026-11-03: `reports/coverage/2026-h2-coverage.md`.

Last reviewed: 2026-11-26
