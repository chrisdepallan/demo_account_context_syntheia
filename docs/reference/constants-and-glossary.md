# Constants and Glossary

The single list of values used across the Acme Cloud sample: code in `src/`, tests in `tests/`, docs in `docs/` and reports in `reports/`. If a value here disagrees with another file, this page wins and the other file is fixed.

All names, prices and URLs are fictional.

## What are the plans and what do they cost?

| Plan | Monthly price per seat | Annual price per seat | Notes |
|------|------------------------|-----------------------|-------|
| Free | $0 | $0 | No payment method needed |
| Starter | $8 | $80 | |
| Pro | $20 | $200 | Trial plan |
| Business | $45 | $450 | |
| Enterprise | Custom | Custom | Annual contract, invoice with net-30 terms |

- Annual billing costs **10 times** the monthly price (two months free).
- Prices are also listed in EUR at the same number (Starter €8, Pro €20, Business €45).
- Storage pack: **100 GB for $10/month**, any paid plan, any number of packs.
- New accounts start in `trialing` on **Pro for 14 days**.

## What are the plan limits?

| Limit | Free | Starter | Pro | Business | Enterprise |
|-------|------|---------|-----|----------|------------|
| Members | 3 | 10 | 100 | 500 | Unlimited |
| Workspaces | 1 | 1 | 3 | 10 | Unlimited |
| Storage | 2 GB total | 10 GB/seat | 50 GB/seat | 200 GB/seat | 1 TB/seat |
| Max file upload | 250 MB | 250 MB | 5 GB | 5 GB | 5 GB |
| Version history | 7 days | 30 days | 180 days | 1 year | Unlimited |
| Audit log retention | None | None | 90 days | 1 year | 7 years |
| API rate limit (requests/minute per key) | No API | 60 | 300 | 1,000 | 5,000 |
| Webhook endpoints | 0 | 2 | 5 | 20 | 50 |

- Guests do not use seats. Each paid seat allows **5 guests**. Free accounts allow **5 guests** in total.
- Storage warning at **90%**; uploads blocked at **100%**; existing files stay editable.
- In code, 1 GB = 1,024 MB and 1 TB = 1,024 GB.

## Which features depend on the plan?

| Feature | Minimum plan |
|---------|--------------|
| API keys and REST API | Starter |
| PayPal | Starter to Business (not Enterprise, not India) |
| Require MFA policy | Pro |
| Audit log | Pro |
| In-app live chat | Pro |
| SSO (SAML/OIDC), Enforce SSO | Business |
| Web session length setting | Business |
| `eu-central` region | Business |
| Phone support | Business |
| SCIM provisioning | Enterprise |
| `ap-south` region | Enterprise |
| 24/7 P1 support, named Customer Success Manager | Enterprise |

## What are the roles and what can each do?

Roles: `owner`, `admin`, `billing_admin`, `member`, `guest`. Exactly one Owner per account.

| Permission key | Owner | Admin | Billing admin | Member | Guest |
|----------------|-------|-------|---------------|--------|-------|
| `projects.edit` | Yes | Yes | No | Yes | No |
| `comments.write` | Yes | Yes | No | Yes | Yes |
| `members.manage` | Yes | Yes | No | No | No |
| `security.manage` | Yes | Yes | No | No | No |
| `workspace.export` | Yes | Yes | No | No | No |
| `api_keys.manage` | Yes | Yes | No | No | No |
| `audit.read` | Yes | Yes | No | No | No |
| `billing.read` | Yes | No | Yes | No | No |
| `billing.manage` | Yes | No | Yes | No | No |
| `account.transfer` | Yes | No | No | No | No |
| `account.close` | Yes | No | No | No | No |

## What are the account states and how do they change?

States: `trialing`, `active`, `past_due`, `read_only`, `closed`, `deleted`.

