# ADR 0005: Hash API keys and show them once

## Status

Accepted.

## Date

2025-05-13

## Context

API keys let customer integrations call the REST API at `https://api.acme-cloud.example/v1` without a user being logged in. A key carries scopes such as `projects:write` or `members:write`, so a stolen key can read or change a workspace's data until someone notices.

Keys are available from the Starter plan upward. A workspace can have up to 25 active keys. Each key is checked on every API request, and the busiest plans allow 5,000 requests per minute per key, so the check must be fast.

The question was what Acme Cloud should keep after a key has been created. Anything we keep can leak from a database, a backup or a log.

## Decision

Acme Cloud stores only a **SHA-256 hash** of each API key, plus its **last 4 characters**. The full key is **shown once**, at creation, and never again.

- A key is a prefix followed by a 32-character random secret. The prefix is `acme_live_` for production and `acme_test_` for the sandbox at `https://sandbox.api.acme-cloud.example/v1`.
- At creation the full key is returned to the creator a single time. The dashboard tells the user to copy it into a secrets manager straight away.
- The stored record holds the key ID (for example `key_5T9W3E7Y`), name, scopes, expiry, the SHA-256 hash and the last 4 characters. The last 4 characters let a person tell keys apart in **Settings → API keys**.
- To check a request, the API hashes the presented key and looks the hash up.
- A lost key cannot be recovered by anyone, including support. The customer rotates it or creates a new one.
- **Rotate** issues a new key and keeps the old one working for 24 hours, so integrations can be switched without downtime.
- **Revoke** stops a key within 60 seconds. API nodes cache key lookups for at most 60 seconds, and that lifetime is a constant in code.

The code is in `src/acme_cloud/api_keys/service.py`, `src/acme_cloud/api_keys/rotation.py` and `src/acme_cloud/api_keys/scopes.py`.

## Alternatives considered

### Store keys encrypted, so they can be shown again

The key would be encrypted in the database and a **Reveal** button would decrypt it for Admins.

Rejected because a key that can be decrypted can be stolen by anyone who gets both the database and the encryption key, and both are held by the same system. A **Reveal** button also turns every Admin session into a way to collect all of a workspace's keys. Showing the key once puts the duty to store it on the customer's secrets manager, which is where it belongs.

### Use a slow password hash such as bcrypt

Passwords are stored with a slow hash, so keys could be too.

Rejected because the reasons do not carry over. A slow hash protects short, guessable secrets. An API key's secret part is 32 random characters, far beyond guessing, so a fast hash is safe. A slow hash would add a large fixed cost to every one of up to 5,000 requests per minute per key, or force a long-lived cache of verified keys, which would make revocation slower.

### Store the full key in plain text

This is the simplest option and allows support to look a key up.

Rejected outright. A single database leak would hand over working keys for every customer.

## Consequences

Good:

- A leak of the key table gives an attacker hashes that cannot be turned back into keys.
- Support staff and engineers never see a customer's key and cannot be asked for one.
- The 4-character suffix is enough for customers and support to say which key they mean, for example "the live key ending 7Q2M".
- Checking a key costs one fast hash and one lookup.

Costs:

- "I lost my key" has only one answer: rotate it or create a new one. This must be said clearly in the UI and by support.
- The creation screen is the only chance to copy the key. If the browser tab is closed too early, the key is wasted.
- Revocation is only as fast as the lookup cache. In October 2026 the cache lifetime in `ap-south` was set to 900 seconds by a region configuration file, so revoked keys kept working there for up to 15 minutes instead of 60 seconds. This was INC-2026-006 and took 5 days to detect. Since release 2026.8 the lifetime is fixed at 60 seconds in code and cannot be set per region.
- Rotation must never be used for a leaked key, because the old key stays valid for 24 hours. A leaked key must be revoked. See `docs/runbooks/leaked-api-key.md`.
- The key prefixes make leaked keys easy to find by scanning code and logs for `acme_live_`. This is useful, but it also means a key pasted into a document is easy for anyone else to spot.

## Related

- Code: `src/acme_cloud/api_keys/service.py`, `src/acme_cloud/api_keys/rotation.py`, `src/acme_cloud/api_keys/scopes.py`, `src/acme_cloud/api_keys/rate_limit.py`
- Rules: `docs/reference/constants-and-glossary.md`, section "What are the API key rules?"
- UI: `docs/ui/settings-api-keys.md` (create, rotate, revoke), `docs/ui/settings-security.md` (**Require key expiry**)
- Runbook: `docs/runbooks/leaked-api-key.md`
- Incident: `reports/incidents/INC-2026-006-key-revocation-delay.md`
- Releases: `reports/releases/2026.2.md` (**Require key expiry**, expiry warning email), `reports/releases/2026.8.md` (cache lifetime fixed in code)
- Audit events: `api_key.created`, `api_key.rotated`, `api_key.revoked`

Last reviewed: 2026-11-26
