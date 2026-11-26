# Runbook: Payment Processor Outage

**For:** the on-call engineer. The Billing team joins as soon as the outage is confirmed.

This runbook was written after INC-2026-002 (2026-03-19, P1, 47 minutes), when the payment processor was down and card payments failed in all regions. At that time there was no outage detection, so every failed charge was counted as a dunning failure: healthy accounts moved to `past_due` and received `payment_failed` emails. Since release 2026.3, processor outages are detected and do not count as dunning failures. There is still only one processor and no fallback (see `docs/architecture/adr/0004-store-payment-methods-as-processor-tokens-only.md`).

## What are the symptoms of a processor outage?

- The alert `payments-processor-errors` fires. It fires when more than 25% of charge attempts in a 5-minute window end in a processor error, with at least 20 attempts in the window.
- Customers report that upgrades, seat additions or card updates fail in **Settings → Billing**.
- Several accounts in different regions become `past_due` within a few minutes of each other.
- Support sees a burst of tickets about `payment_failed` emails from customers whose cards are valid.

A **processor error** is a timeout or a server error from the processor. A **decline** is the processor answering normally and saying that the bank refused the charge. Only processor errors point to an outage. Declines are the customer's problem and always count for dunning.

## How do I confirm it is the processor and not us?

1. Open **Admin console → Operations → Payments**. Look at the error rate for the last 15 minutes, split into processor errors and declines.
2. Check the split by region. A processor outage hits `us-east`, `eu-central` and `ap-south` together. Errors in one region only point to our own network or nodes in that region.
3. Check the split by payment method. If only one method fails, for example UPI, treat it as a partial outage and continue with this runbook for that method.
4. Check the processor's own status page, linked from the same screen.
5. If the processor error rate is above 25% in all regions, the outage is confirmed.

## What do I do, step by step?

1. **Acknowledge the page** within 5 minutes and open an incident with priority P1. Incident IDs look like `INC-2026-007`.
2. **Check that outage mode is on.** It turns on automatically when the alert fires. The banner "Processor outage mode: ON" shows in **Admin console → Operations → Payments**. If it is not on, select **Admin console → Operations → Payments → Declare processor outage**.
3. **Know what outage mode does.** While it is on:
   - a charge that fails with a processor error is held and tried again every 15 minutes;
   - it is not recorded as a dunning failure, the account does not move to `past_due`, and no `payment_failed` email is sent;
   - scheduled dunning retries (days 1, 3, 7 and 14) that fall inside the outage are postponed until it ends and are not used up;
   - declines are still handled normally;
   - customers who try to upgrade, add seats or update a card see "Payments are temporarily unavailable. Please try again later." Nothing is changed on their account.
4. **Post on the status page** at `https://status.acme-cloud.example` within 15 minutes of the start. Say that payments are affected and that no account will lose access because of it.
5. **Tell the support team lead**, so that agents stop treating payment tickets as card problems.
6. **Bring in the Billing team** within 15 minutes of confirming.
7. **Do not** retry charges by hand, and do not ask customers to enter their card again. Both add load and neither can succeed.
8. **Watch for recovery.** Outage mode turns off automatically when the processor error rate stays below 5% for 10 minutes. To end it by hand, select **Admin console → Operations → Payments → End processor outage**. Do this only after 10 clean minutes.
9. **After recovery**, held charges are sent within 15 minutes and postponed dunning retries run within 1 hour.

## How do I repair accounts that were wrongly marked `past_due`?

Up to 5 minutes can pass between the first errors and the alert. Charges that failed in that gap were counted before outage mode started.

1. Open **Admin console → Operations → Payments → Outage review**. It lists every account that moved to `past_due`, or used a dunning retry, between the first processor error and the end of the outage.
2. For each account whose failure was a processor error, select **Reverse dunning**. The dunning day counter is cleared, the account returns to `active`, and the charge is tried again.
3. Leave accounts whose failure was a decline. Their dunning is correct.
4. If the list has more than 50 accounts, ask the Billing team to run the reversal as a batch.
5. Check that the list is empty of processor-error rows before closing the incident.

No account should reach `read_only` because of an outage. If one did, reverse it first, before any other account.

## What do I tell the customer?

- "Our payment provider had an outage between <start> and <end>. Your payment method is fine and you do not need to do anything."
- "Your account was not restricted. Any charge that could not be made during the outage will be made automatically."
- If they received a `payment_failed` email by mistake: "Please ignore that email. Your account is in good standing."
- If a customer was charged twice, it is a billing error and is always refunded in full. Follow `docs/runbooks/refund-escalation.md`. The refund takes 5–10 business days to arrive.

Never ask the customer for a card number. Payment details are changed only by the customer in **Settings → Billing → Payment method → Update**.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| Outage confirmed | Billing team | 15 minutes |
| Outage mode will not turn on or off | Billing team and Platform team lead | At once |
| Outage lasts longer than 2 hours | Billing manager | At the 2-hour mark |
| Any account reached `read_only` because of the outage | Billing team | At once |
| Duplicate charges found | Billing manager | 1 business day |

## What happens after the incident?

1. Confirm that **Outage review** is clean and that outage mode is off.
2. Update the status page to "resolved".
3. Write the incident report under `reports/incidents/` within 5 business days. Record the start and end times, the number of held charges and the number of reversed accounts.
4. If outage mode did not start by itself, open a follow-up for the Billing team.

## Related links

- Incident: `reports/incidents/INC-2026-002-payment-processor-outage.md`
- Release with the fix: `reports/releases/2026.3.md`
- Code: `src/acme_cloud/billing/dunning.py`, `src/acme_cloud/billing/payment_methods.py`, `src/acme_cloud/billing/service.py`
- Architecture: `docs/architecture/account-state-machine.md`, `docs/architecture/adr/0006-dunning-schedule-of-days-1-3-7-and-14.md`
- UI: `docs/ui/settings-billing.md`, `docs/ui/help-and-support.md`
- Other runbooks: `docs/runbooks/account-stuck-in-past-due.md`, `docs/runbooks/refund-escalation.md`

Last reviewed: 2026-11-26
