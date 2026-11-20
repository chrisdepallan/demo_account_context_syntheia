# demo_account_context_syntheia

UI documentation for the Syntheia dashboard: the web app where customers manage their account, members, billing, security and API keys. It is written to be indexed by the MCP documentation server, so an AI assistant can answer "where do I click to…?" questions.

> Source of truth: every screen, path and value here comes from the `demo_account_context@main` library (accounts, billing, auth and support service docs). In that library the product is called **Acme Cloud**, and all names, prices and URLs are fictional. No credentials are stored in this repo.

## What this repo is for

- Indexed as a single library on branch `main`.
- Each Markdown file is split at its headings, so every `##` section is a searchable answer.
- Docs describe the **UI**: menu paths, buttons, who can see them and what happens after a click. Policy details (prices, SLAs, tax rules) stay in `demo_account_context` and are linked from here.

## Repository layout

| Path | Contents |
|------|----------|
| `README.md` | This file |
| `docs/ui/README.md` | Dashboard overview, navigation map, key UI concepts |
| `docs/ui/login-and-profile.md` | Login page, password reset, lockouts, **Profile → Security** |
| `docs/ui/settings-account.md` | **Settings → Account**: transfer ownership, close account |
| `docs/ui/settings-members.md` | **Settings → Members**: invite, remove, reset MFA, roles |
| `docs/ui/settings-workspace.md` | **Settings → Workspace**: export, regions |
| `docs/ui/settings-billing.md` | **Settings → Billing**: plan, seats, payment method, invoices |
| `docs/ui/settings-security.md` | **Settings → Security**: SSO, MFA policy, session rules |
| `docs/ui/settings-api-keys.md` | **Settings → API keys**: create, rotate, revoke |
| `docs/ui/help-and-support.md` | In-app chat, help center, status page |
| `docs/ui/feature-availability.md` | Which UI controls appear on which plan and for which role |
| `docs/ui/internal/admin-console.md` | Internal admin console used by support agents |
| `eval/test-questions.md` | Test questions for the chatbot, with expected answers (**not indexed**) |

## Recommended index globs

```text
README.md
docs/**
```

To keep the internal admin console doc away from customer-facing assistants, exclude `docs/ui/internal/**` from that library and index it in a separate, restricted library. Access is all-or-nothing per library.

## Keeping the index fresh

- There is no auto-sync. Re-index after merging any doc change to `main`.
- When a source doc in `demo_account_context` changes, update the matching page here too.
- Update the "Last reviewed" line at the bottom of a doc when you change it.

## Contributing

1. Use one topic per `##` heading, and phrase headings the way users ask (for example "## How do I invite a member?").
2. Write menu paths in bold with arrows, for example **Settings → Billing → Invoices**.
3. Put concrete values (durations, limits) in the text, not only in tables or screenshots.
4. Never commit secrets or real customer data. The secret filter only skips files by name, so a key pasted into a Markdown file is still indexed.
