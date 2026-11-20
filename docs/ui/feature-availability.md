# Feature Availability by Plan

Use this page to answer "why don't I see X in the dashboard?".

## Which dashboard features depend on the plan?

| UI feature | Free | Starter | Pro | Business | Enterprise |
|------------|------|---------|-----|----------|------------|
| **Settings → API keys** | No | Yes | Yes | Yes | Yes |
| **Require MFA** toggle | No | No | Yes | Yes | Yes |
| Audit log | No | No | Yes (90 days) | Yes (1 year) | Yes (7 years) |
| In-app live chat | No | No | Yes | Yes | Yes |
| **SSO** (SAML/OIDC) and **Enforce SSO** | No | No | No | Yes | Yes |
| Session length setting | No | No | No | Yes | Yes |
| SCIM provisioning | No | No | No | No | Yes |
| `eu-central` region option | No | No | No | Yes | Yes |
| `ap-south` region option | No | No | No | No | Yes |
| PayPal payment option | No | Yes | Yes | Yes | No |

## What limits does the dashboard enforce per plan?

| Limit | Free | Starter | Pro | Business | Enterprise |
|-------|------|---------|-----|----------|------------|
| Members | 3 | 10 | 100 | 500 | Unlimited |
| Workspaces | 1 | 1 | 3 | 10 | Unlimited |
| Storage | 2 GB total | 10 GB/seat | 50 GB/seat | 200 GB/seat | 1 TB/seat |
| Max file upload | 250 MB | 250 MB | 5 GB | 5 GB | 5 GB |
| Version history | 7 days | 30 days | 180 days | 1 year | Unlimited |

## What happens in the UI when storage is full?

At **90%**, Owners and Admins get an email warning. At **100%**, uploads are blocked but existing files stay editable. Adding seats, upgrading, or buying a storage pack (100 GB for $10/month) lifts the block immediately.

## What does a trial account see?

New accounts start in `trialing` on **Pro for 14 days**, so all Pro features are visible. Without a payment method at the end, the account drops to Free and Pro-only controls disappear; no data is deleted.

Source: `services/accounts/docs/plans-and-limits.md` and related docs in `demo_account_context`.

Last reviewed: 2026-11-20
