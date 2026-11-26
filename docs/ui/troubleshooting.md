# Dashboard Troubleshooting

A symptom-to-fix page. Find the heading that matches what you see, then follow the fix. Each answer names the page with the full detail.

## Why can I not see a Settings page?

Settings pages are filtered by **role** first, then by **plan**.

| Page | Roles | Plan |
|------|-------|------|
| **Settings → Account** | Owner | All |
| **Settings → Members** | Owner, Admin | All |
| **Settings → Workspace** | Owner, Admin | All |
| **Settings → Usage** | Owner, Admin | All |
| **Settings → Billing** | Owner, Billing admin | All |
| **Settings → Security** | Owner, Admin | All (SSO needs Business; **Require MFA** needs Pro) |
| **Settings → API keys** | Owner, Admin | Starter and above |
| **Settings → Audit log** | Owner, Admin | Pro and above |

Fix: check your role with an Admin (it is shown next to your name in **Settings → Members**). If the role is right, the plan lacks the feature; the Owner or a Billing admin can upgrade in **Settings → Billing**. Members and Guests see no Settings pages at all, only **Profile**.

## Why can I not invite a member?

- **You are not an Owner or Admin.** Only they see **Settings → Members → Invite**.
- **The member limit is reached** (`ERR_LIMIT_EXCEEDED`): Free **3**, Starter **10**, Pro **100**, Business **500**. Add seats or upgrade in **Settings → Billing**.
- **The batch is too large.** One batch takes up to **50** addresses. Split the list.
- **The guest allowance is used up.** Each paid seat allows **5 guests**; Free allows **5** in total.
- **The account is read-only.** See "Why is the account read-only?" below.

A person who says they never got the invitation: it expires after **7 days**. Resend it from **Settings → Members**.

## Why are uploads blocked?

- **Storage is at 100%.** The meter on **Settings → Usage** is red. Existing files stay editable. Buy a storage pack (**100 GB for $10/month**), add seats or upgrade; the block lifts immediately. See `storage-and-usage.md`.
- **The file is too large.** Free and Starter allow **250 MB** per file; Pro and above allow **5 GB**.
- **The account is read-only.** Nobody can upload or edit until the balance is paid.
- **You are a Guest.** Guests can comment but cannot edit projects or upload.

## Why is the account read-only?

A payment failed and was not fixed in time. The timeline:

- **Day 0** – the account is `past_due`. Everything still works.
- **Days 1, 3, 7, 14** – automatic retries.
- **Day 14** – the account becomes `read_only`. Users can log in and read, but any edit shows `ERR_ACCOUNT_READ_ONLY`.
- **Day 44** – the account is downgraded to Free.

Fix: the Owner or a Billing admin goes to **Settings → Billing → Payment method → Update**. Updating the method triggers a retry at once. When the balance is paid, full access returns within **5 minutes**. Admins and Members cannot fix this; they should tell the Owner.

## Why am I locked out of login?

After **5 failed attempts within 15 minutes**, login is locked for **15 minutes**. After **10 failed attempts within 1 hour**, it is locked for **1 hour** and you get the `login_locked` email. The login page shows `ERR_LOCKED_OUT`.

Fix: wait, or select **Forgot password** on the login page. A password reset unlocks the account at once. The reset link is valid **60 minutes** and works once.

If your workspace enforces SSO, password login is off for your domain. Use **Sign in with SSO**. Only the Owner can still use a password.

## What do I do if I lost my MFA device?

1. Use one of your **10 backup codes** on the MFA screen. Each code works once.
2. Once in, go to **Profile → Security**, remove the lost device, add a new method and generate new backup codes.

No backup codes either? Ask an Owner or Admin to go to **Settings → Members → choose the member → Reset MFA**. You then set up MFA again at your next login.

If you are the **Owner** or the **only Admin**, nobody in the account can reset you. Contact `support@acme-cloud.example`. Support checks your identity and resets MFA within **2 business days**. Support never asks for your password or an MFA code.

## Why did my API key stop working?

The API answers `ERR_UNAUTHENTICATED` (HTTP 401). Check in **Settings → API keys**:

- **Revoked.** A revoked key stops within **60 seconds** and cannot be restored. Create a new key.
- **Expired.** Keys expire after 30, 90, 180 or 365 days unless set to never. The Owner is emailed **14 days** before.
- **Rotated more than 24 hours ago.** After **Rotate**, the old key works for **24 hours** only. Deploy the new key.
- **Wrong environment.** `acme_test_` keys work only on the sandbox URL, `acme_live_` keys only on production.
- **Plan is now Free.** Free has no API.

