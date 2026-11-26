# Notifications and Emails

Acme Cloud sends email for account, billing and security events. Each user controls the optional ones under **Profile → Notifications**. All product email comes from `no-reply@acme-cloud.example`.

## Where do I change my notification settings?

Go to **Profile → Notifications**. Every user has this page. It shows only the emails that apply to your role, so a Member sees fewer rows than an Owner. Changes save at once and apply only to you.

## Which emails does Acme Cloud send?

| Email | Template key | Who gets it | When |
|-------|--------------|-------------|------|
| Trial ending | `trial_ending` | Owner | **3 days** before the 14-day trial ends |
| Payment failed | `payment_failed` | Owner, Billing admins, billing contacts | Day 0 and after each failed retry (days 1, 3, 7, 14) |
| Account read-only | `account_read_only` | Owner, Billing admins | Day 14 after the first failed payment |
| Account downgraded | `account_downgraded` | Owner, Billing admins | Day 44, when the account moves to Free |
| Invoice ready | `invoice_ready` | Owner, Billing admins, billing contacts | Each invoice |
| Storage warning | `storage_warning` | Owner, Admins | Storage reaches **90%** |
| Storage full | `storage_full` | Owner, Admins | Storage reaches **100%** and uploads are blocked |
| Invitation | `invitation` | The invited person | On invite and on resend |
| Password reset | `password_reset` | The user who asked | On request from **Forgot password** |
| Login locked | `login_locked` | The user | After the **1-hour** lockout (10 failed attempts within 1 hour) |
| Key expiring | `key_expiring` | Owner | **14 days** before an API key expires |
| Ownership transfer | `ownership_transfer` | The Admin chosen as new Owner | When the Owner requests the transfer |
| Account closed | `account_closed` | Owner | On closure; includes the **30-day** restore link |
| Export ready | `export_ready` | The person who started the export | When the export finishes |

## Which emails can I turn off?

Two emails are optional. Each has a switch under **Profile → Notifications**:

- **Storage warnings** (`storage_warning`, the 90% email). Owners and Admins only.
- **Export ready** (`export_ready`). Owners and Admins only, because only they can start an export. The export still appears on **Settings → Workspace → Export** when it is ready.

Both switches are on by default.

## Which emails can I not turn off?

Security, billing and account emails are always sent. They are listed under **Profile → Notifications** with a lock icon and no switch.

- **Security**: `password_reset`, `login_locked`, `invitation`, `key_expiring`, `ownership_transfer`.
- **Billing**: `trial_ending`, `payment_failed`, `account_read_only`, `account_downgraded`, `invoice_ready`.
- **Account**: `account_closed`, `storage_full`.

The reason: each of these needs action, or tells you that access or money changed. For example, `storage_full` means uploads are blocked for everyone in the account.

## Who gets billing emails?

The **Owner** and every **Billing admin** always get them. Admins, Members and Guests do not. To send invoices and payment alerts to someone else, for example an accounts-payable mailbox, add a billing contact.

## How do I add a billing contact?

1. Go to **Settings → Billing → Billing contacts** (Owner or Billing admin).
2. Select **Add contact** and enter the email address, for example `accounts-payable@example.com`.
3. Save.

You can add up to **5 extra addresses**. Billing contacts receive `invoice_ready` and `payment_failed`. They do not receive `account_read_only` or `account_downgraded`, and they cannot log in unless they are also members. Billing contacts were added in release **2026.1**.

## Why did I not get the key expiry email?

`key_expiring` goes only to the **Owner**, not to the Admin who created the key. It is sent once, **14 days** before the expiry date. Keys set to never expire do not get one. Check expiry dates in **Settings → API keys**.

## Why did an email not arrive?

Check these in order:

1. **Spam or quarantine.** Search for the sender `no-reply@acme-cloud.example` and ask your mail administrator to allow it.
2. **Wrong role.** Compare your role with the "Who gets it" column above. An Admin does not get invoices; a Billing admin does not get storage warnings.
3. **Switched off.** For `storage_warning` and `export_ready`, check **Profile → Notifications**.
4. **Not a billing contact.** A shared finance mailbox gets invoices only if it is listed under **Settings → Billing → Billing contacts**.
5. **Invitation expired.** Invitations expire after **7 days**. An Owner or Admin can resend from **Settings → Members**.
6. **Password reset for an SSO user.** Users who sign in only through SSO do not get a reset email; they reset the password with their identity provider.
7. **Already used or expired link.** A password reset link is valid **60 minutes** and works once. Request a new one.
8. **Sent once only.** Each email is sent once per event and recipient. If you deleted it, download the invoice from **Settings → Billing → Invoices**, or ask the sender to resend an invitation.

If none of these apply, contact `support@acme-cloud.example` and give the account ID (for example `acc_7F3K9Q2M`) and the email you expected.

## Why did I get the same email twice?

You should not. Since release **2026.2**, every send carries an idempotency key made of the template, the recipient and the object ID, so one invoice produces one `invoice_ready` email per recipient. (This fixed incident **INC-2026-001**, when billing contacts received invoice emails twice.)

Two cases look like duplicates but are not:

- `payment_failed` is sent on day 0 and again after each failed retry on days 1, 3, 7 and 14, so up to **five** times in one dunning cycle.
- An address that is both a Billing admin's login and a billing contact still gets one email per invoice.

## Does Acme Cloud ever ask for my password by email?

No. Product emails contain links to `https://app.acme-cloud.example` only. Support never asks for a password, a full card number or an MFA code, by email, chat or phone. Report anything that does to `support@acme-cloud.example`.

## What do the emails link to?

| Email | Link goes to |
|-------|--------------|
| `trial_ending`, `payment_failed`, `account_read_only` | **Settings → Billing → Payment method** |
| `account_downgraded` | **Settings → Billing** |
| `invoice_ready` | **Settings → Billing → Invoices** (PDF attached) |
| `storage_warning`, `storage_full` | **Settings → Usage** |
| `invitation` | Accept page; valid **7 days** |
| `password_reset` | New password form; valid **60 minutes**, single use |
| `login_locked` | Login page, with **Forgot password** |
| `key_expiring` | **Settings → API keys** |
| `ownership_transfer` | Accept page; valid **7 days** |
| `account_closed` | Restore link; valid **30 days** |
| `export_ready` | **Settings → Workspace → Export**; download valid **7 days** |

Source: `docs/reference/constants-and-glossary.md` ("Which emails does the product send?").

Last reviewed: 2026-11-26
