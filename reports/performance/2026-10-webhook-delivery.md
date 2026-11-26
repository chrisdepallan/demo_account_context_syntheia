# Webhook Delivery Report: October 2026

This report measures webhook delivery in production during the first four weeks after webhooks became generally available in release 2026.7 on 2026-09-29. It covers how fast events are sent, how many arrive on the first attempt, how the six retries perform, and how many endpoints were disabled. It was a condition of the go decision for release 2026.7. All data is fictional sample data. Customers are counted, not named.

## What were the key facts of the measurement?

| Item | Value |
|------|-------|
| Period measured | 2026-10-01 to 2026-10-28 (28 days) |
| Regions | `us-east`, `eu-central` and `ap-south` |
| Deliveries measured | 2,400,000 |
| Delivered on the first attempt | 2,323,200 (96.80%) |
| Delivered in the end, including retries | 2,393,472 (99.73%) |
| Never delivered | 6,528 (0.27%) |
| Endpoints registered on 2026-10-28 | 3,180, in 1,240 workspaces |
| Endpoints disabled after 3 days of failures | 47 |
| Run by | Platform team |

Of 2.4 million deliveries, 96.80% arrived on the first attempt and 99.73% arrived in the end. Almost all deliveries that never arrived were for endpoints that had stopped answering altogether.

A "delivery" is one event sent to one endpoint. If a workspace has two endpoints that listen for the same event, that is two deliveries.

## How does webhook delivery work?

- An Owner or Admin registers an endpoint, which gets an ID such as `wh_8C2V6B4N`. The number of endpoints depends on the plan: Starter 2, Pro 5, Business 20, Enterprise 50. Free accounts have none.
- When an event happens, for example `invoice.paid` or `export.ready`, the payload is sent to each endpoint that listens for it.
- Each request is signed with HMAC-SHA256 in the `Acme-Signature` header.
- The receiver must answer within **10 seconds** with a success status. Anything else counts as a failed attempt.
- A failed delivery is retried **6 times over 24 hours**: 1 minute, 5 minutes, 30 minutes, 2 hours, 8 hours and 24 hours after the first failed attempt.
- An endpoint is disabled after **3 days** of continuous failures.

## How fast are events sent?

Delivery latency is the time from the moment the event happens in Acme Cloud to the moment the first attempt is sent to the receiver.

| Region | Share of deliveries | p50 | p95 | p99 |
|--------|---------------------|-----|-----|-----|
| `us-east` | 71% | 0.7 s | 2.6 s | 6.8 s |
| `eu-central` | 24% | 0.8 s | 3.1 s | 7.9 s |
| `ap-south` | 5% | 1.1 s | 4.2 s | 9.6 s |
| **All regions** | **100%** | **0.8 s** | **2.9 s** | **7.4 s** |

Half of all events were sent within 0.8 seconds and 95% within 2.9 seconds. The Platform team's goal is a p95 under 5 seconds in every region, and all three regions met it. `ap-south` was the slowest, with a p95 of 4.2 seconds, because it has the smallest sender pool.

The longest delays came in bursts. On the first day of a month many invoices are created at once, and on 2026-10-01 the p99 in `us-east` reached 31 seconds for about 20 minutes. No event was lost.

How fast receivers answered on the first attempt:

- p50: 180 ms.
- p95: 1.9 seconds.
- 0.9% of first attempts got no answer within 10 seconds and were counted as failed.

## How many deliveries succeeded on the first attempt?

| Result of the first attempt | Deliveries | Share |
|-----------------------------|------------|-------|
| Succeeded | 2,323,200 | 96.80% |
| Failed | 76,800 | 3.20% |
| **Total** | **2,400,000** | **100%** |

The first attempt succeeded for 96.80% of deliveries. The other 3.20% (76,800 deliveries) went into the retry schedule.

Why the 76,800 first attempts failed:

| Cause | Failed first attempts | Share of failures |
|-------|-----------------------|-------------------|
| Receiver answered with a server error (HTTP 5xx) | 29,184 | 38% |
| Receiver did not answer within 10 seconds | 21,504 | 28% |
| Connection problem (name not found, connection refused, certificate error) | 17,664 | 23% |
| Receiver answered with a client error (HTTP 4xx), for example because the URL had been removed | 8,448 | 11% |
| **Total** | **76,800** | **100%** |

The most common cause was a server error on the receiver's side (38%), followed by a receiver that was too slow (28%). All four causes are on the receiver's side. No failure in the period was caused by the Acme Cloud sender being unavailable.

## How did the six retries perform?

