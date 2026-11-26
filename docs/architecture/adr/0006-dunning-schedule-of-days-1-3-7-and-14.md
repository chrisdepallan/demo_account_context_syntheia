# ADR 0006: Dunning schedule of days 1, 3, 7 and 14

## Status

Accepted.

## Date

2025-06-24

## Context

"Dunning" is what happens after a renewal or seat charge fails: the retries, the emails and the gradual loss of access. Most failed charges are not a decision to stop paying. A card has expired, a bank has blocked an unusual charge, or an account is briefly short of funds. Many of these fix themselves within days, or are fixed quickly once the right person is told.

The schedule had to balance four things:

- give honest customers enough time and enough reminders to fix the problem;
- avoid cutting off a whole team's work because one card expired;
- avoid retrying so often that banks start to treat the charges as suspicious;
- not give paid service for free for months.

It also had to be simple enough for a support agent to explain from memory.

## Decision

After a failed charge (day 0) the system retries automatically on **days 1, 3, 7 and 14**: four retries, with growing gaps.

| Day | Action | Account state if still unpaid |
|-----|--------|-------------------------------|
| 0 | Charge fails; `payment_failed` email | `past_due` |
| 1 | Retry 1 | `past_due` |
| 3 | Retry 2 | `past_due` |
| 7 | Retry 3 | `past_due` |
| 14 | Retry 4 (last); `account_read_only` email if it fails | `read_only` |
| 44 | Downgrade to Free; `account_downgraded` email | `active` on Free |

- In `past_due` nothing is restricted. Users can work normally for the full 14 days.
- In `read_only` users can log in and read, but not edit. The Owner and Billing admins can still pay.
- The `payment_failed` email goes to the Owner, Billing admins and billing contacts on day 0 and after each failed retry: at most five emails.
- Updating the payment method at any time triggers an immediate retry, outside the schedule.
- Paying the balance at any point returns the account to `active` within 5 minutes.
- On day 44, which is 30 days after `read_only` began, the account is downgraded to Free and members over the Free limit of 3 become guests. No content is deleted.

The schedule is in `src/acme_cloud/billing/dunning.py`. The state changes themselves are made by the accounts package (ADR 0003).

## Alternatives considered

### Retry every day for 14 days

Fourteen retries instead of four.

Rejected because repeated declines on the same card make banks and the processor more likely to flag later charges, including ones that would have succeeded. It also means up to fifteen `payment_failed` emails in two weeks, which trains people to ignore them. Early retries catch temporary problems; later ones mainly wait for a person to act, so widening gaps do the same job with fewer attempts.

### One retry after 7 days, then read-only

A much shorter and simpler schedule.

Rejected because it gives only one automatic chance and only two emails. A failure on a Friday before a holiday week could put a team into read-only mode before the billing contact had seen the message. Retries on days 1 and 3 recover a large share of temporary declines with no human involved.

### No grace period: read-only at the first failure

Access would be restricted on day 0 until payment.

Rejected because it punishes the whole team for a problem only the Owner or a Billing admin can fix, and that most members cannot even see. It would also turn every processor problem into an immediate customer-facing outage.

### Delete data instead of downgrading to Free

After day 44 the account would be closed and later deleted.

Rejected because deleting a customer's work over an unpaid invoice is out of proportion, and cannot be undone. Downgrading to Free limits what the customer can do, and keeps the door open for them to return.

## Consequences

Good:

- The timeline is short enough to remember: "retries on days 1, 3, 7 and 14; read-only on day 14; Free on day 44".
- Customers get 14 days of full service and at most five emails before anything is restricted.
- No data is ever deleted by dunning.

Costs:

- An account can use a paid plan for 14 days without paying, and keep reading its data for 30 more.
- After day 14 there are no more automatic retries. Recovery needs a person to pay from **Settings → Billing**.
- The schedule assumes a failure means "the customer's payment method was declined". On 2026-03-19 the payment processor was down for 47 minutes (INC-2026-002) and every failed charge was counted as a dunning failure, moving healthy accounts to `past_due` and sending `payment_failed` emails. Since release 2026.3, failures caused by a processor outage are detected and do not start or advance dunning. See `docs/runbooks/payment-processor-outage.md`.
- The day counter lives in billing and the state lives in accounts. They can disagree after a late payment confirmation. See `docs/runbooks/account-stuck-in-past-due.md`.
- Day 44 turns members into guests when the account has more than 3 members. Upgrading again later does not automatically turn them back; an Admin must change their roles.
- Enterprise accounts pay by invoice with net-30 terms. A late invoice payment follows the same states, but collection is handled by the billing manager with the customer's named Customer Success Manager before day 14 is reached.

## Related

- Code: `src/acme_cloud/billing/dunning.py`, `src/acme_cloud/billing/invoices.py`, `src/acme_cloud/accounts/state_machine.py`, `src/acme_cloud/notifications/templates.py`
- Architecture: `docs/architecture/account-state-machine.md` ("What is the dunning timeline after a failed payment?")
- ADRs: `docs/architecture/adr/0003-account-state-machine-lives-in-the-accounts-module.md`, `docs/architecture/adr/0004-store-payment-methods-as-processor-tokens-only.md`
- UI: `docs/ui/settings-billing.md` ("What does the account look like when a payment fails?")
- Runbooks: `docs/runbooks/payment-processor-outage.md`, `docs/runbooks/account-stuck-in-past-due.md`
- Incident: `reports/incidents/INC-2026-002-payment-processor-outage.md`
- Release: `reports/releases/2026.3.md`

Last reviewed: 2026-11-26
