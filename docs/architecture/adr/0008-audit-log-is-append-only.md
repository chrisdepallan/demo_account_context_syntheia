# ADR 0008: Audit log is append-only

## Status

Accepted.

## Date

2025-09-16

## Context

The audit log answers the question "who did what, and when?" for an account. Customers on Pro and above use it to investigate security events: a member removed, a role changed, an API key created, SSO turned off. Support and on-call engineers use it for the same reasons, for example to see what a leaked API key was used for.

A log used for investigations is only worth something if it can be trusted. The people most likely to want an entry changed or removed are the people whose actions it records: an Admin who removed a colleague by mistake, or an attacker who has taken over an Admin login and wants to hide it. Staff are in the same position: a support agent who resets MFA or issues a refund should not be able to erase the trace.

Retention depends on the plan: none on Free and Starter, 90 days on Pro, 1 year on Business and 7 years on Enterprise.

## Decision

The audit log is **append-only**. Events can be added and read. They cannot be changed, and they cannot be deleted before their retention period ends.

- The log offers two operations to the rest of the system: record an event, and query events. There is no update and no delete, in code, in the API or in the admin console.
- Each event has an ID such as `evt_3G7H2K9M4P6Q` and stores the event type, the actor, the account, the workspace if any, the time in UTC, and a small metadata object.
- The actor is always recorded, including when the actor is a support agent or an automatic job.
- The only removal is the retention purge. It deletes events older than the plan's retention period and nothing else.
- A mistake in an event is corrected by recording a new event, never by editing the old one.
- Reading the log needs the `audit.read` permission, which the Owner and Admins hold.
- The metadata object never contains secrets: no passwords, no full API keys, no MFA codes, no card numbers. For an API key it holds the key ID and the last 4 characters.

The recorded event types are listed in `docs/reference/constants-and-glossary.md`, section "Which audit events are recorded?". The code is in `src/acme_cloud/audit/log.py` and `src/acme_cloud/audit/events.py`.

## Alternatives considered

### An editable log with "soft delete"

Admins, or only support, could hide or correct entries, with the change itself logged.

Rejected because a log that can be edited needs a second log to be trusted, and then the same question applies to that one. Hidden entries are also exactly what an attacker with an Admin login would use. The honest need behind this option, fixing a wrong entry, is met by adding a correcting event.

### Use the application logs as the audit trail

Services already write technical logs. Customers could be given a filtered view of them.

Rejected because technical logs serve engineers: their format changes with every release, they are kept for days and not years, they mix all customers together, and they are routinely trimmed and sampled. An audit trail needs stable event names, a per-account view and a retention promise.

### Let Owners delete their account's audit history on request

Some customers ask for "everything about us" to be removed while the account stays open.

Rejected because the log protects members of the account from each other, and the Owner is one of the actors it records. Deletion of the whole account still removes everything: when a closed account becomes `deleted` on day 31, its audit events go with it.

## Consequences

Good:

- Customers and staff can rely on the log during an investigation. If an event is there, it happened; if an action is on the recorded list, there is an event for it.
- The module is small. With no update or delete, there are few ways for it to go wrong.
- Staff actions are visible to the customer. A support MFA reset appears as `mfa.reset` with a support actor, and a refund appears as `refund.issued`.
- The filters and CSV download added in release 2026.6 are read-only views over the same events and needed no change to how events are stored.

Costs:

- Storage only grows until the purge catches up. Enterprise accounts keep events for 7 years.
- A wrong or embarrassing entry stays visible for the whole retention period. Support cannot remove it and must say so plainly.
- Because nothing can be edited, care is needed about what goes into the metadata in the first place. Anything written there stays for up to 7 years. This is why metadata is kept small and free of secrets and personal details beyond the actor.
- Free and Starter accounts have no audit log. Events are not recorded for them, so upgrading to Pro does not reveal past history; the log starts on the day of the upgrade.
- Services must record the event as part of the action. If the audit collaborator is left out, as it may be in unit tests, the action still succeeds and no event is written. In production wiring the audit log is always present.

## Related

- Code: `src/acme_cloud/audit/log.py`, `src/acme_cloud/audit/events.py`, `src/acme_cloud/accounts/plans.py` (retention days per plan)
- Rules: `docs/reference/constants-and-glossary.md`, sections "Which audit events are recorded?" and "What are the plan limits?"
- Architecture: `docs/architecture/data-model.md` ("How long is each kind of data kept?")
- UI: `docs/ui/feature-availability.md` (audit log by plan), `docs/ui/settings-api-keys.md` ("How do I revoke a leaked key?")
- Runbooks that rely on the log: `docs/runbooks/leaked-api-key.md`, `docs/runbooks/mfa-reset-for-locked-out-owner.md`, `docs/runbooks/unreachable-owner-transfer.md`
- Release: `reports/releases/2026.6.md` (filters, CSV download, 7-year retention on Enterprise)

Last reviewed: 2026-11-26
