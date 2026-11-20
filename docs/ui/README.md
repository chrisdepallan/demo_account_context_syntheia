# Dashboard UI Overview

## What is the dashboard?

The dashboard is the web app at `https://app.acme-cloud.example`. Users sign in there to work in their **workspaces** (projects and files). Owners and Admins also manage the account, members, billing, security and API keys there.

## Key UI concepts

- **Account** – the billing and legal owner. Exactly one **Owner** per account. IDs look like `acc_7F3K9Q2M`.
- **Workspace** – a container for projects, files and members. IDs look like `ws_4H8P2L`. Its data region is fixed when it is created.
- **Role** – decides which Settings pages a user sees: Owner, Admin, Billing admin, Member or Guest.
- **Plan** – Free, Starter, Pro, Business or Enterprise. Some controls only appear on higher plans (see `feature-availability.md`).
- **Account state** – `trialing`, `active`, `past_due`, `read_only`, `closed` or `deleted`. In `read_only` users can log in but cannot edit.

## Navigation map

| Menu path | What you do there | Who can open it | Doc |
|-----------|-------------------|-----------------|-----|
| Login page | Sign in, **Forgot password** | Everyone | `login-and-profile.md` |
| **Profile → Security** | Personal MFA, backup codes | Every user | `login-and-profile.md` |
| **Settings → Account** | Transfer ownership, close account | Owner | `settings-account.md` |
| **Settings → Members** | Invite, remove, reset MFA | Owner, Admin | `settings-members.md` |
| **Settings → Workspace** | Export workspace data | Owner, Admin | `settings-workspace.md` |
| **Settings → Billing** | Plan, payment method, invoices, contacts, cancel | Owner, Billing admin | `settings-billing.md` |
| **Settings → Security** | SSO, Require MFA, Enforce SSO | Owner, Admin | `settings-security.md` |
| **Settings → API keys** | Create, rotate, revoke keys | Owner, Admin (Starter and above) | `settings-api-keys.md` |
| Question-mark icon, bottom right | In-app support chat | Pro and above | `help-and-support.md` |

## Settings tree

```text
Profile
└── Security            (MFA setup, backup codes)
Settings
├── Account             (Transfer ownership, Close account)
├── Members             (Invite, Remove, Reset MFA)
├── Workspace           (Export)
├── Billing
│   ├── Payment method  (Update)
│   ├── Invoices
│   ├── Billing details
│   ├── Billing contacts
│   └── Cancel subscription
├── Security
│   ├── SSO             (Add SAML connection, Test connection, Enable, Enforce SSO)
│   ├── Require MFA
│   └── Require key expiry
└── API keys            (Create key, Rotate, Revoke)
```

## Why can't I see a Settings page?

Settings pages are filtered by role. Members and Guests do not see account, billing or security settings. Billing admins see **Settings → Billing** only. Admins see everything except billing, **Transfer ownership** and **Close account**. Full matrix: `settings-members.md` → "Who can do what?".

Last reviewed: 2026-11-20
