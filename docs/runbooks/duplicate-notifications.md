# Runbook: Duplicate Notifications

**For:** support agents (recognising and reporting duplicates) and the on-call engineer (stopping them).

This runbook grew out of INC-2026-001 (2026-02-11, P2, 3 hours 10 minutes). Invoice emails were sent twice to billing contacts. A retry in the notification queue was not idempotent: when a send timed out, the queue sent the email again, although the first attempt had in fact gone out. Since release 2026.2, every notification carries an idempotency key built from the template, the recipient and the object ID, and the outbox refuses to send the same key twice.

## What are the symptoms?

- Customers report getting the same email two or more times within minutes: the same invoice, the same export, the same warning.
- Billing contacts ask whether they were charged twice. Two `invoice_ready` emails look like two invoices, and this is what made INC-2026-001 a P2.
- The alert `outbox-duplicates-blocked` fires. It fires when the outbox refuses more than 100 duplicate sends in 10 minutes. The refusals mean the protection is working, but something upstream is retrying far too often.
- The alert `outbox-duplicate-sent` fires. It fires when two sends with the same idempotency key are both recorded as delivered. This should be impossible and is always an incident.

## Which repeated emails are normal?

Some emails are meant to arrive more than once. Check this list before treating a report as a fault.

| Template | Why it can repeat |
|----------|-------------------|
| `payment_failed` | Sent on day 0 and after each failed retry (days 1, 3, 7 and 14): up to five emails for one invoice, on different days |
| `invitation` | Sent again each time an Admin selects **Resend** |
| `password_reset` | Sent each time the user selects **Forgot password** |
| `storage_warning` | Sent again if usage falls below 90% and later rises above it |
| `invoice_ready` | One per invoice. A seat change in the middle of a period creates its own invoice, so two invoices in one day are possible |
| Any template | The Owner who is also a billing contact with the same address gets one copy; with a different address they get one copy at each address |

A real duplicate has the same template, the same recipient address and the same object (the same invoice ID, export ID and so on), and the copies arrive minutes apart, not days apart.

## How do I confirm a duplicate?

1. Ask the customer for the subject line, the address that received the email, and the times of both copies. Do not ask them to forward invoices with payment details.
2. Open **Admin console → Account → Notifications**. It lists every send for the account for the last 30 days with template, recipient, object ID, idempotency key, time and result.
3. Filter by the template and the recipient.
4. Read the result:

| What the list shows | Meaning |
|---------------------|---------|
| One send with result "delivered" | We sent it once. The copy was made by the customer's mail system, often a forwarding rule or a shared mailbox. |
| Two sends with different object IDs | Two different things happened, for example two invoices. Not a duplicate. |
| One "delivered" and one or more "blocked (duplicate)" | A retry was stopped. The customer got one email from us. |
| Two "delivered" with the same idempotency key | A real duplicate. Page the on-call engineer. |

5. To see whether other accounts are affected, open **Admin console → Operations → Queues → Notification outbox**. It shows sends, retries and blocked duplicates per template for the last hour.

## What do I do, step by step?

**Support agent**

1. Confirm with the steps above. Most reports end here, as "normal repeat" or "customer's mail system".
2. For a real duplicate, page the on-call engineer with the account ID, the template and the idempotency key.
3. If you receive 3 or more tickets about the same template within 30 minutes, page the on-call engineer even before you have confirmed each one.
4. If the template is `invoice_ready` or `payment_failed`, check **Admin console → Account → Invoices** so that you can tell the customer for certain that there is one invoice and one charge.

**On-call engineer**

1. Acknowledge the page within 5 minutes. Open a P2 incident if billing emails are affected, because customers will believe they were charged twice. Otherwise open a P3.
2. In **Admin console → Operations → Queues → Notification outbox**, find the template with the abnormal retry or duplicate count.
3. Select **Pause template** for that template only. Paused notifications are kept in the outbox and are not lost. Do not pause the whole outbox: `password_reset` and `login_locked` emails must keep flowing.
4. Find the source of the retries. Look at which service is queuing the sends and whether it started after a deploy. Releases reach `us-east` first, so a problem seen only in `us-east` on a release day points to the release.
5. If `outbox-duplicate-sent` fired, the idempotency check itself has failed. Escalate to the Platform team lead at once and keep the template paused.
6. When the source is fixed or rolled back, select **Resume template**. Held notifications are sent, and any duplicates among them are blocked.
7. Watch the blocked-duplicates count for 30 minutes. It should fall below 10 per 10 minutes.

Never send a mass "please ignore our last email" message without the support team lead's agreement. A correction email to people who did not notice the duplicate creates more tickets than it prevents.

## Does this also cover duplicate webhook deliveries?

Partly. Webhook delivery is "at least once". A receiver that takes longer than 10 seconds to answer will receive the same event again on the retry schedule: after 1 minute, 5 minutes, 30 minutes, 2 hours, 8 hours and 24 hours. That is expected, and the customer should ignore events whose ID they have already processed.

It is a fault only if the same event is delivered again after the receiver answered with success inside 10 seconds. In that case, page the on-call engineer and name the endpoint ID (such as `wh_8C2V6B4N`). The Identity team owns webhooks.

## What do I tell the customer?

- Real duplicate of an invoice email: "You received the same invoice email twice because of a fault on our side. There is one invoice, <ID>, and you were charged once."
- Normal repeat of `payment_failed`: "We send a reminder after each failed payment attempt. The attempts are made on days 1, 3, 7 and 14 after the first failure."
- Their own mail system: "We sent this email once, at <time>. The second copy was created after it left our systems, for example by a forwarding rule or a shared mailbox."
- Too many billing emails in general: billing contacts can be removed in **Settings → Billing → Billing contacts**. The Owner and Billing admins always receive them.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| A real duplicate confirmed in the admin console | On-call engineer | At once |
| 3 or more tickets about one template in 30 minutes | On-call engineer | At once |
| `outbox-duplicate-sent` fired | Platform team lead | At once |
| The retries come from billing code | Billing team | 30 minutes |
| Duplicate webhook deliveries after a fast success answer | Identity team | 1 business day |
| A customer was really charged twice | Follow `docs/runbooks/refund-escalation.md` | Same business day |

## What happens after the incident?

1. Confirm that no template is paused and that the outbox backlog is empty.
2. Count the affected recipients from the outbox records. They are kept for 30 days, so do this before they are purged.
3. Reply on every linked ticket.
4. For a P2, write the incident report under `reports/incidents/` within 5 business days.
5. If a new template was involved, check that its object ID is specific enough: two different events must never share an idempotency key, and one event must never get two keys.

## Related links

- Incident: `reports/incidents/INC-2026-001-duplicate-invoice-emails.md`
- Releases: `reports/releases/2026.2.md` (idempotency key), `reports/releases/2026.1.md` (billing contacts)
- Code: `src/acme_cloud/notifications/outbox.py`, `src/acme_cloud/notifications/templates.py`, `src/acme_cloud/notifications/recipients.py`, `src/acme_cloud/api_keys/webhooks.py`
- Email list: `docs/reference/constants-and-glossary.md`, section "Which emails does the product send?"
- Webhook design: `docs/architecture/adr/0009-webhook-delivery-signed-payloads-six-retries.md`
- UI: `docs/ui/settings-billing.md` ("How do I add a billing email address?")
- Other runbooks: `docs/runbooks/refund-escalation.md`

Last reviewed: 2026-11-26
