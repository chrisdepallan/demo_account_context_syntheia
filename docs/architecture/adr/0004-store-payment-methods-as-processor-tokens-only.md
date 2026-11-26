# ADR 0004: Store payment methods as processor tokens only

## Status

Accepted.

## Date

2025-04-08

## Context

Paid plans need a payment method on file so that renewals, seat changes and upgrades can be charged without the customer being present. Acme Cloud accepts cards (Visa, Mastercard, Amex, Discover), PayPal, UPI for Indian accounts, ACH and SEPA bank transfers on annual plans over $1,000 / €1,000, and invoices with net-30 terms on Enterprise.

Holding card details ourselves would bring the whole product inside the scope of card-industry security audits. It would also make every log file, database backup and support screenshot a possible leak. Support agents talk to customers about billing every day, so the simplest way to make sure a card number is never read out, pasted into a ticket or shown on a shared screen is for the system not to have it.

## Decision

Acme Cloud stores a payment method only as an **opaque token issued by the payment processor**, for example `pm_9XK2M4QH7T`.

- The customer enters payment details in a form hosted by the processor. The details go from the browser to the processor and never reach Acme Cloud servers.
- The processor returns a token (`pm_` followed by 10 characters). The token, the method type and the date it was added are all that is stored.
- Card numbers are never stored, never logged and never shown, in the dashboard, the API or the admin console.
- A new or changed card is checked with a temporary **$0 authorization** through the processor before it replaces the old token.
- Charges and refunds are made by sending the token to the processor. A token is useless outside Acme Cloud's processor account.
- Support never asks for or accepts a full card number. If a customer sends one in a ticket, the agent removes it from the ticket and tells the customer to update the method in **Settings → Billing → Payment method → Update**.

The code is in `src/acme_cloud/billing/payment_methods.py`.

## Alternatives considered

### Store card details ourselves, encrypted

We would run our own card vault and send details to a processor at charge time.

Rejected because of cost and risk. Running a vault means yearly external audits, a separated network, and strict rules for everyone who can reach it. A single mistake, such as a debug log line, becomes a reportable breach. The only real gain is freedom to switch processors, which did not justify the burden.

### Store nothing; ask for payment details on every charge

Each renewal would email the customer a payment link.

Rejected because unattended renewal is the basis of a subscription product. Seat additions are charged immediately and prorated by day; asking for a card each time someone invites a colleague would be unusable. It would also make the dunning retries on days 1, 3, 7 and 14 impossible.

### Tokens from two processors, for failover

Each payment method would be registered with two processors so that one can cover for the other.

Rejected at the time as too complex: customers would have to be sent through two hosted forms, or the details would have to pass through our servers to reach both, which brings back the audit scope we wanted to avoid. This alternative was looked at again after INC-2026-002 and rejected again for the same reason. Detection of outages was added instead.

## Consequences

Good:

- No card data exists in Acme Cloud databases, logs, backups or tickets. A leak of the billing database exposes tokens that cannot be used anywhere else.
- The admin console can safely show the payment method to any support agent, because there is nothing sensitive to show: only the token and the method type.
- The same model works for every method. PayPal, UPI, ACH and SEPA are also held as tokens.
- Adding a method (UPI in release 2026.4) did not change the data model.

Costs:

- Acme Cloud depends completely on one processor. When it is down, no charge can succeed, and there is no fallback. On 2026-03-19 this caused INC-2026-002: card payments failed in all regions for 47 minutes, and at the time those failures were counted as dunning failures. Since release 2026.3, processor outages are detected and do not count. See `docs/runbooks/payment-processor-outage.md`.
- Moving to another processor would need either a token migration arranged between the two processors, or every customer entering their details again.
- Support cannot answer "which card is on file?" with a card number. Agents confirm the method type and the date it was added, and ask the customer to check their own records or simply update the method.
- A token can become invalid on the processor's side (for example the card was replaced by the bank). Acme Cloud learns this only when a charge is declined, which starts the normal dunning timeline.
- Tests and this sample cannot make real charges. The sample simulates the processor and uses tokens in the real format.

## Related

- Code: `src/acme_cloud/billing/payment_methods.py`, `src/acme_cloud/billing/service.py`, `src/acme_cloud/common/ids.py` (`pm_` format)
- Rules: `docs/reference/constants-and-glossary.md`, section "What are the billing rules?"
- UI: `docs/ui/settings-billing.md` ("How do I update the payment method?", "Which payment methods can I choose?")
- Admin console: `docs/ui/internal/admin-console.md` ("What must support never do from the console?")
- ADR: `docs/architecture/adr/0006-dunning-schedule-of-days-1-3-7-and-14.md`
- Runbook: `docs/runbooks/payment-processor-outage.md`
- Incident: `reports/incidents/INC-2026-002-payment-processor-outage.md`

Last reviewed: 2026-11-26
