# demo_account_context_syntheia

A sample repository about one fictional product, **Acme Cloud**, built to test how well the MCP documentation server handles a larger repo. It holds about 200 files and 1.2 MB: dashboard UI docs, engineering docs, Python modules with unit tests, and reports.

It is written to be indexed, so an AI assistant can answer questions such as "where do I click to…?", "what happens on day 14 after a failed payment?" or "what caused INC-2026-004?".

> All names, prices, URLs, incidents and numbers are fictional. No credentials or real customer data are stored in this repo.
>
> The UI docs in `docs/ui/` follow the `demo_account_context@main` library (accounts, billing, auth and support service docs). Inside this repo, every business value is defined once in `docs/reference/constants-and-glossary.md`; code, tests, docs and reports repeat those values.

## What this repo is for

- Indexed as one or more libraries on branch `main`.
- Each Markdown file is split at its headings, so every `##` section is a searchable answer.
- The Python files carry the business rules in docstrings and named constants, so they can be indexed as documentation too.
- The mix of Markdown, code, tests and reports shows how the server copes with size, with non-Markdown files and with the same topic appearing in several places.

## Repository layout

| Path | Files | Contents |
|------|-------|----------|
| `README.md` | 1 | This file |
| `CHANGELOG.md` | 1 | Releases 2026.1 to 2026.8 and the 2026 incidents |
| `CONTRIBUTING.md` | 1 | Rules for docs, code, tests and data safety |
| `docs/reference/` | 2 | `constants-and-glossary.md` (every plan, limit, duration, role, ID format and error code) and `release-and-incident-index.md` |
| `docs/ui/` | 17 | Customer-facing dashboard docs (see below) |
| `docs/architecture/` | 12 | System overview, data model, account state machine and 9 ADRs in `adr/` |
| `docs/runbooks/` | 10 | Step-by-step guides for on-call engineers and support agents |
| `docs/testing/` | 8 | Test strategy, test plan for release 2026.8 and 6 manual test suites in `manual/` |
| `src/acme_cloud/` | 60 | Python packages: `common`, `accounts`, `workspaces`, `billing`, `auth`, `api_keys`, `support`, `notifications`, `audit` |
| `tests/unit/` | 55 | pytest unit tests, one folder per package (1,188 tests) |
| `reports/` | 31 | `incidents/`, `releases/`, `test-runs/`, `coverage/`, `quarterly/`, `security/`, `performance/` |
| `tools/repo_stats.py` | 1 | Prints files and size per folder, and the Markdown heading count |
| `pyproject.toml` | 1 | pytest configuration |

### Dashboard UI docs in `docs/ui/`

| File | Contents |
|------|----------|
| `README.md` | Dashboard overview, navigation map, key UI concepts |
| `login-and-profile.md` | Login page, password reset, lockouts, **Profile → Security** |
| `onboarding-and-trial.md` | Sign-up, the 14-day Pro trial, first-run checklist |
| `settings-account.md` | **Settings → Account**: transfer ownership, close account |
| `settings-members.md` | **Settings → Members**: invite, remove, reset MFA, roles |
| `settings-workspace.md` | **Settings → Workspace**: export, regions |
| `settings-billing.md` | **Settings → Billing**: plan, seats, payment method, invoices |
| `settings-security.md` | **Settings → Security**: SSO, MFA policy, session rules |
| `sso-setup-walkthrough.md` | Longer SAML and OIDC setup guide with common errors |
| `settings-api-keys.md` | **Settings → API keys**: create, rotate, revoke |
| `audit-log.md` | **Settings → Audit log**: events, filters, CSV, retention |
| `storage-and-usage.md` | **Settings → Usage**: storage, seats, limits |
| `notifications.md` | **Profile → Notifications** and every email the product sends |
| `help-and-support.md` | In-app chat, help center, status page |
| `troubleshooting.md` | Symptom-to-fix page, including error codes |
| `feature-availability.md` | Which UI controls appear on which plan and for which role |
| `internal/admin-console.md` | Internal admin console used by support agents |

## Recommended index globs

Customer-facing library (what an end-user assistant may see):

```text
README.md
docs/ui/**
```

Exclude `docs/ui/internal/**` from this library.

Engineering library (the full corpus, for the large-repo test):

```text
README.md
CHANGELOG.md
CONTRIBUTING.md
docs/**
src/**
tests/**
reports/**
```

The runbooks, the admin console doc, the incident reports and the security reports are internal. Keep them out of the customer-facing library. Access is all-or-nothing per library, so internal content needs its own restricted library.

## Running the tests and measuring the repo

```text
python -m pip install pytest
python -m pytest
python tools/repo_stats.py --headings
```

The code needs Python 3.10 or later and uses only the standard library.

## Keeping the index fresh

- There is no auto-sync. Re-index after merging any change to `main`.
- When a value changes, change it in `docs/reference/constants-and-glossary.md` first, then in every file that repeats it.
- When a source doc in `demo_account_context` changes, update the matching page in `docs/ui/` too.
- Update the "Last reviewed" line at the bottom of a doc when you change it.

## Known gaps

- Some docs and reports link to `docs/modules/`, `docs/api/`, `tests/integration/` and `eval/test-questions.md`. These do not exist yet.
- The reports were written in parallel and have not had a full consistency check against each other.

## Contributing

See `CONTRIBUTING.md`. In short:

1. Use one topic per `##` heading, and phrase headings the way users ask (for example "## How do I invite a member?").
2. Write menu paths in bold with arrows, for example **Settings → Billing → Invoices**.
3. Put concrete values (durations, limits) in the text, not only in tables or screenshots.
4. Never commit secrets or real customer data. The secret filter only skips files by name, so a key pasted into a Markdown or Python file is still indexed.
