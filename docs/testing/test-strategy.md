# Test Strategy

How Acme Cloud is tested: the levels, what each one covers, the rules for test data, and when a release is allowed to ship. The plan for a single release (for example `test-plan-2026.8.md`) builds on this page.

## Which test levels are there?

| Level | Where | Run by | When |
|-------|-------|--------|------|
| Unit | `tests/unit/<package>/` | CI, developers | Every commit |
| Integration | `tests/integration/` | CI, developers | Every commit |
| Manual suites | `docs/testing/manual/` | QA engineers | Each release, after code freeze |
| Chatbot evaluation | `eval/test-questions.md` | Documentation owner | After any change under `docs/` |

The levels overlap on purpose. A business rule such as "removing seats is credited on the next invoice" is checked as a unit test of the proration function, as an integration test of billing plus accounts, and as manual case `TC-BILL-014` in the dashboard.

## What do unit tests cover?

One package at a time, with no network and no database. The folder name matches the package under `src/acme_cloud/`:

| Folder | Package | Typical checks |
|--------|---------|----------------|
| `tests/unit/common/` | `common` | ID formats, money rounding, business-hours clock, error codes |
| `tests/unit/accounts/` | `accounts` | Plan limits, account state machine, roles and permissions |
| `tests/unit/workspaces/` | `workspaces` | Regions, export statuses, the 24-hour export timeout |
| `tests/unit/billing/` | `billing` | Proration, dunning days 1, 3, 7 and 14, refund approval limits |
| `tests/unit/auth/` | `auth` | Password rules, lockout windows, MFA, sessions, SSO clock skew |
| `tests/unit/api_keys/` | `api_keys` | Prefixes, hashing, scopes, expiry, rotate and revoke |
| `tests/unit/support/` | `support` | Priorities, first-response targets, escalation |
| `tests/unit/notifications/` | `notifications` | Recipients per template, idempotency key |
| `tests/unit/audit/` | `audit` | Event names, retention per plan, append-only rule |

Unit tests must check **boundary values** on both sides. Examples: a password of 11, 12, 128 and 129 characters; failed attempt number 4, 5, 9 and 10; a refund of $500.00 and $500.01; day 13, 14, 43 and 44 of dunning; day 30 and day 31 after closing an account.

## What do integration tests cover?

Flows that cross more than one package. They live in `tests/integration/` and carry the `integration` marker. Examples:

- A failed renewal (`billing`) moves the account to `past_due` (`accounts`), sends `payment_failed` (`notifications`) and later sets `read_only`.
- Removing a member (`accounts`) changes seats (`billing`) and writes `member.removed` and `seats.changed` (`audit`).
- Revoking a key (`api_keys`) writes `api_key.revoked` (`audit`) and queues the `api_key.revoked` webhook.
- A day-44 downgrade turns members over the Free limit into guests.

Integration tests still use in-memory stores and the fixed clock. They do not call a payment processor, an identity provider or a mail server.

## What do the manual suites cover?

What a person sees and clicks in the dashboard and the admin console, against a sandbox. There are six suites:

| Suite | File | IDs |
|-------|------|-----|
| Account and members | `docs/testing/manual/account-and-members.md` | `TC-ACCT-…` |
| Billing | `docs/testing/manual/billing.md` | `TC-BILL-…` |
| Security and SSO | `docs/testing/manual/security-and-sso.md` | `TC-SEC-…` |
| API keys | `docs/testing/manual/api-keys.md` | `TC-KEY-…` |
| Workspace and export | `docs/testing/manual/workspace-and-export.md` | `TC-WS-…` |
| Support and admin console | `docs/testing/manual/support-and-admin-console.md` | `TC-SUP-…` |

Each case has preconditions, numbered steps, an expected result with concrete values, and a priority (High, Medium or Low). Case IDs are never reused. A retired case keeps its number and is marked "Retired".

## What does the chatbot evaluation cover?