| From | To | Trigger |
|------|----|---------|
| `trialing` | `active` | Payment method added and first charge succeeds, or trial ends with no payment method (account moves to Free and is `active`) |
| `active` | `past_due` | A renewal or seat charge fails (day 0) |
| `past_due` | `active` | Balance paid; full access restored within **5 minutes** |
| `past_due` | `read_only` | Day 14 after the first failure |
| `read_only` | `active` | Balance paid, or day 44 downgrade to Free |
| any except `deleted` | `closed` | Owner closes the account |
| `closed` | previous state | Owner restores within **30 days** |
| `closed` | `deleted` | Day 31 after closure; cannot be undone |

Dunning timeline after a failed payment:

- **Day 0**: `past_due`; Owner and Billing admins emailed.
- **Days 1, 3, 7, 14**: automatic retries (four retries).
- **Day 14**: `read_only` if the day-14 retry fails.
- **Day 44**: downgraded to Free; members over the Free limit become guests.

## What are the billing rules?

- Upgrade: immediate; prorated difference charged at once.
- Downgrade: at the end of the billing period; blocked while members, workspaces or storage exceed the lower plan's limits.
- Adding seats: charged immediately, prorated by day. Removing seats: credited on the next invoice, prorated by day.
- Proration uses whole days remaining divided by days in the period, rounded to the nearest cent, half up.
- Cancel: plan stays active until the end of the paid period, then moves to Free.
- Card update: checked with a temporary **$0 authorization**.
- Invoices: PDF, kept **7 years**; reissue possible for the last **12 months** through support.
- Billing contacts: up to **5 extra addresses**.
- Payment methods: cards (Visa, Mastercard, Amex, Discover) on all paid plans; PayPal on Starter to Business, not in India; UPI for Indian accounts; ACH and SEPA on annual plans over $1,000 / €1,000; invoice net-30 on Enterprise.
- Payment methods are stored only as opaque processor tokens such as `pm_9XK2M4QH7T`. Card numbers are never stored, logged or shown.

## What are the refund rules?

- Annual plan closed or cancelled within **30 days** of purchase: full refund. Otherwise no refund for unused time.
- Monthly plans: no refund for unused time.
- Duplicate charges and billing errors: always refunded in full.
- Refund timeline told to the customer: **5–10 business days**.
- Refund statuses: `pending`, `succeeded`, `failed`.
- Approval: up to **$500** any support agent; **$500.01–$5,000** support team lead; over **$5,000** billing manager.
- Goodwill refunds: team-lead approval at any amount; one per account per **12 months**.
- A refund can never exceed the paid amount of the invoice minus earlier refunds.

## What are the authentication rules?

- Password: **12 to 128 characters**; not on a breached list; must not contain the user's email address; must not match the last **5 passwords**.
- Password reset link: valid **60 minutes**, single use; signs out all other sessions.
- Password expiry policy: off by default; 30, 60 or 90 days.
- Lockout: **5 failed attempts within 15 minutes** locks for **15 minutes**; **10 failed attempts within 1 hour** locks for **1 hour** and emails the user. A password reset unlocks at once.
- MFA methods: `totp`, `webauthn`, `sms`. SMS is hidden for Admins and Owners on Business and Enterprise.
- Backup codes: **10**, single use; generating new ones invalidates the old ones.
- Require MFA policy: **7-day** grace period from the user's next login.
- Sessions: web **14 days** of inactivity, mobile **90 days**. Business and Enterprise can set web between **1 hour and 14 days**.
- SSO: SAML 2.0 or OIDC, Business and Enterprise. Needs a verified email domain (DNS TXT record `acme-verify=<token>`). Enforce SSO disables password login for the verified domain except for the Owner (break-glass: password + MFA).
- ACS URL `https://auth.acme-cloud.example/saml/acs/{workspace_id}`; Entity ID `https://auth.acme-cloud.example/saml/{workspace_id}`; NameID format `emailAddress`.
- Allowed clock skew on SAML assertions: **3 minutes**.

## What are the API key rules?

- Prefixes: `acme_live_` (production), `acme_test_` (sandbox). The secret part is 32 characters.
- Only a SHA-256 hash and the last 4 characters are stored. The full key is shown once.
- Up to **25 active keys** per workspace.
- Scopes: `projects:read`, `projects:write`, `files:read`, `files:write`, `members:read`, `members:write`, `billing:read` (Owner and Billing admin only).
- Expiry: 30, 90, 180 or 365 days, or never. "Never" is blocked by **Require key expiry**.
- Expiry warning email: **14 days** before.
- Rotate: old key works for **24 hours**. Revoke: takes effect within **60 seconds**.

