# INC-2026-006: Revoked API Keys Kept Working in `ap-south`

Blameless postmortem. All data is fictional sample data for Acme Cloud.

| Field | Value |
|-------|-------|
| Incident ID | INC-2026-006 |
| Date | 2026-10-15 (Thursday) |
| Priority | P3 |
| Duration | 5 days to detect (started 2026-10-15 09:30 UTC, detected 2026-10-20 08:10 UTC, fixed 2026-10-20 11:52 UTC) |
| Regions | `ap-south` |
| Customers affected | 9 accounts (14 revoked keys); 3 of those keys were used after the 60-second limit |
| Detected by | A customer's security team, through a support ticket |
| Owning team | Identity team (owns `api_keys`) |
| Supporting team | Platform team (regional configuration) |

## What happened?

A revoked API key must stop working within 60 seconds. From 2026-10-15 to 2026-10-20, a revoked key in `ap-south` could keep working for up to 15 minutes.

The API servers keep a short-lived cache of valid keys so that they do not look up every request in the key store. The cache lifetime (TTL) is 60 seconds. That number is what makes the 60-second promise true. On 2026-10-15 a performance change set the TTL to 900 seconds in the configuration of `ap-south` only.

Nobody noticed for 5 days. An Enterprise customer found it during their own security test and opened a ticket.

## What was the customer impact?

- `ap-south` is an Enterprise-only region, so all affected accounts are Enterprise accounts.
- Between 2026-10-15 09:30 UTC and 2026-10-20 11:52 UTC, 14 keys were revoked in `ap-south`. They belonged to 9 accounts.
- For 11 of the 14 keys, no request arrived after the revocation. The delay had no effect.
- For 3 keys in 3 accounts, 41 requests were accepted more than 60 seconds after the revocation. The longest gap between revocation and the last accepted request was 13 min 20 s.
- All 41 requests came from the customers' own integrations, which were still running with the old key. The requests matched the normal pattern of each integration.
- None of the 14 revocations was reported by the customer as a response to a leaked key. There is no sign that anyone outside the customers used a revoked key.
- **Rotate** was not affected. After a rotation the old key works for 24 hours by design.
- Expired keys were affected in the same way as revoked keys: an expired key could work up to 15 minutes too long. 2 keys expired in the window; neither was used afterwards.
- `us-east` and `eu-central` were not affected. Their TTL stayed at 60 seconds.

## What is the timeline?

All times are UTC.

| Date and time | Event |
|---------------|-------|
| 2026-10-15 09:30 | A configuration change for `ap-south` goes live. Its goal is to cut API response times in the newest region. One of its 6 settings raises the key cache TTL from 60 to 900 seconds. Start of the incident. |
| 2026-10-15 to 2026-10-19 | API response times in `ap-south` improve. No alert fires. 12 keys are revoked in this period. |
| 2026-10-20 08:10 | Detection. An Enterprise customer's security team reports in a ticket that a key still worked 9 minutes after **Revoke**. |
| 2026-10-20 09:05 | A support agent repeats the test with an `acme_test_` key in `ap-south`. The revoked key works for 13 minutes. |
| 2026-10-20 09:20 | Support escalates to the Identity team. The incident is declared as P3. |
| 2026-10-20 09:45 | The same test in `us-east` and `eu-central` shows the key blocked within 60 seconds. The problem is limited to one region. |
| 2026-10-20 10:40 | The configuration of the three regions is compared. The TTL of 900 seconds in `ap-south` is found. |
| 2026-10-20 11:52 | Mitigation and resolution. The TTL in `ap-south` is set back to 60 seconds and the API servers are reloaded. |
| 2026-10-20 12:05 | Three test revocations in `ap-south` take effect in 22, 41 and 57 seconds. |
| 2026-10-21 | The Identity team reviews the API logs for all 14 revoked keys and the 2 expired keys. |
| 2026-10-22 | The Owners of the 9 accounts are informed by email, with the list of their keys and the requests accepted after revocation. |

