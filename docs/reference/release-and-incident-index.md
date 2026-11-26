# Release and Incident Index 2026

One-page index of releases and incidents in 2026. Details are in `reports/releases/`, `reports/incidents/` and `CHANGELOG.md`. All of it is fictional sample data.

## Which releases shipped in 2026?

Releases are named `<year>.<number>`. Deploys go to `us-east` first, then `eu-central` and `ap-south` one business day later.

| Release | Date | Headline changes | Report |
|---------|------|------------------|--------|
| 2026.1 | 2026-01-20 | Billing contacts (up to 5); invoice PDF redesign | `reports/releases/2026.1.md` |
| 2026.2 | 2026-03-03 | **Require key expiry** policy; key expiry warning email 14 days before | `reports/releases/2026.2.md` |
| 2026.3 | 2026-04-14 | Passkeys (WebAuthn) as an MFA method; SMS hidden for Admins and Owners on Business and Enterprise | `reports/releases/2026.3.md` |
| 2026.4 | 2026-05-26 | `ap-south` region for Enterprise; UPI payments for Indian accounts | `reports/releases/2026.4.md` |
| 2026.5 | 2026-07-07 | Workspace export rewritten as a queued job; one export per workspace | `reports/releases/2026.5.md` |
| 2026.6 | 2026-08-18 | Audit log filters and CSV download; 7-year retention on Enterprise | `reports/releases/2026.6.md` |
| 2026.7 | 2026-09-29 | Webhooks general availability; `Acme-Signature` header | `reports/releases/2026.7.md` |
| 2026.8 | 2026-11-10 | Ownership transfer needs acceptance within 7 days; OIDC SSO | `reports/releases/2026.8.md` |

## Which incidents happened in 2026?

| Incident | Date | Priority | Duration | What happened | Root cause | Report |
|----------|------|----------|----------|---------------|------------|--------|
| INC-2026-001 | 2026-02-11 | P2 | 3 h 10 min | Invoice emails sent twice to billing contacts | Retry in the notification queue was not idempotent | `reports/incidents/INC-2026-001-duplicate-invoice-emails.md` |
| INC-2026-002 | 2026-03-19 | P1 | 47 min | Card payments failed for all regions | Payment processor outage; no fallback and dunning counted the failures | `reports/incidents/INC-2026-002-payment-processor-outage.md` |
| INC-2026-003 | 2026-05-06 | P2 | 2 h 25 min | SAML logins rejected with "signature invalid" for 38 workspaces | Clock drift of 4 minutes on two auth nodes, above the 3-minute allowed skew | `reports/incidents/INC-2026-003-saml-clock-skew.md` |
| INC-2026-004 | 2026-07-22 | P2 | 9 h 40 min | Workspace exports stuck in `running` | Export worker lost its job lease after the 2026.5 rewrite; no timeout | `reports/incidents/INC-2026-004-stuck-exports.md` |
| INC-2026-005 | 2026-09-08 | P1 | 1 h 12 min | Dashboard unavailable in `eu-central` | Database failover did not promote the replica automatically | `reports/incidents/INC-2026-005-eu-central-failover.md` |
| INC-2026-006 | 2026-10-15 | P3 | 5 days to detect | Revoked API keys worked for up to 15 minutes instead of 60 seconds in `ap-south` | Key cache TTL set to 900 seconds in one region's config | `reports/incidents/INC-2026-006-key-revocation-delay.md` |

## What changed because of the incidents?

| Incident | Follow-up | Shipped in |
|----------|-----------|------------|
| INC-2026-001 | Notification sends carry an idempotency key (template + recipient + object ID) | 2026.2 |
| INC-2026-002 | Processor outages are detected and do not count as dunning failures; runbook `docs/runbooks/payment-processor-outage.md` | 2026.3 |
| INC-2026-003 | Clock drift alert at 30 seconds; runbook `docs/runbooks/sso-login-failures.md` | 2026.4 |
| INC-2026-004 | Exports running longer than 24 hours are marked `failed`; runbook `docs/runbooks/stuck-export.md` | 2026.6 |
| INC-2026-005 | Automatic replica promotion tested every quarter; runbook `docs/runbooks/region-failover.md` | 2026.7 |
| INC-2026-006 | Key cache TTL fixed at 60 seconds in code, not config; runbook `docs/runbooks/leaked-api-key.md` | 2026.8 |

## Which architecture decisions are recorded?

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | One Owner per account | Accepted |
| 0002 | Workspace region is fixed at creation | Accepted |
| 0003 | Account state machine lives in the accounts module | Accepted |
| 0004 | Store payment methods as processor tokens only | Accepted |
| 0005 | Hash API keys and show them once | Accepted |
| 0006 | Dunning schedule of days 1, 3, 7 and 14 | Accepted |
| 0007 | Exports run as queued jobs | Accepted, replaces the synchronous export |
| 0008 | Audit log is append-only | Accepted |
| 0009 | Webhook delivery with signed payloads and six retries | Accepted |

ADR files are in `docs/architecture/adr/`.

Last reviewed: 2026-11-26
