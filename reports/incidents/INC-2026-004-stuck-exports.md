# INC-2026-004: Workspace Exports Stuck in `running`

Blameless postmortem. All data is fictional sample data for Acme Cloud.

| Field | Value |
|-------|-------|
| Incident ID | INC-2026-004 |
| Date | 2026-07-22 (Wednesday) |
| Priority | P2 |
| Duration | 9 h 40 min (03:20 to 13:00 UTC) |
| Regions | `us-east`, `eu-central` |
| Customers affected | 41 workspaces in 37 accounts |
| Detected by | Customer reports to support (first ticket at 08:45 UTC) |
| Owning team | Accounts team (owns `workspaces`) |
| Supporting team | Platform team (on-call, worker infrastructure) |

## What happened?

On 2026-07-22 at 03:20 UTC the export workers in `us-east` and `eu-central` were restarted as part of routine node maintenance. 41 workspace exports were in progress. After the restart they stayed in the status `running`, but no worker was working on them.

The exports would never have finished. There was no timeout, so the status never changed. Because only one export per workspace can run at a time, the affected workspaces could not start a new export either.

Release 2026.5 (2026-07-07) had rewritten the export as a queued job 15 days earlier. This was the first worker restart with exports in progress.

## What was the customer impact?

- 41 exports in 41 workspaces were stuck. The workspaces belonged to 37 accounts.
- The **Settings → Workspace → Export** page showed the export as running for up to 9 h 40 min.
- 17 attempts to start a new export for an affected workspace failed with `ERR_CONFLICT` (HTTP 409), because the stuck export still counted as running.
- No `export_ready` email was sent for the stuck exports until they were restarted.
- 2 customers reported that they needed the export on the same day for a region move. A workspace's region is fixed at creation, so export and re-import is the only way to move.
- 11 support tickets were opened.
- No data was lost or changed. Exports only read data. Exports of other workspaces started after 03:20 worked normally. `ap-south` was not restarted that night and was not affected.

## What is the timeline?

All times are UTC on 2026-07-22.

| Time | Event |
|------|-------|
| 03:20 | Routine restart of the export workers in `us-east` and `eu-central`. 41 exports are in progress and lose their job lease. |
| 03:25 | The leases have not been renewed for 5 minutes. The 41 jobs have the status `running` and no worker. Nothing returns them to the queue and nothing alerts. |
| 08:45 | First support ticket: an export has been "running" for more than 5 hours. |
| 09:30 | Third ticket. A support agent checks the admin console and sees the status `running` for all three. |
| 10:05 | The support team lead escalates to the Accounts team. |
| 10:20 | The Accounts team declares a P2 incident. The on-call engineer joins. |
| 10:50 | A query finds 41 exports in `running` that started before 03:20. No worker log line mentions them after 03:20. |
| 11:30 | Root cause found: the queue hands out a job again only if its status is `queued`. Jobs in `running` with an expired lease are ignored. |
| 12:10 | A script that sets the 41 exports back to `queued` is reviewed by a second engineer. |
| 12:25 | The script runs for 5 exports as a test. Workers pick them up. |
| 13:00 | Mitigation and resolution: all 41 exports are back in the queue and new exports can be started. Incident resolved. |
| 15:45 | All 41 exports are `ready`. The `export_ready` emails are sent. Each link is valid for 7 days from this time. |

## What was the root cause?

The export worker lost its job lease after the 2026.5 rewrite, and there was no timeout.

Since 2026.5 an export is a queued job (ADR 0007). A worker takes a job, sets the export to `running` and holds a lease on it, which it renews every 60 seconds. A job whose lease is not renewed for 5 minutes is meant to go back to the queue. The code is in `src/acme_cloud/workspaces/export.py`.

Two things were missing:

1. **No recovery of lost leases.** When a worker stops, it no longer renews its leases. The queue was meant to give those jobs to another worker. It only looked at jobs in `queued`, so an export in `running` with a lost lease was never handed out again.
2. **No timeout.** Nothing limited how long an export could stay in `running`. The status could stay wrong forever, and the rule "one running export per workspace" then blocked every new export.

## Why was it not caught earlier?

