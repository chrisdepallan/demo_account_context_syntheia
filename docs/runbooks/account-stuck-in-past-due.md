# Runbook: Account Stuck in `past_due`

**For:** support agents first; the on-call engineer if the standard fix does not work.

An account should leave `past_due` or `read_only` and become `active` within **5 minutes** of its balance being paid. This runbook is for the case where the customer has paid and the account has not recovered. It did not come out of a single incident. It exists because the dunning day counter lives in the billing package and the account state lives in the accounts package (`docs/architecture/adr/0003-account-state-machine-lives-in-the-accounts-module.md`), and the two can disagree. The step about processor outages was added after INC-2026-002.

## What are the symptoms?

- The customer says they paid or updated their card, but the dashboard still shows the payment warning banner.
- The account is `read_only` and users cannot edit, although the customer has a receipt.
- The customer keeps getting `payment_failed` emails after paying.
- The alert `account-state-mismatch` fires. It fires when an account with no unpaid invoice has been `past_due` or `read_only` for more than 15 minutes.

## How do I confirm the account is really stuck?

Many "stuck" accounts are correctly `past_due`. Check before changing anything.

1. Open **Admin console → Account → Overview**. Note the state, the plan, the dunning day and the date of the next retry.
2. Open **Admin console → Account → Invoices**. List every invoice that is not fully paid.
3. Compare:

| What you find | Is it stuck? | What it means |
|---------------|--------------|---------------|
| An unpaid invoice exists, and the customer paid a different one | No | Two charges failed, for example a renewal and a seat charge. Both must be paid. |
| The invoice is partly paid | No | The balance is the unpaid part. |
| The customer updated the card but the retry was declined | No | The $0 authorization passed, but the bank refused the real charge. |
| The payment was made less than 5 minutes ago | Not yet | Wait until 5 minutes have passed. |
| The payment is a bank transfer (ACH or SEPA) still on its way | No | The invoice is paid when the money arrives, not when it is sent. |
| All invoices are paid, more than 5 minutes ago, and the state is still `past_due` or `read_only` | **Yes** | Continue with the steps below. |

4. Check **Admin console → Operations → Payments** for the banner "Processor outage mode: ON". During an outage, payments cannot be confirmed. Follow `docs/runbooks/payment-processor-outage.md` and come back here afterwards.

## What do I do, step by step?

**Support agent**

1. Confirm that the account is stuck using the table above. Note the invoice ID (such as `INV-2026-004812`) and the time it was paid.
2. Select **Admin console → Account → Billing → Dunning → Recalculate state**. This asks billing to look at the invoices again and, if nothing is unpaid, asks the accounts package for the transition to `active`. It never changes an invoice and never makes a charge.
3. Wait 5 minutes and reload **Admin console → Account → Overview**. The state should be `active`, the dunning day should be empty, and no retry should be scheduled.
4. If the account is `active`, tell the customer and go to "What happens afterwards?".
5. If the state has not changed after 5 minutes, page the on-call engineer. Give the account ID (such as `acc_7F3K9Q2M`), the invoice ID and the time of the payment. Use P2 if the account is `read_only`, because users cannot work. Use P3 if it is `past_due`, because nothing is restricted yet.
6. If the account is on dunning day 12 or later, say so in the page. On day 14 the account becomes `read_only`, and the fix must land before then.

Support agents must not use any other route to change the state, such as changing the plan and changing it back, or closing and restoring the account. A restore returns the account to the state it had before closure, so it would still be `past_due`.

**On-call engineer**

1. Acknowledge the page within 5 minutes.
2. In **Admin console → Account → Billing → Dunning**, open **History**. It lists every charge attempt, payment confirmation and state request with its time and result.
3. Look for a payment confirmation with no state request after it, or a state request that was refused.
   - **No state request:** the confirmation was received but not processed. Select **Replay last payment event**.
   - **Request refused with `ERR_CONFLICT`:** the account was in a state from which `active` cannot be reached. The usual case is `closed`: the Owner closed the account, and the payment arrived afterwards. This is correct behaviour. The payment is recorded on the invoice and the account stays `closed`. Tell the support agent.
4. If the replay does not help, escalate to the Billing team. Do not edit the account state directly. Only the accounts package's state machine may change it.
5. Check the size of the problem: **Admin console → Operations → Payments → State mismatches** lists every account with no unpaid invoice that is still `past_due` or `read_only`. More than 10 accounts means a fault, not a one-off. Open a P2 incident.

## What if day 14 or day 44 passed while the account was stuck?

- **The account became `read_only` after the customer had paid.** The recalculation returns it to `active`. No data was lost: `read_only` blocks editing only.
- **The account was downgraded to Free on day 44 after the customer had paid.** This is a billing error. Escalate to the Billing team at once. They restore the paid plan. Members who were turned into guests by the downgrade must be given their roles back by an Admin in **Settings → Members**; give the customer the list from the audit log (`member.role_changed` events on the downgrade date).
- **The customer was charged twice while trying to fix it.** A duplicate charge is always refunded in full. Follow `docs/runbooks/refund-escalation.md`.

## What do I tell the customer?

- Not stuck, second invoice: "Your payment for invoice <ID> was received. There is a second unpaid invoice, <ID>, for <amount>. Once it is paid, the warning will disappear within 5 minutes."
- Stuck, fixed: "Your payment was received on <date>. A fault on our side delayed the update of your account. It is now active and nothing further is needed."
- Stuck, being worked on: "We can see your payment. Your account has not updated because of a fault on our side. An engineer is working on it, and you do not need to pay again."
- Always: "Please do not pay a second time."

Only the Owner and Billing admins can see invoices. If an Admin or Member writes in, confirm that the account has a billing problem, but share invoice details only with the Owner or a Billing admin.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| **Recalculate state** did not work after 5 minutes | On-call engineer | At once if `read_only`; 1 business hour if `past_due` |
| **Replay last payment event** did not work | Billing team | 30 minutes |
| More than 10 accounts in **State mismatches** | On-call engineer opens a P2 incident | At once |
| Account downgraded on day 44 although paid | Billing team and the billing manager | At once |
| Enterprise account paying by invoice (net-30) | Billing manager | Same business day |

## What happens afterwards?

1. Add the times to the ticket: payment received, recalculation run, account `active`.
2. Check the customer's subscribed webhooks: an `account.state_changed` event should have been sent when the account became `active`.
3. If an incident was opened, write the report under `reports/incidents/` within 5 business days.
4. If the same account is stuck twice within 30 days, tell the Billing team even if the standard fix worked both times.

## Related links

- State machine: `docs/architecture/account-state-machine.md` ("What is the dunning timeline after a failed payment?")
- Decisions: `docs/architecture/adr/0003-account-state-machine-lives-in-the-accounts-module.md`, `docs/architecture/adr/0006-dunning-schedule-of-days-1-3-7-and-14.md`
- Code: `src/acme_cloud/billing/dunning.py`, `src/acme_cloud/billing/invoices.py`, `src/acme_cloud/accounts/state_machine.py`
- UI: `docs/ui/settings-billing.md` ("How do I update the payment method?", "What does the account look like when a payment fails?")
- Incident: `reports/incidents/INC-2026-002-payment-processor-outage.md`
- Other runbooks: `docs/runbooks/payment-processor-outage.md`, `docs/runbooks/refund-escalation.md`

Last reviewed: 2026-11-26
