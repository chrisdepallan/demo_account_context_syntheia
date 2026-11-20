# Admin Console (Internal)

Internal tool for support agents. Not visible to customers. Index this folder in a restricted library, not the customer-facing one.

## How do I issue a refund in the admin console?

1. Open the account in the admin console and check the invoice is paid and inside policy.
2. Select **Invoices → Refund**, choose full or partial, and add the ticket number (for example `SUP-58213`) in the reason field.
3. The refund shows as `pending`, then `succeeded` once the processor confirms.
4. Tell the customer the amount and the **5–10 business day** timeline.

## Who can approve a refund?

| Amount | Approver |
|--------|----------|
| Up to $500 | Any support agent |
| $500.01 – $5,000 | Support team lead |
| Over $5,000 | Billing manager |

Goodwill refunds need team-lead approval at any amount and are limited to one per account per 12 months.

## What must support never do from the console?

- Never ask for or accept a customer's password, full card number or MFA code.
- Never reset MFA or change the Owner based on email alone.
- Never share one customer's data with another unless they are in the same workspace.

Source: `services/billing/docs/refunds.md`, `services/support/docs/sla-and-escalation.md` in `demo_account_context`.

Last reviewed: 2026-11-20
