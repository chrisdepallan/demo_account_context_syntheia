# API Load Test: March 2026

This report describes a load test of the Acme Cloud REST API at `https://api.acme-cloud.example/v1`. The test measured response times when many API keys send requests at the rate limit of their plan, and it checked what happens when a key goes over the limit. All data is fictional sample data.

## What were the key facts of the test?

| Item | Value |
|------|-------|
| Test dates | 2026-03-10 to 2026-03-12 |
| Code under test | Release 2026.2 (shipped 2026-03-03) |
| Environment | Staging, sized like production, in `us-east` and `eu-central` |
| Run by | Platform team, with the Identity team for the rate-limit part |
| Requests sent | 3,960,000 per region in the latency test; 95,400 in the rate-limit test |
| Result | Passed, with 3 findings |

The API stayed within the latency goals at every plan's rate limit. The rate limiter held each key to its limit exactly. Three findings were recorded; the most important was that a small share of HTTP 429 responses came without a `Retry-After` header.

The `ap-south` region was not tested. It did not exist in March 2026; it opened on 2026-05-26.

## Which rate limits were tested?

The rate limit is counted in requests per minute for each API key and depends on the plan.

| Plan | Rate limit per key | Keys in the test | Total load | Duration |
|------|--------------------|------------------|------------|----------|
| Free | No API | Not tested | | |
| Starter | 60 requests/minute | 200 | 12,000 requests/minute | 30 minutes |
| Pro | 300 requests/minute | 100 | 30,000 requests/minute | 30 minutes |
| Business | 1,000 requests/minute | 40 | 40,000 requests/minute | 30 minutes |
| Enterprise | 5,000 requests/minute | 10 | 50,000 requests/minute | 30 minutes |

Each scenario ran for 30 minutes with every key sending exactly at its limit. The heaviest scenario was Enterprise: 10 keys at 5,000 requests per minute each, which is 50,000 requests per minute in total.

The request mix was 70% reads and 30% writes. List requests used the default page size of 25. Every POST carried an `Idempotency-Key` header.

## What were the latency goals?

The Platform team set these pass criteria for the test. They are internal goals for this test, not a promise to customers.

- Reads: p95 under 300 ms.
- Writes: p95 under 500 ms.
- Any request: p99 under 1,000 ms.
- Server errors (HTTP 5xx): under 0.1% of requests.

p50, p95 and p99 mean that 50%, 95% and 99% of requests were at least that fast. Times were measured at the load generator, in the same region as the API.

## How fast was the API at each plan's rate limit?

Results for `us-east`, all endpoint groups together:

| Scenario | Total load | p50 | p95 | p99 | Server errors |
|----------|------------|-----|-----|-----|---------------|
| Starter keys at 60/minute | 12,000 requests/minute | 38 ms | 112 ms | 240 ms | 0.00% |
| Pro keys at 300/minute | 30,000 requests/minute | 41 ms | 124 ms | 265 ms | 0.01% |
| Business keys at 1,000/minute | 40,000 requests/minute | 44 ms | 139 ms | 310 ms | 0.01% |
| Enterprise keys at 5,000/minute | 50,000 requests/minute | 47 ms | 158 ms | 372 ms | 0.02% |

Latency rose only slightly with load. From the lightest scenario to the heaviest, the load grew more than four times, while p95 grew from 112 ms to 158 ms and p99 from 240 ms to 372 ms. Server errors stayed at or below 0.02%, far under the 0.1% limit.

Results in `eu-central` were a little slower: in the Enterprise scenario p50 was 49 ms, p95 was 166 ms and p99 was 391 ms. All goals were also met there.

## How fast was each endpoint group?

Results for `us-east` in the heaviest scenario (Enterprise keys, 50,000 requests per minute). Endpoint groups are named after the API key scope they need.

| Endpoint group | Kind | p50 | p95 | p99 | Goal met? |
|----------------|------|-----|-----|-----|-----------|
| `projects:read` | Read | 31 ms | 96 ms | 210 ms | Yes |
| `projects:write` | Write | 58 ms | 171 ms | 365 ms | Yes |
| `files:read` (file metadata and lists) | Read | 36 ms | 118 ms | 262 ms | Yes |
| `files:write` (start of an upload, not the transfer itself) | Write | 74 ms | 248 ms | 590 ms | Yes |
| `members:read` | Read | 29 ms | 88 ms | 190 ms | Yes |
| `members:write` | Write | 66 ms | 195 ms | 420 ms | Yes |
| `billing:read` (invoices) | Read | 52 ms | 182 ms | 455 ms | Yes |

