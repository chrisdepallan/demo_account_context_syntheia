# INC-2026-005: Dashboard Unavailable in `eu-central`

Blameless postmortem. All data is fictional sample data for Acme Cloud.

| Field | Value |
|-------|-------|
| Incident ID | INC-2026-005 |
| Date | 2026-09-08 (Tuesday) |
| Priority | P1 |
| Duration | 1 h 12 min (06:14 to 07:26 UTC) |
| Regions | `eu-central` |
| Customers affected | 1,284 accounts with at least one workspace in `eu-central` (1,611 workspaces) |
| Detected by | Automated alert on the database primary (06:16 UTC) |
| Owning team | Platform team (infrastructure, on-call) |
| Incident commander | On-call engineer (Platform team) |

## What happened?

On 2026-09-08 at 06:14 UTC the primary database node in `eu-central` failed because of a storage fault. A replica was healthy and fully up to date. It should have been promoted to primary automatically in under a minute.

The promotion did not happen. Automatic promotion had been switched off in `eu-central` during storage maintenance on 2026-08-27 and was never switched back on. The dashboard and the API for workspaces in `eu-central` were unavailable until an engineer promoted the replica by hand. Service was back at 07:26 UTC, 1 h 12 min after the failure.

## What was the customer impact?

- 1,284 accounts had at least one workspace in `eu-central`. All are on Business or Enterprise, because the region is offered from the Business plan. 1,611 workspaces were unavailable.
- Users could sign in at `https://app.acme-cloud.example/login`, but opening a workspace in `eu-central` showed an error page.
- API calls for those workspaces at `https://api.acme-cloud.example/v1` returned `ERR_INTERNAL` (HTTP 500). About 96,000 API requests failed.
- The incident started at 08:14 local time in Frankfurt, at the beginning of the working day for most affected customers.
- Workspaces in `us-east` and `ap-south` were not affected. An account with workspaces in several regions could still use the others.
- No data was lost. Replication to the replica is synchronous, so every change that was confirmed to a user before 06:14 was on the replica.
- 3 exports that were running in `eu-central` paused and continued after the promotion. None got stuck.
- 87 support tickets were opened. For Enterprise customers the P1 first-response target of 30 minutes was met for all 14 tickets.

## What is the timeline?

All times are UTC on 2026-09-08.

| Time | Event |
|------|-------|
| 06:14 | The primary database node in `eu-central` fails. The dashboard starts to return errors for workspaces in the region. |
| 06:16 | Detection. The alert "database primary unreachable" pages the on-call engineer. |
| 06:19 | The on-call engineer acknowledges and waits for the automatic promotion, which normally takes under 1 minute. |
| 06:24 | No promotion has happened. The on-call engineer declares a P1 incident. |
| 06:26 | Status page post on `https://status.acme-cloud.example`: "Workspaces in eu-central are unavailable. Other regions are working." This is 12 minutes after the start and inside the 15-minute target for P1. |
| 06:31 | The on-call engineer pages the database specialist on the Platform team's second-line rota. |
| 06:44 | The database specialist joins. |
| 06:52 | Cause of the missing promotion found: the failover controller in `eu-central` is in maintenance mode since 2026-08-27. |
| 07:03 | The replica is checked: healthy, zero replication lag at the time of failure. Decision to promote by hand. |
| 07:12 | Mitigation. The replica is promoted to primary. |
| 07:19 | The application servers are restarted so that they connect to the new primary. |
| 07:26 | The error rate is back to normal. Incident resolved. |
| 07:40 | Status page updated to "Resolved". |
| 11:30 | A new replica is in place in `eu-central`. Maintenance mode is off and the region has full redundancy again. |

## What was the root cause?

The database failover did not promote the replica automatically.

Each region has a failover controller. It watches the primary and promotes the replica when the primary is gone. The controller has a maintenance mode that stops automatic promotion, so that planned work on the primary does not trigger a failover.

On 2026-08-27 the Platform team upgraded storage in `eu-central` and put the controller into maintenance mode. The work finished without problems. The last step, leaving maintenance mode, was a manual step on a checklist and was missed. For 12 days the region ran without automatic failover and nothing showed it.

The storage fault on 2026-09-08 was a normal hardware failure. It is the kind of event that automatic promotion exists for.

## Why was it not caught earlier?

- Maintenance mode had no time limit and no alert. A controller could stay in it forever.
- Automatic promotion had last been tested in `eu-central` in November 2025. There was no fixed schedule for failover tests.
- The health dashboard showed "replica healthy" in green. It did not show whether the controller was allowed to promote it.
- `us-east` and `ap-south` had the same storage upgrade in August. In both, maintenance mode was switched off correctly, so the gap in the checklist was not noticed.

## What went well?

- The alert fired 2 minutes after the failure and the on-call engineer acknowledged it 3 minutes later.
- The status page post went out 12 minutes after the start.
- No data was lost, because replication is synchronous.
- The regions are isolated from each other. The failure stayed inside `eu-central`.
- Support had a reply text 10 minutes after the status page post, because support has been on the P1 paging list since INC-2026-002.

## What went badly?

- The on-call engineer waited 5 minutes for a promotion that could not happen. Nothing told them that it was switched off.
- No runbook existed for a manual promotion. The steps were worked out during the incident, and the on-call engineer had never done one.
- From paging the database specialist to the promotion took 41 minutes.
- The application servers did not find the new primary by themselves. They needed a restart, which added 7 minutes.

## What are the action items?

| Action | Owning team | Due date | Status | Shipped in |
|--------|-------------|----------|--------|------------|
| Automatic replica promotion is tested every quarter in every region, with a real promotion. | Platform team | 2026-09-29 | Done; first test on 2026-10-13 | 2026.7 |
| Write the runbook `docs/runbooks/region-failover.md`, including manual promotion. | Platform team | 2026-09-29 | Done | 2026.7 |
| Maintenance mode ends by itself after 4 hours and pages the on-call engineer if it is still on after 2 hours. | Platform team | 2026-09-29 | Done | 2026.7 |
| Application servers reconnect to a new primary without a restart. | Platform team | 2026-09-29 | Done | 2026.7 |
| Show "automatic promotion: on/off" for each region on the health dashboard. | Platform team | 2026-09-15 | Done | Not tied to a release |
| Every on-call engineer does one manual promotion in a test environment. | Platform team | 2026-10-31 | Done | Not tied to a release |

The first two rows are the follow-up listed in `docs/reference/release-and-incident-index.md`.

## What did the first quarterly failover test show?

The first test ran on 2026-10-13 in all three regions, outside business hours for each region.

| Region | Time to promote the replica | Result |
|--------|-----------------------------|--------|
| `us-east` | 38 seconds | Passed |
| `eu-central` | 44 seconds | Passed |
| `ap-south` | 52 seconds | Passed |

The application servers reconnected without a restart in all three regions. The next test is due in January 2027.

## What is related?

- Runbook: `docs/runbooks/region-failover.md`
- Code module: none in the application. The failover controller is infrastructure owned by the Platform team. The reconnect change is in the shared database code under `src/acme_cloud/common/`.
- Release that shipped the fix: `reports/releases/2026.7.md`
- Architecture decision: ADR 0002 "Workspace region is fixed at creation" in `docs/architecture/adr/`
- Index: `docs/reference/release-and-incident-index.md`
- UI docs: `docs/ui/help-and-support.md` (status page), `docs/ui/settings-workspace.md` (regions)

Last reviewed: 2026-11-26
