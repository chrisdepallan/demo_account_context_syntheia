# ADR 0009: Webhook delivery with signed payloads and six retries

## Status

Accepted.

## Date

2026-08-04

## Context

Customers want to know when something changes in their account without asking the API again and again. Typical uses are adding a paid invoice to an accounting system, removing a person from other tools when they are removed from Acme Cloud, and starting a download when an export is ready.

Webhooks were in limited preview during the first half of 2026 and became generally available in release 2026.7. Before general availability, three questions needed fixed answers:

1. How does a receiver know that a request really comes from Acme Cloud? Webhook URLs are public addresses. Anyone who learns one can send a fake `invoice.paid` to it.
2. What happens when the receiver is down or slow? Customer servers restart, deploy and break like any others.
3. When do we stop trying? An endpoint that has been dead for weeks should not get traffic for ever.

## Decision

Acme Cloud sends each event as an HTTP POST with a **signed payload**, retries failed deliveries **six times over 24 hours**, and disables endpoints that keep failing.

**Signing**

- Each webhook endpoint (ID such as `wh_8C2V6B4N`) has its own signing secret, shown once when the endpoint is created.
- Every delivery carries an `Acme-Signature` header of the form `t=<unix time>,v1=<hex digest>`.
- The digest is an HMAC-SHA256, computed with that endpoint's secret, over the text `<unix time>.<raw body>`.
- The receiver computes the same HMAC and rejects the request if the values differ. It should also reject a signature whose time is more than 300 seconds (5 minutes) old, so that a captured request cannot be replayed later.

**Delivery and retries**

- The receiver must answer within **10 seconds** with a success status. A slower answer, an error status or a failed connection counts as a failed delivery.
- A failed delivery is retried six times: after **1 minute, 5 minutes, 30 minutes, 2 hours, 8 hours and 24 hours**.
- After the sixth retry fails, that event is dropped for that endpoint.
- Retries send the same event with the same event ID, so a receiver can ignore one it has already handled.

**Disabling**

- An endpoint that fails continuously for **3 days** is disabled. An Owner or Admin must turn it on again after fixing it.

**Events and limits**

- The events are `account.state_changed`, `member.invited`, `member.removed`, `invoice.paid`, `invoice.payment_failed`, `refund.succeeded`, `api_key.created`, `api_key.revoked`, `export.ready` and `sso.enforced`.
- Endpoints per workspace by plan: Free 0, Starter 2, Pro 5, Business 20, Enterprise 50.

The code is in `src/acme_cloud/api_keys/webhooks.py`.

## Alternatives considered

### No signature; publish the sending IP addresses

Receivers would accept requests only from a list of Acme Cloud addresses.

Rejected because the list would change whenever a region or node is added (`ap-south` arrived in release 2026.4), and every customer firewall would need updating. Many receivers run on platforms where filtering by address is not possible. An address check also proves only where a request came from, not that its content is unchanged.

### Mutual TLS with client certificates

Acme Cloud would present a certificate that the receiver checks.

Rejected because it is hard for customers to set up and harder to renew. Most serverless and low-code platforms that customers use to receive webhooks cannot check client certificates. An HMAC needs only a shared secret and a few lines of code in any language.

### Retry without limit, with growing delays

Deliveries would be retried for days or weeks until they succeed.

Rejected because very late events do harm. An `invoice.payment_failed` delivered a week late, after the invoice was paid, misleads the receiver. An unbounded backlog for dead endpoints also costs queue capacity that healthy endpoints need. Twenty-four hours covers a normal outage and a bad deploy.

### No webhooks; offer an events list for polling

Customers would call an endpoint regularly to fetch new events.

Rejected as the only mechanism because polling uses up the customer's rate limit (60 requests per minute per key on Starter) and delays every reaction by the polling interval.

## Consequences

Good:

- Receivers can prove that a request is genuine and unchanged with a standard HMAC check.
- A receiver that is down for a few hours loses nothing: the 2-hour, 8-hour and 24-hour retries cover it.
- The schedule is fixed and published, so customers can plan around it.
- Dead endpoints stop consuming capacity after 3 days.

Costs:

- Delivery is "at least once", not "exactly once". A receiver that answers after the 10-second limit has passed may still have processed the event, and will receive it again. Receivers must handle repeats by checking the event ID.
- Events can arrive out of order when an early one is being retried. Receivers should not assume order.
- A receiver that is down for more than 24 hours loses events. They must then be recovered by calling the REST API.
- The signing secret is one more secret for the customer to store. Like an API key, it is shown once.
- The 10-second limit means receivers should store the event and answer at once, then do slow work afterwards.
- Disabled endpoints stay disabled until a person acts. A customer who does not notice will silently stop receiving events.
- A webhook payload must never contain secrets. `api_key.created` carries the key ID and last 4 characters, never the key.
- Sending follows the same idempotency idea as email after INC-2026-001: one delivery record per event and endpoint, so a retry inside our own queue cannot create a second, separate delivery chain.

## Related

- Code: `src/acme_cloud/api_keys/webhooks.py`, `src/acme_cloud/accounts/plans.py` (endpoint limits per plan)
- Rules: `docs/reference/constants-and-glossary.md`, section "What are the REST API rules?"
- ADRs: `docs/architecture/adr/0005-hash-api-keys-and-show-them-once.md`, `docs/architecture/adr/0003-account-state-machine-lives-in-the-accounts-module.md` (`account.state_changed`)
- UI: `docs/ui/settings-api-keys.md`
- Runbooks: `docs/runbooks/duplicate-notifications.md`, `docs/runbooks/leaked-api-key.md`
- Incident: `reports/incidents/INC-2026-001-duplicate-invoice-emails.md`
- Release: `reports/releases/2026.7.md` (webhooks general availability, `Acme-Signature` header)

Last reviewed: 2026-11-26