## What are the member and workspace rules?

- Invitations: up to **50 per batch**; expire after **7 days**; can be resent.
- Removing a member: access ends immediately; content is reassigned to the remover.
- Ownership transfer: target must be an Admin; must be accepted within **7 days**; previous Owner becomes Admin.
- Unreachable Owner: support process, up to **5 business days**. Support MFA reset for the only Admin or Owner: up to **2 business days**.
- Regions: `us-east` (Virginia, all plans, default), `eu-central` (Frankfurt, Business and Enterprise), `ap-south` (Mumbai, Enterprise). Fixed at creation.
- Export: ZIP with JSON and original files; link valid **7 days**; one running export per workspace; an export that runs longer than **24 hours** is marked `failed`.
- Export statuses: `queued`, `running`, `ready`, `expired`, `failed`.

## What are the support rules?

- Channels: help center and email on all plans; live chat on Pro and above (Monday–Friday, 08:00–18:00 US Central Time); phone on Business and Enterprise; 24/7 for P1 on Enterprise.
- Priorities: **P1** service down or data at risk; **P2** major feature broken, no workaround; **P3** minor issue or workaround exists; **P4** question or request.

First-response targets:

| Priority | Free | Starter | Pro | Business | Enterprise |
|----------|------|---------|-----|----------|------------|
| P1 | 3 business days | 2 business days | 4 business hours | 1 business hour | 30 minutes, 24/7 |
| P2 | 3 business days | 2 business days | 8 business hours | 4 business hours | 2 hours |
| P3 | 3 business days | 2 business days | 2 business days | 1 business day | 1 business day |
| P4 | 3 business days | 3 business days | 3 business days | 3 business days | 3 business days |

- A business day is 10 business hours (08:00–18:00 US Central Time, Monday–Friday).
- Escalation: customer replies "escalate"; a team lead reviews within **1 business day**.
- P1 incidents are posted on the status page within **15 minutes**.
- Support never asks for or accepts a password, full card number or MFA code.

## What are the REST API rules?

- Base URL: `https://api.acme-cloud.example/v1`. Sandbox: `https://sandbox.api.acme-cloud.example/v1`.
- Auth: `Authorization: Bearer <api key>`.
- Rate limit by plan (see limits table). Over the limit: HTTP 429 with `Retry-After` in seconds.
- Pagination: cursor based, `limit` default **25**, maximum **100**.
- Idempotency: `Idempotency-Key` header on POST; keys are remembered for **24 hours**.
- Webhooks: signed with HMAC-SHA256 in the `Acme-Signature` header; receiver must answer within **10 seconds**; failed deliveries are retried **6 times** over **24 hours** (after 1 minute, 5 minutes, 30 minutes, 2 hours, 8 hours and 24 hours); an endpoint is disabled after **3 days** of continuous failures.
- Webhook events: `account.state_changed`, `member.invited`, `member.removed`, `invoice.paid`, `invoice.payment_failed`, `refund.succeeded`, `api_key.created`, `api_key.revoked`, `export.ready`, `sso.enforced`.

## What are the error codes?

| Code | HTTP | Meaning |
|------|------|---------|
| `ERR_VALIDATION` | 400 | Input failed validation |
| `ERR_UNAUTHENTICATED` | 401 | Missing, invalid, expired or revoked credentials |
| `ERR_PERMISSION_DENIED` | 403 | Role or scope does not allow the action |
| `ERR_PLAN_REQUIRED` | 403 | Feature is not on the account's plan |
| `ERR_NOT_FOUND` | 404 | Resource does not exist |
| `ERR_CONFLICT` | 409 | Action conflicts with current state (for example a second running export) |
| `ERR_LIMIT_EXCEEDED` | 409 | A plan or resource limit is reached |
| `ERR_ACCOUNT_READ_ONLY` | 423 | Account is `read_only`, `closed` or `deleted` and cannot be edited |
| `ERR_LOCKED_OUT` | 423 | Login is temporarily locked |
| `ERR_RATE_LIMITED` | 429 | Too many requests |
| `ERR_PAYMENT_FAILED` | 402 | The payment processor declined the charge |
| `ERR_INTERNAL` | 500 | Unexpected error |

