# Data Model

The entities in the Acme Cloud sample, their key fields, how they relate, and how long each is kept. Field lists name the important fields only; the code in `src/acme_cloud/` is the full definition.

## How do the entities relate to each other?

```text
Account 1 ──── 1 Subscription ──── * Invoice ──── * Refund
   │                  └──── 0..1 PaymentMethod (processor token)
   ├──── * Member (exactly one with role owner)
   ├──── * Invitation
   ├──── * Ticket
   ├──── * AuditEvent
   └──── * Workspace
              ├──── * Export
              ├──── * ApiKey
              ├──── * WebhookEndpoint
              └──── 0..1 SsoConnection

User 1 ──── * Member        (one membership per account)
User 1 ──── * Session
```

An **Account** is the billing and legal owner. A **Workspace** is where the work happens. A person is a **User** (`usr_` ID) and becomes a **Member** of an account when they accept an invitation.

## What do the IDs look like?

Random IDs use the 32-character alphabet `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`. The letters I and O and the digits 0 and 1 are left out so that an ID can be read aloud on a support call without mistakes. ID generation and validation are in `src/acme_cloud/common/ids.py`.

| Entity | Format | Example |
|--------|--------|---------|
| Account | `acc_` + 8 | `acc_7F3K9Q2M` |
| Workspace | `ws_` + 6 | `ws_4H8P2L` |
| User | `usr_` + 8 | `usr_2B6N8R4V` |
| Invitation | `inv_` + 8 | `inv_6R2T8W4Z` |
| Ownership transfer request | `tr_` + 8 | `tr_9D3F7H5K` |
| Subscription | `sub_` + 8 | `sub_4M8P2S6V` |
| Invoice | `INV-<year>-<6 digits>` | `INV-2026-004812` |
| Payment method token | `pm_` + 10 | `pm_9XK2M4QH7T` |
| Refund | `rf_` + 10 | `rf_8M2K4Q9X7T` |
| API key ID | `key_` + 8 | `key_5T9W3E7Y` |
| Webhook endpoint | `wh_` + 8 | `wh_8C2V6B4N` |
| Export | `exp_` + 8 | `exp_6J4D8S2A` |
| SSO connection | `sso_` + 6 | `sso_7Q3W9E` |
| Session | `ses_` + 12 | `ses_2H6K9M3P7R4T` |
| Audit event | `evt_` + 12 | `evt_3G7H2K9M4P6Q` |
| Support ticket | `SUP-<5 digits>` | `SUP-58213` |

An invitation ID starts with lowercase `inv_`; an invoice ID starts with uppercase `INV-`. They are different objects.

## What is stored for an Account, a Member and an Invitation?

**Account**

- ID, name, plan (`free`, `starter`, `pro`, `business`, `enterprise`), state (`trialing`, `active`, `past_due`, `read_only`, `closed`, `deleted`).
- Trial end date: 14 days after creation, on the Pro plan.
- Seat count and number of storage packs.
- The state held before closure, so that a restore within 30 days can return to it.
- Billing details: company name, billing address, VAT/GST ID, PO number, and up to 5 extra billing contact addresses.

**Member**

- User ID, account ID, role (`owner`, `admin`, `billing_admin`, `member`, `guest`), date joined.
- Exactly one Member per account has the role `owner`.
- Guests do not use a seat. Each paid seat allows 5 guests; a Free account allows 5 guests in total.
- When a member is removed, access ends at once and their content is reassigned to the person who removed them.

**Invitation**

- Invitee email, role offered, inviter, created time, status.
- Up to 50 invitations per batch. An invitation expires after 7 days and can be resent, which sends the `invitation` email again.

**Ownership transfer request**

- Current Owner, target Admin, requested time. It must be accepted within 7 days. On acceptance the target becomes Owner and the previous Owner becomes Admin.

## What is stored for a Workspace and an Export?

**Workspace**

- ID, account ID, name, region (`us-east`, `eu-central`, `ap-south`), storage used.
- The region is set at creation and has no update path.
- Storage is counted per account against the plan limit. A warning is sent at 90%; uploads are blocked at 100%.

**Export**

