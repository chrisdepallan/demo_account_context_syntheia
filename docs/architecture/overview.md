# Architecture Overview

This page describes how the Acme Cloud sample is put together: the packages, the teams that own them, how a request moves through the system, and how regions and deploys work. Business values (prices, limits, durations) are not repeated in full here; they live in `docs/reference/constants-and-glossary.md`.

## What are the main parts of the system?

Acme Cloud has three customer-facing entry points and one internal one:

- **Dashboard** at `https://app.acme-cloud.example`: the web app where users work and where Owners and Admins change settings.
- **REST API** at `https://api.acme-cloud.example/v1`: used by the dashboard and by customer integrations with API keys.
- **Auth service** at `https://auth.acme-cloud.example`: login, MFA, sessions and SSO (SAML 2.0 and OIDC).
- **Admin console** at `https://admin.acme-cloud.example`: staff only, used by support agents and on-call engineers.

Behind these entry points the business logic is split into nine Python packages under `src/acme_cloud/`.

| Package | What it does | Main modules |
|---------|--------------|--------------|
| `common` | Enums, error types, ID formats, clock, money | `enums.py`, `errors.py`, `ids.py`, `clock.py`, `money.py` |
| `accounts` | Accounts, plans, roles, the account state machine, members, invitations, ownership | `plans.py`, `permissions.py`, `state_machine.py`, `members.py`, `invitations.py`, `ownership.py`, `service.py` |
| `workspaces` | Workspaces, regions, storage limits, exports | `regions.py`, `storage.py`, `export.py`, `service.py` |
| `billing` | Subscriptions, proration, payment methods, invoices, dunning, refunds | `proration.py`, `subscriptions.py`, `payment_methods.py`, `invoices.py`, `dunning.py`, `refunds.py`, `service.py` |
| `auth` | Passwords, lockout, MFA, sessions, SSO, security policies | `passwords.py`, `lockout.py`, `mfa.py`, `sessions.py`, `sso.py`, `policies.py`, `service.py` |
| `api_keys` | Key creation, scopes, rotation, rate limits, webhooks | `scopes.py`, `service.py`, `rotation.py`, `rate_limit.py`, `webhooks.py` |
| `support` | Tickets, channels, SLA targets, escalation, conduct rules | `channels.py`, `sla.py`, `escalation.py`, `conduct.py`, `service.py` |
| `notifications` | Email templates, the outbox, recipient rules | `templates.py`, `outbox.py`, `recipients.py` |
| `audit` | Audit event types and the append-only log | `events.py`, `log.py` |

## Which team owns which package?

| Team | Owns | Typical questions |
|------|------|-------------------|
| Accounts team | `accounts`, `workspaces` | Roles, account states, exports, regions |
| Billing team | `billing` | Charges, invoices, dunning, refunds |
| Identity team | `auth`, `api_keys` | Login, MFA, SSO, API keys, webhooks |
| Support Tools team | `support`, admin console | Ticket SLAs, admin-console actions |
| Platform team | `common`, `notifications`, `audit`, infrastructure, on-call | Queues, regions, deploys, alerts |

The Platform team runs the on-call rota. The on-call engineer is the first responder for every alert and pulls in the owning team when a runbook says so. Runbooks are in `docs/runbooks/`.

## How does a request flow through the system?

A change made in the dashboard and a call made with an API key follow the same path.

1. **Dashboard or client** sends the request to the REST API. The dashboard sends the user's session; an integration sends `Authorization: Bearer <api key>`.
2. **Authentication.** The API asks the `auth` package to check the session, or the `api_keys` package to check the key hash, scopes and rate limit. A bad credential returns `ERR_UNAUTHENTICATED` (401). Too many requests return `ERR_RATE_LIMITED` (429) with `Retry-After`.
3. **Service call.** The API calls one function on the owning package's `service.py`. Each service is the only public entry point of its package.
4. **Checks inside the service**, always in this order:
   1. Account state. A `read_only`, `closed` or `deleted` account cannot be edited: `ERR_ACCOUNT_READ_ONLY` (423).
   2. Permission. The caller's role (or key scope) must allow the action: `ERR_PERMISSION_DENIED` (403).
   3. Plan. The feature must be on the plan (`ERR_PLAN_REQUIRED`, 403) and under the plan limit (`ERR_LIMIT_EXCEEDED`, 409).
   4. Input validation: `ERR_VALIDATION` (400).