- The test run at the code freeze on 2026-06-30 saw the gap. Its notes say: "an export has no upper time limit; if a worker dies, the job may stay `running`". The gap was accepted, with the condition that a time limit is added in 2026.6. See `reports/test-runs/2026-06-30-release-2026.5.md`.
- No automated test stopped a worker in the middle of a job. The behaviour "another worker takes over" did not work yet, so there was nothing to test against.
- The manual cases for 2026.5 (`TC-WS-011` to `TC-WS-016`) covered start, status, a refused second export, the email and the expired link. None stopped a worker.
- Between 2026-07-07 and 2026-07-22 the workers were restarted twice, both times with no export in progress.
- No alert watched the age of exports in `running` or the number of jobs without a lease.

## What went well?

- Once the query for old `running` exports existed, the full list of 41 was known in minutes.
- The fix script was reviewed by a second engineer and tested on 5 exports before it ran on all of them.
- No export had to be requested again by a customer. All 41 finished after the restart.
- The download links were valid for 7 days from the real finish time, not from the request time.

## What went badly?

- The incident lasted 9 h 40 min, and for the first 5 h 25 min nobody at Acme Cloud knew about it.
- From first ticket to escalation took 80 minutes. An export that runs for hours is normal for large workspaces, so the first tickets did not look urgent.
- Support had no way to cancel or restart an export from the admin console.
- There was no runbook. The diagnosis started from the code.
- The gap was known at the code freeze and accepted until 2026.6, six weeks later. In those six weeks it had no ticket, no owner and no alert to cover it.

## What are the action items?

| Action | Owning team | Due date | Status | Shipped in |
|--------|-------------|----------|--------|------------|
| Exports running longer than 24 hours are marked `failed`. The workspace can then start a new export. | Accounts team | 2026-08-18 | Done | 2026.6 |
| Write the runbook `docs/runbooks/stuck-export.md`. | Accounts team | 2026-08-18 | Done | 2026.6 |
| Return a `running` export to the queue when its lease has not been renewed for 5 minutes, so that another worker takes it over. | Accounts team | 2026-08-18 | Done | 2026.6 |
| Alert `export-running-too-long`: page the on-call engineer when any export has been `running` for more than 6 hours. | Platform team | 2026-08-18 | Done | 2026.6 |
| Show the worker and the last lease renewal of each export in the admin console. Add **Requeue** and **Mark failed** actions for the on-call engineer. | Support Tools team, Accounts team | 2026-08-18 | Done | 2026.6 |
| Add automated tests for the time limit and for a worker that stops in the middle of a job (5 unit tests, 3 integration tests), and the manual cases `TC-WS-017` and `TC-WS-018`. | Accounts team | 2026-08-11 | Done | 2026.6 |
| Until 2026.6 ships: wait for running exports to finish before a worker restart, and check for old `running` exports every morning. | Platform team, Accounts team | 2026-07-23 | Done, ended on 2026-08-19 | Not tied to a release |
| Test process: a gap that is accepted at a code freeze gets a ticket with an owner and a target release before the decision is signed. New background jobs need a "worker dies in the middle" test before the freeze. | All teams, tracked by the release manager | 2026-08-11 | Done | Not tied to a release |

The first two rows are the follow-up listed in `docs/reference/release-and-incident-index.md`.

## What does a customer see for a failed export since 2026.6?

- An export that runs longer than **24 hours** gets the status `failed`. The 24 hours count from the moment the export became `running`; time in `queued` is not included. At exactly 24 hours it is still `running`.
- The requester is told when an export fails.
- The export statuses are `queued`, `running`, `ready`, `expired` and `failed`.
- A `failed` export does not block a new one. The Owner or an Admin starts it again under **Settings → Workspace → Export**.
- The 24-hour rule is the last safety net. A lost lease is normally noticed after 5 minutes, another worker takes the job, and the customer sees no failure.

## What is related?

- Runbook: `docs/runbooks/stuck-export.md`
- Code module: `src/acme_cloud/workspaces/export.py`
- Release that introduced the queued export: `reports/releases/2026.5.md`
- Release that shipped the fix: `reports/releases/2026.6.md`
- Test runs: `reports/test-runs/2026-06-30-release-2026.5.md`, `reports/test-runs/2026-08-11-release-2026.6.md`
- Architecture decision: ADR 0007 "Exports run as queued jobs" in `docs/architecture/adr/`
- Index: `docs/reference/release-and-incident-index.md`
- UI doc: `docs/ui/settings-workspace.md`

Last reviewed: 2026-11-26
