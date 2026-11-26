# INC-2026-002: Payment Processor Outage

Blameless postmortem. All data is fictional sample data for Acme Cloud.

| Field | Value |
|-------|-------|
| Incident ID | INC-2026-002 |
| Date | 2026-03-19 (Thursday) |
| Priority | P1 |
| Duration | 47 min (14:08 to 14:55 UTC) |
| Regions | All regions at that time: `us-east`, `eu-central` |
| Customers affected | 565 accounts (391 through automatic charges, 174 through payments made in the dashboard) |
| Detected by | Automated alert on the card payment failure rate (14:11 UTC) |
| Owning team | Billing team |
| Incident commander | On-call engineer (Platform team) |

## What happened?

On 2026-03-19 the external payment processor had an outage. From 14:08 to 14:55 UTC every card payment failed in all regions.

Acme Cloud had no fallback processor. The larger problem was inside the product: the billing code treated each failed attempt as a normal card decline. Renewals that failed moved accounts to `past_due`. Dunning retries that failed were counted as used. Nine accounts were moved to `read_only` because their day-14 retry ran during the outage.

## What was the customer impact?

565 accounts were affected in two groups.

**Automatic charges: 391 accounts**

| Effect | Accounts |
|--------|----------|
| Renewal or seat charge failed; account wrongly moved from `active` to `past_due` | 326 |
| Already `past_due`; one of the four dunning retries (days 1, 3, 7, 14) was used up | 56 |
| Day-14 retry failed; account wrongly moved to `read_only` | 9 |

- All 391 accounts received a `payment_failed` email. It went to the Owner, the Billing admins and the billing contacts.
- The 9 `read_only` accounts could log in but could not edit. The longest time in `read_only` was 1 h 14 min.

**Payments made in the dashboard: 174 accounts**

- 212 attempts failed with `ERR_PAYMENT_FAILED` (HTTP 402). These were upgrades, added seats and card updates under **Settings → Billing → Payment method → Update**.
- The card update failed because the temporary $0 authorization could not be made.

No customer was charged twice. No payment data was exposed. Payment methods are stored only as processor tokens.

## What is the timeline?

All times are UTC on 2026-03-19 unless a date is given.

| Time | Event |
|------|-------|
| 14:08 | The processor starts to answer with errors and timeouts. First failed charge. |
| 14:11 | Detection. The alert "card payment failure rate above 25% for 3 minutes" pages the on-call engineer. |
| 14:14 | The on-call engineer acknowledges, sees a failure rate of 100% and declares a P1 incident. |
| 14:17 | The processor's own status page confirms an outage. |
| 14:20 | Status page post on `https://status.acme-cloud.example`: "Card payments are failing. Your data and access are not affected." This is 12 minutes after the start and inside the 15-minute target for P1. |
| 14:24 | A Billing team engineer joins the incident channel. |
| 14:31 | Decision to pause the renewal job and the dunning retry job. No switch exists, so a configuration deploy is prepared. |
| 14:39 | Mitigation. Both jobs are paused. No more automatic charges fail after this time. |
| 14:55 | The processor recovers. Payments in the dashboard succeed again. End of the outage. |
| 15:02 | Status page updated to "Monitoring". |
| 15:10 | The renewal job is resumed. Failed renewals are charged again. |
| 15:25 | The 9 `read_only` accounts are set back to `past_due` by hand, with their day-14 retry restored. |
| 16:40 | The re-run of charges is complete. 318 of the 326 renewals succeed. The other 8 are real declines and stay `past_due` with day 0 set to 2026-03-19. |
| 17:30 | Status page updated to "Resolved". |
| 2026-03-20 11:00 | Cleanup complete. Dunning retry counts are restored for the 56 accounts. A correction email is sent to all 391 accounts. |

## What was the root cause?

The trigger was outside Acme Cloud: the payment processor was unavailable for 47 minutes.

The root cause of the customer impact was in `src/acme_cloud/billing/dunning.py`. The code had one failure path. A timeout or a server error from the processor was handled in the same way as a card that was declined. The code therefore:

- moved accounts to `past_due` on day 0,
- counted a dunning retry as used,
- moved accounts to `read_only` when the day-14 retry failed,
- sent the `payment_failed` email.

There was no check for "the processor is down" and no fallback.

## Why was it not caught earlier?

- The dunning tests used two processor answers: success and decline. No test used a processor that was unreachable.
- The dunning schedule of days 1, 3, 7 and 14 (ADR 0006) was designed around card declines. Outages were not part of the design discussion.
- The processor had not had an outage longer than 5 minutes in the previous 12 months, so the gap was never seen in production.
- No runbook existed for a processor outage.

## What went well?

- The alert fired 3 minutes after the first failure. The on-call engineer acknowledged it 3 minutes later.
- The status page post was published 12 minutes after the start.
- The `read_only` accounts were corrected first, 30 minutes after the processor recovered.
- The decision to re-charge renewals automatically avoided 318 customers having to act.

## What went badly?

- Pausing the two jobs took 8 minutes because it needed a configuration deploy. During those 8 minutes more accounts were moved to `past_due`.
- 391 accounts received a `payment_failed` email that was wrong. The correction email was sent the next day, about 20 hours later.
- Restoring dunning retry counts was manual work in the database and took until 2026-03-20.
- Support learned about the incident from the status page, not from the incident channel. 44 tickets arrived before support had a reply text.

## What are the action items?

| Action | Owning team | Due date | Status | Shipped in |
|--------|-------------|----------|--------|------------|
| Processor outages are detected and do not count as dunning failures. Charges are held and tried again after recovery. | Billing team | 2026-04-14 | Done | 2026.3 |
| Write the runbook `docs/runbooks/payment-processor-outage.md`. | Billing team | 2026-04-14 | Done | 2026.3 |
| Add a switch that pauses the renewal and dunning jobs without a deploy. | Billing team | 2026-04-14 | Done | 2026.3 |
| Add automated tests for processor timeouts and server errors in renewals and in each dunning retry. | Billing team | 2026-04-14 | Done | 2026.3 |
| Add support to the P1 paging list so that a reply text is ready with the status page post. | Platform team | 2026-03-27 | Done | Not tied to a release |
| Review a second payment processor as a fallback. | Billing team | 2026-06-30 | Closed, not planned | Not tied to a release |

The first two rows are the follow-up listed in `docs/reference/release-and-incident-index.md`. The fallback processor was reviewed and not pursued; holding charges during an outage removes the customer impact at a much lower cost.

## How does outage detection work since 2026.3?

- A processor answer is put into one of two groups: **decline** (the card was refused) or **unavailable** (timeout or server error).
- An unavailable answer does not change the account state, does not use a dunning retry and does not send `payment_failed`.
- When 10 unavailable answers in a row are seen within 2 minutes, the billing module marks the processor as down. Automatic charges are held and tried again when a test call succeeds.
- Payments made in the dashboard show a message that asks the user to try again later.

## What is related?

- Runbook: `docs/runbooks/payment-processor-outage.md`
- Code module: `src/acme_cloud/billing/dunning.py`
- Release that shipped the fix: `reports/releases/2026.3.md`
- Architecture decisions: ADR 0004 (payment methods as processor tokens only) and ADR 0006 (dunning schedule) in `docs/architecture/adr/`
- Index: `docs/reference/release-and-incident-index.md`
- UI doc: `docs/ui/settings-billing.md`

Last reviewed: 2026-11-26