- ID, workspace ID, requester, status (`queued`, `running`, `ready`, `expired`, `failed`), started time, finished time, download link expiry.
- Only one export per workspace may be `queued` or `running`. A second request returns `ERR_CONFLICT`.
- An export that runs longer than 24 hours is marked `failed`.
- The ZIP contains JSON and the original files. The link is valid for 7 days, then the status becomes `expired` and the ZIP is deleted.

## What is stored for billing?

**Subscription**

- Account ID, plan, billing interval (monthly or annual), seats, current period start and end, cancel-at-period-end flag, currency (USD or EUR).
- One subscription per account. Free accounts have a subscription record with no payment method.

**Invoice**

- ID, account ID, amount, currency, status, issue date, paid amount, line items (plan, seats, proration, storage packs).
- Amounts are whole cents (`src/acme_cloud/common/money.py`), so no rounding error reaches an invoice.
- Invoice numbers are a single sequence per year.

**PaymentMethod**

- Only an opaque processor token such as `pm_9XK2M4QH7T`, the method type (card, PayPal, UPI, ACH, SEPA, invoice), the card brand for cards (Visa, Mastercard, Amex or Discover) and the date it was added.
- Card numbers are never stored, logged or shown. See `adr/0004-store-payment-methods-as-processor-tokens-only.md`.

**Refund**

- ID, invoice ID, amount, kind (cancellation, duplicate charge, billing error or goodwill), reason, ticket ID, approver role, status (`pending`, `succeeded`, `failed`).
- The sum of all refunds on an invoice can never exceed the invoice's paid amount.

## What is stored for authentication and API access?

**Session**

- ID, user ID, client type (web or mobile), created time, last activity time.
- Web sessions end after 14 days of inactivity and mobile sessions after 90 days. Business and Enterprise accounts can set the web limit between 1 hour and 14 days.
- A password reset ends all of the user's other sessions.

**SsoConnection**

- ID, workspace ID, protocol (SAML 2.0 or OIDC), identity provider settings, verified domain, enabled flag, enforced flag.
- The domain is verified with a DNS TXT record `acme-verify=<token>`.

**ApiKey**

- Key ID, workspace ID, name, environment (`acme_live_` or `acme_test_` prefix), scopes, expiry, SHA-256 hash of the full key, last 4 characters, created and revoked times.
- The full key is never stored. Up to 25 active keys per workspace.

**WebhookEndpoint**

- ID, workspace ID, URL, subscribed events, signing secret, enabled flag, time of first failure in the current failure run.
- The number of endpoints depends on the plan: Starter 2, Pro 5, Business 20, Enterprise 50.

## What is stored for support and audit?

**Ticket**

- ID such as `SUP-58213`, account ID, channel, priority (P1 to P4), opened time, first-response due time, escalated flag.
- The first-response due time is worked out from the plan and priority in business hours (`src/acme_cloud/support/sla.py`).

**AuditEvent**

- ID, event type (for example `member.removed`), actor, account ID, workspace ID if any, time in UTC, and a small metadata object.
- Events are never edited or deleted before retention ends. See `adr/0008-audit-log-is-append-only.md`.

## How long is each kind of data kept?

| Data | Kept for |
|------|----------|
| Account and workspace content | Until the account is `deleted`: day 31 after closure |
| Invoices (PDF and record) and their refunds | 7 years, even after the account is deleted |
| Payment method token | Until replaced, or until the account is deleted |
| Invitations | 7 days until expiry; expired invitations are removed after 30 days |
| Export ZIP | 7 days after it becomes `ready` |
| Web session | 14 days of inactivity (or the account's own setting) |
| Mobile session | 90 days of inactivity |
| Audit events | Free and Starter: not recorded. Pro: 90 days. Business: 1 year. Enterprise: 7 years |
| File version history | Free 7 days, Starter 30 days, Pro 180 days, Business 1 year, Enterprise unlimited |
| API key record (hash and last 4) | Until the workspace is deleted |
| `Idempotency-Key` values | 24 hours |
| Notification outbox records | 30 days |
| Webhook delivery attempts | 30 days |
| Support tickets | 3 years after the ticket is closed |

## What is never stored?

- Passwords in readable form.
- Full API keys.
- Card numbers, in any form.
- MFA codes or backup codes in readable form.

Support agents never ask for or accept a password, a full card number or an MFA code, so none of these should appear in a ticket either.

Last reviewed: 2026-11-26
