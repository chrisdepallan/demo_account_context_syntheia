# Account State Machine

Every account is in exactly one of six states. This page lists the states, every allowed transition, what causes each one, and what users see. The transition table in code is in `src/acme_cloud/accounts/state_machine.py`; the states themselves are the `AccountState` enum in `src/acme_cloud/common/enums.py`.

## What are the account states?

| State | Meaning | Can log in? | Can edit? |
|-------|---------|-------------|-----------|
| `trialing` | New account, on Pro for 14 days | Yes | Yes |
| `active` | Normal operation, on any plan including Free | Yes | Yes |
| `past_due` | A charge failed; retries are running | Yes | Yes |
| `read_only` | Still unpaid on day 14 | Yes | No |
| `closed` | The Owner closed the account; restorable for 30 days | No | No |
| `deleted` | Day 31 after closure; final | No | No |

"Can edit" covers creating and changing projects, files, members and settings. In `read_only`, `closed` and `deleted` an edit returns `ERR_ACCOUNT_READ_ONLY` (HTTP 423).

## What does the state diagram look like?

```text
                 first charge succeeds,
                 or trial ends with no payment method (-> Free)
   [trialing] ------------------------------------------> [active]
                                                           |    ^
                              renewal or seat charge fails |    | balance paid
                              (day 0)                      v    | (within 5 minutes)
                                                        [past_due]
                                                           |
                               day-14 retry fails          |
                                                           v
   [active] <----------------------------------------- [read_only]
              balance paid, or day 44 downgrade to Free

   any state except deleted --- Owner closes --------> [closed]
   [closed] --- Owner restores within 30 days -------> previous state
   [closed] --- day 31 ------------------------------> [deleted]
```

There are no other transitions. For example, an account cannot go from `trialing` straight to `past_due`, and nothing leaves `deleted`.

## What triggers each transition, and who causes it?

| From | To | Trigger | Caused by |
|------|----|---------|-----------|
| `trialing` | `active` | A payment method is added and the first charge succeeds | Owner or Billing admin |
| `trialing` | `active` | The 14-day trial ends with no payment method; the plan becomes Free | Scheduled job |
| `active` | `past_due` | A renewal or seat charge fails (day 0) | Billing, on a declined charge |
| `past_due` | `active` | The balance is paid | Automatic retry, or Owner or Billing admin paying by hand |
| `past_due` | `read_only` | The day-14 retry fails | Dunning job |
| `read_only` | `active` | The balance is paid | Owner or Billing admin |
| `read_only` | `active` | Day 44: the plan is downgraded to Free | Dunning job |
| any except `deleted` | `closed` | The Owner closes the account | Owner |
| `closed` | previous state | The Owner restores within 30 days | Owner, or support on the Owner's request |
| `closed` | `deleted` | Day 31 after closure | Scheduled job |

Only the `accounts` package changes the state. The `billing` package asks for a transition and never writes the field itself. The reason is recorded in `adr/0003-account-state-machine-lives-in-the-accounts-module.md`.

Every state change sends the `account.state_changed` webhook event to subscribed endpoints. Closing and restoring also write the audit events `account.closed` and `account.restored`.

## What happens during the trial?

- A new account starts in `trialing` on the Pro plan for 14 days. All Pro features are visible.
- The Owner gets the `trial_ending` email 3 days before the trial ends, which is day 11.
- If a payment method is added and the first charge succeeds, the account becomes `active` on the chosen paid plan.
- If the first charge is declined, the account stays `trialing`. The person paying sees `ERR_PAYMENT_FAILED` and can try another method until the trial ends.
- If the trial ends with no payment method, the account becomes `active` on Free. No data is deleted, but Pro-only controls disappear.

## What is the dunning timeline after a failed payment?

Days are counted from the first failed charge, which is day 0.