5. **The work itself**, for example adding a seat or starting an export.
6. **Side effects.** The service records an audit event through its `audit` collaborator and queues emails through its `notifier` collaborator. Both are optional: a service built without them still works, which keeps unit tests small.
7. **Response.** Errors are subclasses of `AcmeError` in `src/acme_cloud/common/errors.py`. Each carries a stable code and an HTTP status, and the API returns its `to_dict()` body.

Every service takes a `Clock` (see `src/acme_cloud/common/clock.py`). No module reads the system time directly. Tests use `FixedClock` and move time forward to reach day 14 or day 44 of the dunning timeline.

## How do the packages depend on each other?

Dependencies point downward only. A package may import from packages below it, never from packages above it or beside it unless an arrow is shown.

```text
                     Dashboard / REST API / Admin console
                                    |
      +-----------+---------+-------+-------+-----------+
      |           |         |               |           |
  workspaces   billing     auth         api_keys     support
      |           |         |               |           |
      +-----------+---------+-------+-------+-----------+
                                    |
                                accounts
                    (plans, permissions, state machine)
                                    |
                  +-----------------+-----------------+
                  |                 |                 |
            notifications         audit            common
              (outbox)        (append-only)   (enums, errors, IDs,
                  |                 |           clock, money)
                  +--------> common <---------+
```

Rules that follow from the diagram:

- `accounts` knows nothing about billing, auth or support. Billing asks `accounts` to change an account's state; it never writes the state itself (see `adr/0003-account-state-machine-lives-in-the-accounts-module.md`).
- Plan prices, limits and feature gates are read from `src/acme_cloud/accounts/plans.py`. No other package hard-codes them.
- `notifications` and `audit` depend only on `common`. Services receive them as collaborators, so they can be replaced with fakes.
- `common` imports nothing from the other packages.

## How are regions set up?

There are three data regions: `us-east` (Virginia, all plans, the default), `eu-central` (Frankfurt, Business and Enterprise) and `ap-south` (Mumbai, Enterprise). A workspace's region is chosen at creation and never changes (see `adr/0002-workspace-region-is-fixed-at-creation.md`).

- Each region runs its own dashboard, API and auth nodes, worker queues, and a primary database with one standby replica in a second availability zone.
- Workspace content (projects, files, exports) stays in the workspace's region.
- Account, billing and identity records are global. Their primary copy is in `us-east`, and the other regions keep read copies.
- Configuration is the same in all regions. Values that must never differ between regions, such as the 60-second API key cache lifetime, are constants in code and not configuration. This rule came out of INC-2026-006.

If a region's primary database fails, the standby replica is promoted inside the same region. Data never moves to another region during a failover. See `docs/runbooks/region-failover.md`.

## In what order are releases deployed?

Releases are named `<year>.<number>`, for example `2026.8`. A release goes to `us-east` first. `eu-central` and `ap-south` follow one business day later, if `us-east` has run for that day without a P1 or P2 incident caused by the release. A release that is rolled back in `us-east` is not deployed to the other two regions.

The 2026 releases and incidents are listed in `docs/reference/release-and-incident-index.md`.

## What is deliberately out of scope in this sample?

The repository is a documentation and test corpus, not a running product. The code keeps the business rules real and leaves the infrastructure out.

- **No database.** Everything is held in memory in Python dictionaries and lists.
- **No HTTP layer.** There is no web server; the "API" is the set of `service.py` functions and the error codes they raise.
- **No real payment processor.** Charges are simulated. Payment methods are opaque tokens such as `pm_9XK2M4QH7T`.
- **No real email.** The outbox records what would be sent and to whom.
- **No real cryptography for SSO.** Signature and clock-skew checks are modelled, not performed against a live identity provider.
- **No third-party packages.** Only the Python standard library is used.
- **No real customers.** All names, prices, IDs and URLs are fictional.

## Where do I read more?

- Entities and IDs: `docs/architecture/data-model.md`
- Account states and timelines: `docs/architecture/account-state-machine.md`
- Decisions and their reasons: `docs/architecture/adr/`
- What to do when something breaks: `docs/runbooks/`
- What the customer sees: `docs/ui/README.md`

Last reviewed: 2026-11-26