Other answers are not a dead key: `ERR_PERMISSION_DENIED` means the key lacks the scope; `ERR_RATE_LIMITED` (HTTP 429) means too many requests per minute, so wait for the `Retry-After` seconds.

## Why does my export link say it has expired?

The download link is valid for **7 days** after the export is ready. After that the export shows `expired` and the ZIP is gone. Fix: an Owner or Admin starts a new export in **Settings → Workspace → Export**.

## Why is my export stuck?

- **Status `queued` or `running`.** Large workspaces take hours. Only **one export per workspace** runs at a time, and starting a second one shows `ERR_CONFLICT`.
- **Running for more than 24 hours.** The export is marked `failed` automatically. Start a new one.
- **Status `failed`.** Start a new one. If it fails twice, contact support with the export ID (for example `exp_6J4D8S2A`).
- **Status `ready` but no email.** The `export_ready` email goes only to the person who started the export, and can be turned off in **Profile → Notifications**. The download is on **Settings → Workspace → Export** either way.

## Why did I not get the invoice email?

`invoice_ready` goes to the **Owner**, **Billing admins** and **billing contacts** only. An Admin or Member never gets it.

1. Check spam for `no-reply@acme-cloud.example`.
2. To send invoices to another address, add it in **Settings → Billing → Billing contacts** (up to **5 extra addresses**).
3. Download the PDF yourself from **Settings → Billing → Invoices**. Invoices are kept **7 years**.

Need the invoice changed? Edit **Settings → Billing → Billing details** for future invoices. Support can reissue an invoice from the last **12 months**.

## Why is the Close account button missing?

Only the **Owner** sees **Settings → Account → Close account**. Admins, Billing admins, Members and Guests do not. If the Owner has left the company and cannot be reached, an Admin contacts support; the process needs written confirmation from a company officer and takes up to **5 business days**.

## Why is the Transfer ownership button missing?

Same reason: Owner only. Also, the list of targets shows **Admins** only. Make the person an Admin first in **Settings → Members**. The new Owner must accept within **7 days**.

## Why is a button or option missing even though I am an Admin?

| Missing | Reason |
|---------|--------|
| **Settings → Billing** | Admins have no billing permission. Ask the Owner or a Billing admin |
| "Never" in the key expiry list | **Require key expiry** is on |
| SMS as an MFA method | Hidden for Admins and Owners on Business and Enterprise |
| `eu-central` or `ap-south` region | Needs Business, or Enterprise for `ap-south` |
| PayPal | Starter to Business only; not on Enterprise and not in India |
| Chat icon | Live chat is Pro and above, Monday–Friday, 08:00–18:00 US Central Time |
| `billing:read` scope | Offered to the Owner and Billing admins only |

## What do the error codes mean?

| Code | What it means for you | What to do |
|------|-----------------------|------------|
| `ERR_VALIDATION` | Something you typed is not accepted | Read the field message; for example a password under 12 characters |
| `ERR_UNAUTHENTICATED` | You are not signed in, or the key is invalid, expired or revoked | Sign in again, or check the key |
| `ERR_PERMISSION_DENIED` | Your role or the key's scope does not allow this | Ask an Owner or Admin |
| `ERR_PLAN_REQUIRED` | The feature is not on your plan | Upgrade in **Settings → Billing** |
| `ERR_NOT_FOUND` | The item does not exist or was deleted | Check the link or ID |
| `ERR_CONFLICT` | The action clashes with something in progress, such as a second export | Wait for the first to finish |
| `ERR_LIMIT_EXCEEDED` | A plan limit is reached: members, guests, workspaces, storage, file size or 25 API keys | Free up room, add seats or upgrade |
| `ERR_ACCOUNT_READ_ONLY` | The account is `read_only` or `closed` | Pay the balance, or restore the account |
| `ERR_LOCKED_OUT` | Login is temporarily locked | Wait 15 minutes or 1 hour, or reset the password |
| `ERR_RATE_LIMITED` | Too many requests | Wait and try again |
| `ERR_PAYMENT_FAILED` | The payment processor declined the charge | Try another payment method or ask your bank |
| `ERR_INTERNAL` | Something went wrong on our side | Try again; check `https://status.acme-cloud.example`; then contact support |

## Where do I get help if none of this works?

Help center `https://help.acme-cloud.example` and `support@acme-cloud.example` on all plans; live chat (question-mark icon, bottom right) on Pro and above; phone on Business and Enterprise. Give the account ID, for example `acc_7F3K9Q2M`, and the error code. See `help-and-support.md`.

Source: `docs/reference/constants-and-glossary.md` ("What are the error codes?" and the rule sections).

Last reviewed: 2026-11-26
