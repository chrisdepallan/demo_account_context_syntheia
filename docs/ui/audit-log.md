# Settings → Audit log

The audit log is the record of who did what in the account. **Owners** and **Admins** on **Pro and above** see it under **Settings → Audit log**. Billing admins, Members and Guests do not see the page.

## Where do I find the audit log?

Go to **Settings → Audit log**. The page lists events with the newest first. Each row shows the time (always in **UTC**), the actor, the event name, the workspace (if the event belongs to one) and a **Details** link that opens the event's metadata. Event IDs look like `evt_3G7H2K9M4P6Q`.

The page opens on the last **30 days**. Use the filters to look further back, up to the retention limit of the plan.

## Who can see the audit log?

Only roles with the `audit.read` permission: the **Owner** and **Admins**. The plan must be **Pro, Business or Enterprise**. A trial account is on Pro, so it has the audit log for the 14 days of the trial.

## What do users on Free or Starter see?

Nothing. **Audit log** is not listed in the Settings menu on Free and Starter. Opening the page address directly shows the message "Audit log is available on Pro and above" (error code `ERR_PLAN_REQUIRED`) and a link to **Settings → Billing**.

Free and Starter keep no audit history. Recording starts at the moment the account moves to Pro or above; earlier activity cannot be shown later.

## Which events does the audit log record?

| Event | What it means in plain words |
|-------|------------------------------|
| `login.succeeded` | A user signed in |
| `login.failed` | A sign-in attempt failed (wrong password, wrong MFA code, rejected SSO response) |
| `login.locked` | Login was locked after too many failed attempts |
| `password.reset` | A user set a new password through a reset link |
| `mfa.enrolled` | A user added an MFA method |
| `mfa.reset` | An Admin, the Owner or support removed a user's MFA so they can set it up again |
| `member.invited` | An invitation was sent or resent |
| `member.removed` | A member was removed from the account |
| `member.role_changed` | A member's role was changed |
| `ownership.transfer_requested` | The Owner asked an Admin to take over the account |
| `ownership.transferred` | The Admin accepted and is now the Owner |
| `account.closed` | The Owner closed the account |
| `account.restored` | The Owner restored the account inside the 30-day window |
| `plan.changed` | The plan was upgraded, downgraded or cancelled |
| `seats.changed` | Seats were added or removed |
| `payment_method.updated` | The payment method was replaced |
| `refund.issued` | Support issued a refund |
| `sso.enabled` | An SSO connection was enabled |
| `sso.enforced` | **Enforce SSO** was turned on |
| `policy.changed` | A security policy changed (Require MFA, password expiry, session length, Require key expiry) |
| `api_key.created` | An API key was created |
| `api_key.rotated` | An API key was rotated |
| `api_key.revoked` | An API key was revoked |
| `export.started` | A workspace export was requested |
| `export.downloaded` | An export ZIP was downloaded |

## What does one audit event contain?

Each event stores five things: the **actor**, the **account**, the **workspace** (if any), the **time in UTC** and a small **metadata** object.

- The actor is usually a user (`usr_2B6N8R4V`, shown with the email address). It can also be an API key (`key_5T9W3E7Y`), **Acme Cloud support** for actions taken by staff, or **System** for automatic actions such as a day-44 downgrade.
- The metadata depends on the event. Examples: `member.role_changed` shows the old and new role; `api_key.revoked` shows the key ID and the last 4 characters; `plan.changed` shows the old and new plan; `login.failed` shows the reason and the IP address.
- Metadata never contains passwords, MFA codes, full API keys or payment details. Payment methods appear only as tokens such as `pm_9XK2M4QH7T`.

## How do I filter the audit log?

Filters were added in release **2026.6**. Three filters sit above the list and can be combined:

1. **Actor** – pick a member, an API key, **Acme Cloud support** or **System**.
2. **Event type** – pick one or more event names, for example `login.failed` and `login.locked`.
3. **Date range** – pick a start and end date. Dates are in UTC.

Select **Clear filters** to return to the last 30 days.

## How do I download the audit log as a CSV?

1. Go to **Settings → Audit log** and set the filters you need.
2. Select **Download CSV**.

The file contains the filtered events, not only the rows on screen. Columns: `event_id`, `time_utc`, `actor`, `event`, `workspace_id`, `metadata`. One file holds up to **50,000 events**; for more, narrow the date range and download in parts. CSV download was added in release **2026.6**.

## How long are audit events kept?

| Plan | Retention |
|------|-----------|
| Free | None |
| Starter | None |
| Pro | **90 days** |
| Business | **1 year** |
| Enterprise | **7 years** |

Events are never edited or deleted before the retention period ends. Nobody can remove a single event, including the Owner and support. Older events drop off automatically.

## What happens to the audit log when the plan changes?

- **Upgrade** (for example Pro to Business): retention grows at once. Events already dropped are not brought back.
- **Downgrade to a lower paid plan with an audit log** (for example Business to Pro): events older than the new limit are removed when the downgrade takes effect at the end of the billing period.
- **Move to Free or Starter**: the page disappears and the history is no longer available. Download a CSV first if you need a copy.

## How do I investigate a revoked API key?

1. Go to **Settings → Audit log**.
2. Set **Event type** to `api_key.created`, `api_key.rotated` and `api_key.revoked`. The metadata shows the key ID and the last 4 characters, so you can match the key.
3. Read who created the key and who revoked it, and when.
4. Change the **Actor** filter to the key itself (for example `key_5T9W3E7Y`) and clear **Event type**. This lists every change that was made with the key, such as `member.invited` or `export.started`.
5. Select **Download CSV** to keep a copy for your records.

A revoked key stops working within **60 seconds**. To revoke a key, see `settings-api-keys.md`.

## How do I investigate a suspicious login?

1. Go to **Settings → Audit log**.
2. Set **Actor** to the user and **Event type** to `login.succeeded`, `login.failed` and `login.locked`.
3. Open **Details** on each row and compare the IP address and time with what the user expects.
4. Look for follow-up events by the same actor: `password.reset`, `mfa.enrolled`, `mfa.reset`, `api_key.created`, `export.started`.
5. If the login was not the user's, ask them to reset the password from the login page (this signs out all other sessions) and reset their MFA in **Settings → Members → choose the member → Reset MFA**. Revoke any key created during the session.

`login.locked` appears after **5 failed attempts within 15 minutes** (15-minute lock) and after **10 failed attempts within 1 hour** (1-hour lock; the user is also emailed).

## Why is an event I expect missing?

- The event is older than the plan's retention (90 days on Pro, 1 year on Business, 7 years on Enterprise).
- The account was on Free or Starter at the time, so nothing was recorded.
- A filter is still set. Select **Clear filters**.
- The action is not an audited event. The log covers the 25 event types listed above. Ordinary project and file edits are tracked in version history, not here.

Source: `docs/reference/constants-and-glossary.md` ("Which audit events are recorded?", "What are the plan limits?"); release 2026.6 in `docs/reference/release-and-incident-index.md`.

Last reviewed: 2026-11-26
