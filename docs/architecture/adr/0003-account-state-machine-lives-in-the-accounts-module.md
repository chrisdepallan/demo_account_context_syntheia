# ADR 0003: Account state machine lives in the accounts module

## Status

Accepted.

## Date

2025-03-18

## Context

An account has six states: `trialing`, `active`, `past_due`, `read_only`, `closed` and `deleted`. Several parts of the system want to change the state:

- billing, when a charge fails or a balance is paid;
- the dunning job, on day 14 and day 44;
- the Owner, when closing or restoring the account;
- scheduled jobs, when a trial ends or when day 31 after closure arrives.

Many more parts need to read the state. Every service that edits anything must refuse to do so in `read_only`, `closed` or `deleted`, and login must refuse `closed` and `deleted` accounts.

In the first prototype the state was a plain field, and both the billing code and the accounts code assigned to it. Two bugs appeared within weeks. An account closed by its Owner was moved back to `active` by a late payment confirmation. And an account restored from `closed` always came back as `active`, even if it had been `read_only` before closure, which gave unpaid accounts a free way out of read-only mode.

## Decision

The account state and its transition table live in one place: `src/acme_cloud/accounts/state_machine.py`, owned by the Accounts team.

- The module holds the full list of allowed transitions. A request for any other transition is refused with `ERR_CONFLICT`.
- No other package assigns the state. Billing, auth, workspaces and support call the `accounts` package to ask for a transition, giving the reason.
- The state before closure is remembered on the account, so that a restore within 30 days returns to that state.
- The same module answers the two read questions, "can users edit?" and "can users log in?". They are defined once on the `AccountState` enum in `src/acme_cloud/common/enums.py`.
- Each successful transition is announced in one place: the `account.state_changed` webhook event, and the audit events `account.closed` and `account.restored` where they apply.

The dependency goes one way: `billing` imports `accounts`; `accounts` never imports `billing`.

## Alternatives considered

### Keep the state in the billing package

Most transitions (four of the ten) are caused by payments, so billing could own the field.

Rejected because closure, restore, deletion and trial expiry are not billing events, and Free accounts have a state but nothing to bill. The accounts package would have to import billing just to close an account, creating a circular dependency between the two most-changed packages.

### Let every package write the state directly, with a shared helper for validation

Each package would call a small `validate_transition` function and then set the field itself.

Rejected because this is how the prototype bugs happened. A helper that callers may forget is weaker than a single writer. It also scatters the side effects: every writer would need to remember the webhook, the audit event and the "previous state" bookkeeping.

### A separate lifecycle package between accounts and billing

A new top-level package would own only the state machine.

Rejected as too much structure for one small table of ten transitions. The state is an attribute of the account, and the Accounts team already owns the account record. A new package would also need a new owner.

## Consequences

Good:

- The transition table can be read and tested in one file. The documentation in `docs/architecture/account-state-machine.md` mirrors it row for row.
- Illegal transitions fail loudly instead of quietly corrupting an account. A payment confirmation for a `closed` account is recorded on the invoice but does not reopen the account.
- Restore returns to the previous state, so closing and restoring cannot be used to escape `past_due` or `read_only`.
- Webhook and audit side effects cannot be forgotten, because there is one writer.

Costs:

- Billing changes that need a new transition require a change in the accounts package and a review from the Accounts team. This is deliberate, but it slows billing work down.
- The accounts package must stay free of billing concepts. It knows that "the balance was paid" is a reason for a transition, but not what an invoice is. Reasons are passed in as plain values.
- The dunning day counter lives in billing (`src/acme_cloud/billing/dunning.py`), while the state lives in accounts. When the two disagree, for example a paid invoice with the account still `past_due`, someone must reconcile them. That case has its own runbook: `docs/runbooks/account-stuck-in-past-due.md`.
- The rule added after INC-2026-002, that processor outages do not count as dunning failures, is implemented in billing. The state machine did not change: billing simply does not ask for the `active` to `past_due` transition during an outage.

## Related

- Code: `src/acme_cloud/accounts/state_machine.py`, `src/acme_cloud/accounts/service.py`, `src/acme_cloud/billing/dunning.py`, `src/acme_cloud/common/enums.py`
- Architecture: `docs/architecture/account-state-machine.md`, `docs/architecture/overview.md` ("How do the packages depend on each other?")
- ADR: `docs/architecture/adr/0006-dunning-schedule-of-days-1-3-7-and-14.md`
- UI: `docs/ui/settings-billing.md` ("What does the account look like when a payment fails?"), `docs/ui/settings-account.md`
- Runbooks: `docs/runbooks/account-stuck-in-past-due.md`, `docs/runbooks/payment-processor-outage.md`
- Incident: `reports/incidents/INC-2026-002-payment-processor-outage.md`

Last reviewed: 2026-11-26
