# Changelog

Changes to the Acme Cloud sample product in 2026, newest first. Each release has a full report in `reports/releases/`. Incident IDs link to `reports/incidents/`. Everything here is fictional sample data.

Releases are named `<year>.<number>`. They deploy to `us-east` first, then to `eu-central` and `ap-south` one business day later.

## 2026.8 (2026-11-10)

### Added
- Ownership transfer now needs the new Owner to accept within **7 days**; the request expires otherwise (`src/acme_cloud/accounts/ownership.py`).
- OIDC as a second SSO protocol next to SAML 2.0 (`src/acme_cloud/auth/sso.py`).

### Fixed
- API key cache lifetime is fixed at 60 seconds in code and can no longer be changed by region config. Follow-up to INC-2026-006.

## 2026.7 (2026-09-29)

### Added
- Webhooks are generally available: ten event types, payloads signed with HMAC-SHA256 in the `Acme-Signature` header, six retries over 24 hours.
- Webhook endpoint limits per plan: Starter 2, Pro 5, Business 20, Enterprise 50.

### Changed
- Automatic database replica promotion is now tested every quarter. Follow-up to INC-2026-005.

## 2026.6 (2026-08-18)

### Added
- Audit log filters (actor, event type, date range) and CSV download.
- Audit log retention of 7 years on Enterprise.

### Fixed
- Exports that run longer than 24 hours are marked `failed` so a new export can start. Follow-up to INC-2026-004.

## 2026.5 (2026-07-07)

### Changed
- Workspace export was rewritten as a queued job. Only one export per workspace can run at a time; a second request returns `ERR_CONFLICT`.
- The export download link stays valid for 7 days, as before.

## 2026.4 (2026-05-26)

### Added
- `ap-south` (Mumbai) region for Enterprise workspaces.
- UPI payments for Indian accounts.

### Changed
- Alert when clock drift on an auth node passes 30 seconds. Follow-up to INC-2026-003.

## 2026.3 (2026-04-14)

### Added
- Passkeys and security keys (WebAuthn) as an MFA method.

### Changed
- SMS codes are hidden for Admins and Owners on Business and Enterprise.
- A payment processor outage is detected and no longer counts as a failed payment in the dunning schedule. Follow-up to INC-2026-002.

## 2026.2 (2026-03-03)

### Added
- **Require key expiry** policy under **Settings → Security**; it hides the "never" expiry option for API keys.
- Email to the Owner 14 days before an API key expires.

### Fixed
- Notification sends carry an idempotency key (template + recipient + object ID), so a retried send is not delivered twice. Follow-up to INC-2026-001.

## 2026.1 (2026-01-20)

### Added
- Billing contacts: up to 5 extra addresses that receive invoices and payment alerts.
- Redesigned invoice PDF.

## Incidents in 2026

| Incident | Date | Priority | Summary |
|----------|------|----------|---------|
| INC-2026-001 | 2026-02-11 | P2 | Invoice emails sent twice to billing contacts |
| INC-2026-002 | 2026-03-19 | P1 | Card payments failed in all regions for 47 minutes |
| INC-2026-003 | 2026-05-06 | P2 | SAML logins rejected for 38 workspaces |
| INC-2026-004 | 2026-07-22 | P2 | Workspace exports stuck in `running` |
| INC-2026-005 | 2026-09-08 | P1 | Dashboard unavailable in `eu-central` for 1 hour 12 minutes |
| INC-2026-006 | 2026-10-15 | P3 | Revoked API keys worked for up to 15 minutes in `ap-south` |

See `docs/reference/release-and-incident-index.md` for root causes and follow-ups.