| Day | What happens | State after | Emails |
|-----|--------------|-------------|--------|
| 0 | Renewal or seat charge fails | `past_due` | `payment_failed` to Owner, Billing admins and billing contacts |
| 1 | Automatic retry 1 | `past_due`, or `active` if it succeeds | `payment_failed` if it fails |
| 3 | Automatic retry 2 | same | `payment_failed` if it fails |
| 7 | Automatic retry 3 | same | `payment_failed` if it fails |
| 14 | Automatic retry 4, the last one | `read_only` if it fails | `payment_failed` and `account_read_only` |
| 44 | Downgrade to Free | `active` | `account_downgraded` |

Important details:

- There are four retries in total. After day 14 there are no more automatic retries; the customer must pay from **Settings → Billing**.
- Updating the payment method while `past_due` triggers an immediate retry. The new card is first checked with a temporary $0 authorization.
- Once the balance is paid, full access is restored within 5 minutes.
- Day 44 is 30 days after the account became `read_only`.
- On the day-44 downgrade, members over the Free limit of 3 become guests.
- A charge that fails because the payment processor itself is down does not start or advance dunning. This rule was added in release 2026.3 after INC-2026-002. See `docs/runbooks/payment-processor-outage.md`.

The schedule and why it was chosen: `adr/0006-dunning-schedule-of-days-1-3-7-and-14.md`. The code is in `src/acme_cloud/billing/dunning.py`.

## What is the close, restore and delete timeline?

| Day | What happens |
|-----|--------------|
| 0 | The Owner closes the account in **Settings → Account → Close account** and types the account name to confirm. The subscription is cancelled, the state becomes `closed`, all members are signed out, and the Owner gets the `account_closed` email with a restore link. |
| 0 to 30 | The Owner can restore with the link in the email, or by asking support. The account returns to the state it had before closure. |
| 31 | The account becomes `deleted`. Nobody, including support and engineering, can recover it. |

- Only the Owner can close an account (`account.close` permission). Admins do not see the button.
- An account can be closed from any state except `deleted`. Closing a `past_due` or `read_only` account and restoring it later returns it to `past_due` or `read_only`, not to `active`.
- An annual plan closed within 30 days of purchase is refunded in full. Otherwise there is no refund for unused time.
- Invoices are kept for 7 years even after deletion.

## What do users see in each state?

| State | Dashboard | API | Billing page |
|-------|-----------|-----|--------------|
| `trialing` | Everything works; a banner shows the days left in the trial | Works at the Pro rate limit of 300 requests per minute per key | Prompt to add a payment method |
| `active` | Everything the plan allows | Works at the plan's rate limit | Normal |
| `past_due` | Everything still works; Owner and Billing admins see a payment warning banner | Works | Shows the unpaid invoice and the next retry date |
| `read_only` | Users can log in, open and download content, but cannot edit; every role sees a read-only banner | Read calls work; write calls return `ERR_ACCOUNT_READ_ONLY` | Owner and Billing admins can still pay or update the payment method |
| `closed` | Nobody can log in; the login page says the account is closed | All calls fail | Not reachable; the Owner uses the restore link |
| `deleted` | Nobody can log in | All calls fail | Not reachable |

Paying the balance and updating the payment method are the two actions that stay open in `read_only`. They have to, or the account could never recover.

## What should I check when an account is in the wrong state?

1. Look at the state, the plan and the dunning day in **Admin console → Account → Overview**.
2. Compare with the invoices in **Admin console → Account → Invoices**. An account is `past_due` or `read_only` only while at least one invoice is unpaid.
3. If the invoice is paid and more than 5 minutes have passed, follow `docs/runbooks/account-stuck-in-past-due.md`.
4. If the failures happened during a processor outage, follow `docs/runbooks/payment-processor-outage.md`.

## Where is this described for customers?

- Payment failures: `docs/ui/settings-billing.md`, section "What does the account look like when a payment fails?"
- Closing and restoring: `docs/ui/settings-account.md`
- Trials: `docs/ui/feature-availability.md`, section "What does a trial account see?"

Last reviewed: 2026-11-26