| Step | Time after the first failure | Deliveries that succeeded at this step | Share of the 76,800 failed deliveries |
|------|------------------------------|----------------------------------------|---------------------------------------|
| Retry 1 | 1 minute | 41,472 | 54.0% |
| Retry 2 | 5 minutes | 14,592 | 19.0% |
| Retry 3 | 30 minutes | 7,680 | 10.0% |
| Retry 4 | 2 hours | 3,840 | 5.0% |
| Retry 5 | 8 hours | 1,920 | 2.5% |
| Retry 6 | 24 hours | 768 | 1.0% |
| Never delivered | After all 6 retries failed | 6,528 | 8.5% |
| **Total** | | **76,800** | **100%** |

The retries recovered 70,272 of the 76,800 failed deliveries (91.5%). More than half (54.0%) succeeded on the first retry after 1 minute, and 83.0% had succeeded by the third retry after 30 minutes. This shows that most failures are short: a restart or a brief overload on the receiver's side.

The late retries still matter. Retries 4, 5 and 6 together delivered 6,528 events that would otherwise have been lost (3,840 + 1,920 + 768); these belong to receivers that were down for hours. By coincidence this is the same number as the deliveries that never arrived.

In the end 6,528 deliveries were never delivered, which is 8.5% of the failed deliveries and 0.27% of all deliveries. Of these, 5,940 (91%) were for the 47 endpoints that were later disabled.

Timing of the retries was accurate: 99.9% of retries were sent within 5 seconds of the scheduled time. The schedule is counted from the first failed attempt, so the last retry is sent 24 hours after it. A bug that would have spread the retries over more than 34 hours was found and fixed at the code freeze for release 2026.7 (`reports/test-runs/2026-09-22-release-2026.7.md`).

## How many endpoints were disabled after 3 days of failures?

| Measure | Value |
|---------|-------|
| Endpoints registered on 2026-10-28 | 3,180 |
| Endpoints that failed at least once in the period | 1,126 (35.4%) |
| Endpoints disabled after 3 days of continuous failures | 47 (1.5%) |
| Of those, enabled again by the customer before 2026-10-28 | 29 |
| Still disabled on 2026-10-28 | 18 |

Forty-seven endpoints were disabled, 1.5% of all endpoints. Customers fixed and re-enabled 29 of them; 18 were still disabled at the end of the period.

- An endpoint is disabled only when every attempt has failed for 3 days in a row. One success in between starts the count again.
- When an endpoint is disabled, the Owner and Admins are told, and the endpoint is shown as disabled in the dashboard.
- Events that happen while an endpoint is disabled are not sent to it and are not sent later.
- The most common reasons, according to the support tickets: the receiving server had been shut down (19 endpoints), a certificate had expired (11), and the URL was a test address that no longer existed (9). The other 8 had mixed reasons.
- Support received 207 tickets about webhook deliveries and disabled endpoints between 2026-10-01 and 2026-11-20.

## Which events were sent most often?

| Event | Share of deliveries |
|-------|---------------------|
| `member.invited` | 24% |
| `invoice.paid` | 21% |
| `api_key.created` | 14% |
| `member.removed` | 12% |
| `export.ready` | 9% |
| `account.state_changed` | 7% |
| `api_key.revoked` | 5% |
| `invoice.payment_failed` | 4% |
| `refund.succeeded` | 3% |
| `sso.enforced` | 1% |

Member and invoice events made up more than half of all deliveries. `invoice.paid` is the event behind the burst on the first day of the month.

## What were the findings?

| No. | Finding | Severity | Action | Status on 2026-11-26 |
|-----|---------|----------|--------|----------------------|
| 1 | Bursts on the first day of a month raise the p99 delay to about 31 seconds in `us-east` | Low | Add sender capacity that starts automatically when the queue grows | Done on 2026-10-29; the p99 on 2026-11-01 was 8.2 seconds |
| 2 | `ap-south` has the highest latency (p95 of 4.2 seconds) and the least room to the 5-second goal | Low | Add a third sender in `ap-south` | Planned for December 2026 |
| 3 | Customers cannot see why a delivery failed | Medium | Show the last 50 delivery attempts per endpoint, with status and response time | Planned for the first release of 2027 |
| 4 | The code that disables and re-enables endpoints has few automated tests | Medium | More tests; the `notifications` package is at 83.8% line coverage against a target of 85% | Due by 2026-12-15 |

There were four findings: two medium and two low. None of them lost events. Finding 4 is the reason the `notifications` package misses its coverage target in the second-half coverage report.

## What should integrators take from this report?

- Answer quickly. Accept the event, answer with a success status, and do the real work afterwards. Slow answers caused 28% of all first-attempt failures.
- Expect the same event more than once. A retry can arrive although the first attempt was processed, if the answer was too slow.
- Do not rely on the order of events.
- Check the `Acme-Signature` header on every request.
- Keep the endpoint reachable. After 3 days of continuous failures it is disabled, and events from that time are not sent later.

Last reviewed: 2026-11-26