Every endpoint group met its goal. The fastest group was `members:read` (p95 of 88 ms). The slowest was `files:write` (p95 of 248 ms, p99 of 590 ms), which is expected because starting an upload checks the storage limit of the account. Among the reads, `billing:read` was clearly the slowest, with a p99 of 455 ms; see finding 3.

Two more measurements from the same run:

- **Page size.** A list request with `limit=100` (the maximum) had a p95 of 205 ms for `projects:read`, about 2.1 times the p95 with the default of 25. It still met the goal.
- **Idempotency.** A repeated POST with the same `Idempotency-Key` returned the stored first answer with a p50 of 12 ms and did not create a second object. Keys are remembered for 24 hours.

## What happens when a key goes over its rate limit?

One key per plan sent requests at 150% of its limit for 10 minutes.

| Plan | Limit per minute | Sent per minute | Sent in 10 minutes | Accepted | Refused with HTTP 429 |
|------|------------------|-----------------|--------------------|----------|-----------------------|
| Starter | 60 | 90 | 900 | 600 | 300 |
| Pro | 300 | 450 | 4,500 | 3,000 | 1,500 |
| Business | 1,000 | 1,500 | 15,000 | 10,000 | 5,000 |
| Enterprise | 5,000 | 7,500 | 75,000 | 50,000 | 25,000 |
| **Total** | | | **95,400** | **63,600** | **31,800** |

The limiter was exact. Each key had exactly its limit accepted in every minute, and every request above the limit was refused. One third of the 95,400 requests (31,800) were refused, as expected at 150% of the limit.

How a refused request looks:

- HTTP status 429 with the error code `ERR_RATE_LIMITED`.
- A `Retry-After` header with the number of seconds to wait. The values seen were between 1 and 60 seconds, because the limit is counted per minute.
- Refusals were fast: p50 of 4 ms and p95 of 9 ms. A key that is over its limit does not slow down other keys.
- A second test client waited for the number of seconds in `Retry-After` and then tried again. All of its retries were accepted on the first try.
- Limits are per key. Two keys of the same workspace each got their own full limit.

## Was the `Retry-After` header always present?

No. This was the main finding of the test.

- Of the 31,800 responses with HTTP 429, 31,673 had a `Retry-After` header (99.6%) and 127 did not (0.4%).
- All 127 came from a second place in the code. The API gateway has its own short burst protection, which acts before the per-key limiter. Its 429 response did not set the header.
- A client that relies on the header had no value to wait for in those cases.
- Fix: the gateway now sets `Retry-After` on every 429. The fix shipped in release 2026.3 on 2026-04-14, with an automated test that fails if any 429 lacks the header.

## What were the findings?

| No. | Finding | Severity | Action | Status |
|-----|---------|----------|--------|--------|
| 1 | 0.4% of HTTP 429 responses had no `Retry-After` header | Medium | Gateway sets the header on every 429 | Fixed in release 2026.3 |
| 2 | `files:write` has the highest p99 (590 ms) and the least room to the 1,000 ms goal | Low | Watch in production; test again after any change to storage checks | Open, monitored |
| 3 | `billing:read` is slow for accounts with many invoices; the p99 of 455 ms came from test accounts with more than 500 invoices | Low | Database index for listing invoices by account and date | Fixed on 2026-03-24 |

There were three findings: one medium and two low. Two are fixed. The third is a point to watch, not a defect.

## What did the test not cover?

- The transfer of file contents. Only the API calls around an upload were measured.
- Webhooks. They were not generally available in March 2026; delivery was measured in October 2026 (`reports/performance/2026-10-webhook-delivery.md`).
- Workspace export, which is a background job (`reports/performance/2026-07-export-benchmark.md`).
- The sandbox API at `https://sandbox.api.acme-cloud.example/v1`, which runs on smaller hardware.
- Behaviour during an outage of a dependency. One week after this test, on 2026-03-19, the payment processor outage INC-2026-002 showed that this matters; it is unrelated to API latency.

## What should be done next?

1. Repeat the test once a year and after any change to the rate limiter.
2. Add `ap-south` to the next test.
3. Add a scenario with mixed plans at the same time, since production traffic is mixed.
4. Tell integrators in the API guide to always read `Retry-After` and never retry at once.

Last reviewed: 2026-11-26