`eval/test-questions.md` holds "where do I click to…?" questions with expected answers. After a documentation change the docs are re-indexed and the questions are asked again. An answer passes when it gives the right menu path and the right value. This level tests the documentation, not the code. The file is not indexed, so the assistant cannot read the expected answers.

## What are the rules for test data?

1. **Fixed clock.** Tests never read the real time. The `clock` fixture in `tests/conftest.py` starts at **Monday 2026-01-05 09:00 UTC** and moves only with `advance(...)`.
2. **Seeded IDs.** The `ids` fixture uses seed **2026**, so the same IDs come out on every run.
3. **No real personal data.** No real names, addresses or phone numbers. People are named by role ("the Owner", "Admin A"). Email addresses use `@example.com`.
4. **Payment methods only as tokens.** A payment method appears as a `pm_` token such as `pm_9XK2M4QH7T`. Card numbers never appear in code, fixtures, test cases, logs or reports. Manual cases say "a valid test card from the sandbox processor".
5. **No secrets.** API keys in tests are generated in the test and never committed. Examples show only the prefix (`acme_test_`) and the last 4 characters.
6. **Fictional URLs.** Only `*.acme-cloud.example` hosts.
7. **Sandbox only for manual runs.** Manual suites run against sandbox accounts with `acme_test_` keys, never against production data.

## What are the entry criteria for release testing?

Manual testing of a release starts when all of these are true:

- Code freeze is declared and the release branch is cut.
- Unit and integration suites pass on the release branch.
- The test plan for the release is approved by the QA lead.
- A sandbox is deployed in each region the release ships to.
- Test accounts exist for each plan and role the plan needs.

## What are the exit criteria?

A release may ship when:

- **100%** of unit and integration tests pass. No test is skipped without a linked ticket.
- Coverage targets are met (see below).
- **100%** of High-priority manual cases in scope are run and pass.
- At least **95%** of Medium-priority cases in scope pass, and each failure has a ticket and an agreed fix date.
- No open **P1** or **P2** defect. P3 and P4 defects are listed in the release report.
- The chatbot evaluation is re-run if `docs/` changed.
- The sign-off roles in the test plan have signed.

## What is the coverage target?

Line coverage, measured in CI:

- **90%** for the `billing` and `auth` packages.
- **85%** for every other package.

A pull request that drops a package below its target fails CI. The higher target for `billing` and `auth` reflects the cost of a mistake there: wrong charges and wrong access.

## How do I run the tests?

From the repository root:

```text
python -m pip install -e ".[test]"
python -m pytest
```

Useful variations:

```text
python -m pytest tests/unit/billing          # one package
python -m pytest -m integration              # integration tests only
python -m pytest -m "not integration"        # unit tests only
python -m pytest -k proration                # tests whose name matches
```

`pyproject.toml` sets `testpaths = ["tests"]`, puts `src` on the Python path and registers the `integration` marker. Python **3.10 or newer** is required.

## How are test-run reports produced?

Each formal run produces one Markdown report in `reports/test-runs/`.

1. CI runs `python -m pytest` on the release branch and keeps the result summary and the coverage figures.
2. The QA engineer running a manual suite records each case as Pass, Fail, Blocked or Not run, with the defect ticket for each failure.
3. The QA lead combines both into one report: release, date, environment and region, commit, automated totals (passed, failed, skipped, duration), coverage per package, manual results per suite, open defects, and the go or no-go decision.
4. The report is committed with the release. Reports are not edited afterwards; a re-run gets a new report.

## Who owns which tests?

The team that owns a package owns its tests: Accounts team (`accounts`, `workspaces`), Billing team (`billing`), Identity team (`auth`, `api_keys`), Support Tools team (`support`, admin console), Platform team (`common`, `notifications`, `audit`). The QA lead owns the manual suites and this strategy.

## How do incidents feed back into testing?

Every incident follow-up adds a regression test at the lowest level that can catch it. Examples from 2026: the 24-hour export timeout after **INC-2026-004** (unit test plus `TC-WS-009`), and key revocation within 60 seconds in every region after **INC-2026-006** (`TC-KEY-011`).

Last reviewed: 2026-11-26
