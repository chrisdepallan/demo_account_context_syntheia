# Runbook: Refund Escalation

**For:** support agents. Support team leads and the billing manager approve larger amounts.

Use this runbook when a refund request is above your own approval limit, falls outside the standard policy, has failed at the payment processor, or when the customer disputes a refusal. A simple refund inside policy is described in `docs/ui/internal/admin-console.md`. This runbook did not come out of an incident, but duplicate charges found after a processor outage (see `docs/runbooks/payment-processor-outage.md`) are handled with it.

## What are the symptoms that a refund needs escalation?

- The amount is over **$500**, so an agent cannot approve it alone.
- The customer asks for money back for unused time on a monthly plan, or on an annual plan more than 30 days after purchase.
- The refund shows `failed` in the admin console.
- The customer says a refund marked `succeeded` has not arrived after 10 business days.
- The customer replies "escalate" after a refusal.

## How do I confirm what the customer is owed?

1. Open **Admin console → Account → Invoices** and find the invoice (ID such as `INV-2026-004812`).
2. Check that the invoice is paid, and note the paid amount and any earlier refunds. A refund can never be more than the paid amount minus earlier refunds.
3. Decide which rule applies:

| Case | Rule | Refund |
|------|------|--------|
| Annual plan closed or cancelled within 30 days of purchase | Policy | Full |
| Annual plan after 30 days | Policy | None for unused time |
| Monthly plan | Policy | None for unused time |
| Duplicate charge or billing error | Policy | Always in full |
| Anything else the customer feels is unfair | Goodwill | At the team lead's decision |

4. For "within 30 days", count from the purchase date on the invoice to the date of closure or cancellation. Day 30 is still inside the window.
5. For a billing error, find the proof: two invoices for the same period, a charge after cancellation took effect, or proration that does not match the seat change. Proration uses whole days remaining divided by days in the period, rounded to the nearest cent, half up.

## Who approves which amount?

| Refund amount | Approver |
|---------------|----------|
| Up to $500 | Any support agent |
| $500.01 to $5,000 | Support team lead |
| Over $5,000 | Billing manager |
| Goodwill refund, any amount | Support team lead, and only one per account per 12 months |

- The limit applies to the single refund, not to the customer's total for the year.
- Do not split one refund into smaller parts to stay under a limit. Two refunds on the same invoice within 7 days are added together for approval.
- EUR invoices use the same numbers: up to €500, €500.01 to €5,000, over €5,000.

## What do I do, step by step?

1. Make sure the request comes from the Owner or a Billing admin. Other roles cannot see billing; ask them to bring in someone who can.
2. Open or find the ticket (ID such as `SUP-58213`).
3. Select **Admin console → Account → Invoices → Refund**. Choose full or partial, enter the amount, and put the ticket ID in the reason field.
4. Choose the type: **Policy**, **Billing error** or **Goodwill**. For goodwill, the screen shows the date of the account's last goodwill refund. If it is less than 12 months ago, the refund cannot be made.
5. If the amount is within your limit and the type is not goodwill, select **Issue refund**. The refund (ID such as `rf_8M2K4Q9X7T`) shows as `pending`.
6. If it is above your limit, or is goodwill, select **Request approval**. Add two or three sentences: what happened, which rule applies, and what you recommend. The request goes to the support team lead, or to the billing manager for amounts over $5,000.
7. Tell the customer the request is being reviewed and when they will hear back.
8. When it is approved, the refund is issued automatically and shows as `pending`. When it is refused, the approver's reason appears on the ticket; pass it on in plain words.
9. Watch for `succeeded`. This is normally within 1 hour. Then tell the customer the amount and the **5–10 business day** timeline.

## What do I do when a refund shows `failed`?

A `failed` refund means the processor could not send the money back to the original payment method, for example because a card was closed.

1. Check **Admin console → Operations → Payments** for a processor outage. If outage mode is on, wait for it to end and select **Retry refund**.
2. If there is no outage, ask the Owner or a Billing admin to update the method in **Settings → Billing → Payment method → Update**, then select **Retry refund** once.
3. If it fails a second time, do not retry again. Escalate to the Billing team, which arranges payment by bank transfer.
4. Never ask for card or bank account details in the ticket. The Billing team collects what it needs through the secure billing form.

A `failed` refund does not use up the invoice's refundable amount. Only `pending` and `succeeded` refunds count.

## What do I do when a `succeeded` refund has not arrived?

1. Count business days from the date the refund became `succeeded`. Before day 10, ask the customer to wait.
2. After 10 business days, give the customer the refund ID and the date, and ask them to check with their bank or card issuer.
3. If the bank cannot find it, escalate to the Billing team with the refund ID. Do not issue a second refund. A second refund on the same invoice would be refused anyway, because the total would exceed the paid amount.

## What do I tell the customer?

- Approved: "We have refunded <amount> on invoice <ID>. It will reach your account in 5–10 business days."
- In review: "A refund of this size needs a second approval. You will hear from us within <time>."
- Refused under policy: "Monthly plans are not refunded for unused time. Your plan stays active until <date>, the end of the paid period, and then moves to Free."
- Duplicate charge: "You were charged twice by mistake. We have refunded the second charge in full."
- Goodwill refused because of the 12-month rule: say so directly, and give the date from which a new request can be considered.

Do not promise a refund before it is approved, and do not give a date earlier than 5 business days.

## When and to whom do I escalate?

| Situation | Escalate to | They answer within |
|-----------|-------------|--------------------|
| $500.01 to $5,000, or any goodwill refund | Support team lead | 1 business day |
| Over $5,000 | Billing manager | 2 business days |
| Refund `failed` twice | Billing team | 2 business days |
| `succeeded` but not received after 10 business days and the bank cannot find it | Billing team | 2 business days |
| Customer replies "escalate" | Support team lead | 1 business day |
| More than 5 duplicate charges found on the same day | Billing manager and the on-call engineer; possible billing fault | At once |

## What happens afterwards?

1. Check that the audit log has a `refund.issued` event, and that customers with webhooks received `refund.succeeded`.
2. Close the ticket with the refund ID, the amount, the type and the approver's role.
3. For a billing error, add the invoice ID to the Billing team's error list so that the cause is fixed.

## Related links

- Refund rules: `docs/reference/constants-and-glossary.md`, section "What are the refund rules?"
- Admin console: `docs/ui/internal/admin-console.md` ("How do I issue a refund in the admin console?", "Who can approve a refund?")
- UI: `docs/ui/settings-billing.md`, `docs/ui/settings-account.md` (refund on closing an annual plan), `docs/ui/help-and-support.md` (escalation)
- Code: `src/acme_cloud/billing/refunds.py`, `src/acme_cloud/billing/invoices.py`, `src/acme_cloud/billing/proration.py`, `src/acme_cloud/support/escalation.py`
- Incident with possible duplicate charges: `reports/incidents/INC-2026-002-payment-processor-outage.md`
- Other runbooks: `docs/runbooks/payment-processor-outage.md`, `docs/runbooks/account-stuck-in-past-due.md`

Last reviewed: 2026-11-26