## What was the root cause?

The key cache TTL was set to 900 seconds in one region's configuration.

There were two parts:

1. **The value was configurable.** The TTL lived in the regional configuration next to ordinary performance settings. Nothing marked it as a value that a documented promise depends on. The code in `src/acme_cloud/api_keys/rotation.py` read whatever number it was given.
2. **The change was reviewed as a performance change.** The review looked at response times and load on the key store. The link between "cache TTL" and "revoke takes effect within 60 seconds" was not written down anywhere the reviewer would see it.

## Why was it not caught earlier?

- The automated test for revocation runs against a test setup with the default TTL of 60 seconds. It does not read the regional configuration.
- No check in production measured how long a revoked key keeps working.
- Regional configuration could differ between regions with no report of the differences.
- The effect is invisible in normal use. Most revoked keys are no longer in use, so nobody sees a late block.
- `ap-south` is the newest and smallest region. Only 14 keys were revoked there in 5 days.

## What went well?

- Support reproduced the customer's report in under an hour and escalated with a clear test case.
- Comparing regions narrowed the search quickly: one region wrong, two regions right.
- The fix was a one-line configuration change and was verified with three test revocations.
- The API logs were complete, so the Identity team could list every request made with a revoked key.
- Affected customers received exact data, not a general notice.

## What went badly?

- Detection took 5 days and came from a customer.
- From the ticket to the fix took 3 h 42 min. A P3 has no paging, so the work waited for the start of the Identity team's working day.
- The priority was set by the rule "minor issue or workaround exists". The review agreed that a security promise that is not kept should be handled as P2, even when few customers are affected.
- The runbook for a leaked key told customers and support that **Revoke** is enough after 60 seconds. For 5 days that statement was wrong in one region.

## What are the action items?

| Action | Owning team | Due date | Status | Shipped in |
|--------|-------------|----------|--------|------------|
| Key cache TTL fixed at 60 seconds in code, not config. The regional setting is removed. | Identity team | 2026-11-10 | Done | 2026.8 |
| Update the runbook `docs/runbooks/leaked-api-key.md`: after **Revoke**, verify that the key is rejected with `ERR_UNAUTHENTICATED`, then check the audit log. | Identity team | 2026-11-10 | Done | 2026.8 |
| Production check in every region: every hour, create a test key, revoke it and measure the time until it is rejected. Page above 60 seconds. | Identity team | 2026-11-10 | Done | 2026.8 |
| Daily report of configuration differences between regions, sent to the Platform team. | Platform team | 2026-11-10 | Done | 2026.8 |
| Treat a broken security promise as P2 or higher in the incident priority guide. | Platform team | 2026-10-30 | Done | Not tied to a release |
| List all values that a documented customer promise depends on and move them from configuration into code. | Identity team, Billing team, Accounts team | 2026-12-15 | In progress | Planned for the first release of 2027 |

The first two rows are the follow-up listed in `docs/reference/release-and-incident-index.md`.

## What should a customer do after revoking a leaked key?

The advice did not change, and since 2026.8 it holds in every region:

1. Select **Revoke** next to the key under **Settings → API keys**. The key stops working within 60 seconds.
2. Create a new key with only the scopes the integration needs.
3. Check the audit log (Pro and above) for `api_key.revoked` and for requests made with the old key.

Customers in `ap-south` who revoked a key between 2026-10-15 and 2026-10-20 were contacted directly. No other customer needs to act.

## What is related?

- Runbook: `docs/runbooks/leaked-api-key.md`
- Code module: `src/acme_cloud/api_keys/rotation.py`
- Release that shipped the fix: `reports/releases/2026.8.md`
- Release that opened `ap-south`: `reports/releases/2026.4.md`
- Architecture decision: ADR 0005 "Hash API keys and show them once" in `docs/architecture/adr/`
- Index: `docs/reference/release-and-incident-index.md`
- UI doc: `docs/ui/settings-api-keys.md`

Last reviewed: 2026-11-26