## What do the IDs look like?

| Object | Format | Example |
|--------|--------|---------|
| Account | `acc_` + 8 uppercase letters/digits | `acc_7F3K9Q2M` |
| Workspace | `ws_` + 6 | `ws_4H8P2L` |
| User | `usr_` + 8 | `usr_2B6N8R4V` |
| Invoice | `INV-<year>-<6 digits>` | `INV-2026-004812` |
| Refund | `rf_` + 10 | `rf_8M2K4Q9X7T` |
| Payment method token | `pm_` + 10 | `pm_9XK2M4QH7T` |
| API key ID | `key_` + 8 | `key_5T9W3E7Y` |
| Export | `exp_` + 8 | `exp_6J4D8S2A` |
| Audit event | `evt_` + 12 | `evt_3G7H2K9M4P6Q` |
| Webhook endpoint | `wh_` + 8 | `wh_8C2V6B4N` |
| SSO connection | `sso_` + 6 | `sso_7Q3W9E` |
| Support ticket | `SUP-<5 digits>` | `SUP-58213` |
| Incident | `INC-<year>-<3 digits>` | `INC-2026-007` |
| Manual test case | `TC-<AREA>-<3 digits>` | `TC-BILL-014` |

## Which audit events are recorded?

`login.succeeded`, `login.failed`, `login.locked`, `password.reset`, `mfa.enrolled`, `mfa.reset`, `member.invited`, `member.removed`, `member.role_changed`, `ownership.transfer_requested`, `ownership.transferred`, `account.closed`, `account.restored`, `plan.changed`, `seats.changed`, `payment_method.updated`, `refund.issued`, `sso.enabled`, `sso.enforced`, `policy.changed`, `api_key.created`, `api_key.rotated`, `api_key.revoked`, `export.started`, `export.downloaded`.

Each event stores the actor, the account, the workspace (if any), the time in UTC and a small metadata object. Events are never edited or deleted before the retention period ends.

## Which emails does the product send?

| Template key | Sent to | When |
|--------------|---------|------|
| `trial_ending` | Owner | 3 days before the trial ends |
| `payment_failed` | Owner, Billing admins, billing contacts | Day 0 and after each failed retry |
| `account_read_only` | Owner, Billing admins | Day 14 |
| `account_downgraded` | Owner, Billing admins | Day 44 |
| `invoice_ready` | Owner, Billing admins, billing contacts | Each invoice |
| `storage_warning` | Owner, Admins | Storage at 90% |
| `storage_full` | Owner, Admins | Storage at 100% |
| `invitation` | Invitee | On invite and resend |
| `password_reset` | User | On request |
| `login_locked` | User | 1-hour lockout |
| `key_expiring` | Owner | 14 days before key expiry |
| `ownership_transfer` | New Owner | On request |
| `account_closed` | Owner | On closure, includes the 30-day restore link |
| `export_ready` | Requester | Export finished |

## Which teams own what?

| Team | Owns |
|------|------|
| Accounts team | `accounts`, `workspaces` |
| Billing team | `billing` |
| Identity team | `auth`, `api_keys` |
| Support Tools team | `support`, admin console |
| Platform team | `common`, `notifications`, `audit`, infrastructure, on-call |

People are referred to by role (for example "the on-call engineer", "the billing manager"), not by name.

## Which URLs does the product use?

- Dashboard: `https://app.acme-cloud.example`
- Login: `https://app.acme-cloud.example/login`
- Auth service: `https://auth.acme-cloud.example`
- API: `https://api.acme-cloud.example/v1`
- Help center: `https://help.acme-cloud.example`
- Status page: `https://status.acme-cloud.example`
- Support email: `support@acme-cloud.example`
- Internal admin console: `https://admin.acme-cloud.example` (staff only)

Last reviewed: 2026-11-26
