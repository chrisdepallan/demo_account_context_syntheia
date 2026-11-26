# INC-2026-001: Duplicate Invoice Emails to Billing Contacts

Blameless postmortem. All data is fictional sample data for Acme Cloud.

| Field | Value |
|-------|-------|
| Incident ID | INC-2026-001 |
| Date | 2026-02-11 (Wednesday) |
| Priority | P2 |
| Duration | 3 h 10 min (09:05 to 12:15 UTC) |
| Regions | `us-east`, `eu-central` |
| Customers affected | 412 accounts; 1,263 billing contact addresses received a second copy |
| Detected by | Customer reports to support (first ticket at 09:52 UTC) |
| Owning team | Platform team (owns `notifications`) |
| Supporting team | Billing team |

## What happened?

On 2026-02-11 the daily invoice run sent the `invoice_ready` email twice to billing contacts. Between 09:05 and 12:15 UTC, 1,263 billing contact addresses in 412 accounts received two identical emails for the same invoice.

Owners and Billing admins received the email once, as expected. No invoice was created twice and no customer was charged twice. Only the email was duplicated.

Billing contacts were new. They shipped three weeks earlier in release 2026.1 (2026-01-20), which added a second send step to the `invoice_ready` notification.

## What was the customer impact?

- 412 accounts were affected. Each had at least one billing contact under **Settings → Billing → Billing contacts**.
- 1,263 addresses received a second copy of an invoice email. No address received more than two copies.
- 19 support tickets were opened. Most asked the same question: "Was I charged twice?" The answer in every case was no.
- 3 customers reported that their accounts-payable system had created a second payable from the duplicate email. Support confirmed in writing that one invoice existed.
- No refunds were needed, because no duplicate charge happened.
- No data was exposed. Each duplicate went to an address that was already entitled to receive the invoice.

## What is the timeline?

All times are UTC on 2026-02-11.

| Time | Event |
|------|-------|
| 09:00 | The daily invoice run starts. It creates invoices and queues `invoice_ready` notifications in the outbox. |
| 09:05 | The email provider starts answering slowly. The first billing-contact send step passes the 30-second worker timeout and is retried. The first duplicates are sent. |
| 09:52 | First support ticket: a billing contact reports two identical invoice emails. |
| 10:20 | Fourth ticket with the same report. The support team lead sees the pattern and pages the on-call engineer. |
| 10:26 | The on-call engineer declares a P2 incident and opens the incident channel. |
| 10:48 | Outbox logs confirm that the contact send step ran twice for the same invoices. |
| 11:05 | The Billing team confirms that invoices and charges are not duplicated. Support receives a reply text for open tickets. |
| 11:40 | Mitigation: retries are switched off for the billing-contact step of `invoice_ready`. New duplicates stop being queued. |
| 12:15 | The last retry that was already scheduled is sent. No duplicates after this time. Incident resolved. |
| 14:30 | The on-call engineer confirms the count: 1,263 duplicates in 412 accounts. |

On 2026-02-12 the Billing team emailed the Owner of each affected account to explain the duplicate and to confirm that one invoice and one charge existed.

## What was the root cause?

The retry in the notification queue was not idempotent.

The `invoice_ready` notification had two send steps after release 2026.1:

1. Send to the Owner and Billing admins.
2. Send to the billing contacts (up to 5 extra addresses).

The outbox worker in `src/acme_cloud/notifications/outbox.py` marked a step as done only when the email provider answered. On 2026-02-11 the provider accepted the messages but answered after more than 30 seconds. The worker treated the step as failed and retried it. The retry sent the same emails again, because nothing recorded that those emails had already been accepted.

Step 1 was not affected. Its batches were smaller and stayed under the 30-second timeout.

## Why was it not caught earlier?

- The tests for billing contacts in 2026.1 covered a provider that answers quickly and a provider that rejects the send. They did not cover a provider that accepts the send but answers late.
- The test run at the code freeze on 2026-01-13 wrote the gap down: "the invoice email has no protection against being sent twice if the notification queue retries a send". It was accepted as a risk and not treated as a blocker. See `reports/test-runs/2026-01-13-release-2026.1.md`.
- The retry logic was older than billing contacts. It was written when a notification had one small send step, so a late answer was rare.
- There was no alert on "same template, same recipient, same object sent more than once".
- The provider's slow responses did not count as errors, so the email error-rate alert stayed green.

## What went well?

- Support noticed the pattern after four tickets and paged the on-call engineer directly.
- The Billing team proved within 39 minutes of the incident being declared that no charge was duplicated. That fact went into every customer reply.
- The mitigation was a configuration switch and needed no code deploy.
- The follow-up email to Owners went out the next day and closed most tickets without further questions.

## What went badly?

- Detection depended on customers. The first duplicate was sent at 09:05 and the incident was declared at 10:26, 81 minutes later.
- Turning off retries did not cancel retries that were already scheduled. Duplicates continued for 35 minutes after the mitigation.
- Between 11:40 and the release of the fix, the billing-contact step had no retry at all. A real provider failure in that period would have meant missed emails. This was accepted as the smaller risk and none occurred.
- Support had no saved reply for "duplicate email, single charge" and wrote one during the incident.

## What are the action items?

| Action | Owning team | Due date | Status | Shipped in |
|--------|-------------|----------|--------|------------|
| Notification sends carry an idempotency key built from template + recipient + object ID. A send with a key that was already accepted is skipped. | Platform team | 2026-03-03 | Done | 2026.2 |
| Add an automated test for "provider accepts the send but answers after the timeout". | Platform team | 2026-03-03 | Done | 2026.2 |
| Turn retries back on for the billing-contact step once the idempotency key is live. | Platform team | 2026-03-04 | Done | 2026.2 |
| Two alerts on the outbox: `outbox-duplicates-blocked` (more than 100 duplicate sends refused in 10 minutes) and `outbox-duplicate-sent` (two sends with the same key both recorded as delivered). | Platform team | 2026-03-03 | Done | 2026.2 |
| Write the runbook `docs/runbooks/duplicate-notifications.md`, including how to pause one template without pausing the whole outbox. | Platform team | 2026-03-03 | Done | 2026.2 |
| Add a saved support reply for duplicate notification emails. | Support Tools team | 2026-02-18 | Done | Not tied to a release |

The first row is the follow-up listed in `docs/reference/release-and-incident-index.md`.

## How does the idempotency key work?

The key is the template key, the recipient address and the object ID joined together. For an invoice email the object ID is the invoice ID, for example `INV-2026-004812`.

- The outbox stores the key when the provider accepts the send.
- Before any send or retry, the worker looks up the key. If it exists, the send is skipped and logged as "already sent".
- A resend that is requested on purpose, such as an invitation resend, uses a new object ID and is not blocked.

This applies to all 14 email templates, not only `invoice_ready`.

## What is related?

- Runbook: `docs/runbooks/duplicate-notifications.md`
- Test run at the code freeze of 2026.1: `reports/test-runs/2026-01-13-release-2026.1.md`
- Code module: `src/acme_cloud/notifications/outbox.py`
- Release that introduced billing contacts: `reports/releases/2026.1.md`
- Release that shipped the fix: `reports/releases/2026.2.md`
- Index: `docs/reference/release-and-incident-index.md`
- UI doc for billing contacts: `docs/ui/settings-billing.md`

Last reviewed: 2026-11-26
