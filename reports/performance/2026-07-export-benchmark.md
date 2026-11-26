# Workspace Export Benchmark: July 2026

This report describes a benchmark of the workspace export after release 2026.5, which rewrote the export as a queued job. It measured how long an export takes for workspaces from 1 GB to 500 GB, how several exports behave at the same time, and what happens when a worker fails. The last part found the missing timeout that caused INC-2026-004 one week later. All data is fictional sample data.

## What were the key facts of the benchmark?

| Item | Value |
|------|-------|
| Benchmark dates | 2026-07-13 to 2026-07-15 |
| Code under test | Release 2026.5 (shipped 2026-07-07) |
| Environment | Staging in `us-east`, with a pool of 8 export workers |
| Run by | Platform team with the Accounts team |
| Why it was run | Condition of the go decision for release 2026.5 |
| Result | Speed and concurrency: passed. Failure handling: failed, 2 findings |

The queued export handled every size up to 500 GB, which the old export could not do. But when a worker was stopped abruptly, 2 of 6 jobs stayed in `running` for good, and nothing in the product ended them.

## How does the queued export work?

- The Owner or an Admin starts the export in **Settings → Workspace → Export**, or through the API. It needs the `workspace.export` permission.
- The export gets an ID such as `exp_6J4D8S2A` and the status `queued`.
- A worker takes the job and sets it to `running`. While it works, it holds a lease on the job and renews it.
- The result is a ZIP with JSON and the original files. The status becomes `ready`, and the requester gets the `export_ready` email.
- The download link is valid for 7 days; then the status is `expired`.
- Only one export per workspace can be `queued` or `running`. A second request fails with `ERR_CONFLICT` (HTTP 409).

Before release 2026.5 the export ran inside the web request. That worked for small workspaces only.

## How long does an export take for each workspace size?

Each size was exported three times on an idle worker pool. The table shows the middle value of the three runs.

| Workspace size | Files | Time from start to `ready` | Speed |
|----------------|-------|----------------------------|-------|
| 1 GB | 2,000 | 3 minutes | 0.33 GB/minute |
| 5 GB | 10,000 | 8 minutes | 0.63 GB/minute |
| 10 GB | 20,000 | 14 minutes | 0.71 GB/minute |
| 50 GB | 100,000 | 58 minutes | 0.86 GB/minute |
| 100 GB | 200,000 | 1 hour 52 minutes | 0.89 GB/minute |
| 250 GB | 500,000 | 4 hours 41 minutes | 0.89 GB/minute |
| 500 GB | 1,000,000 | 9 hours 36 minutes | 0.87 GB/minute |

A 1 GB workspace took 3 minutes and a 500 GB workspace took 9 hours 36 minutes. From 50 GB upwards the speed was steady at a little under 0.9 GB per minute, so the time grows in a straight line with the size: roughly 11 minutes for every 10 GB plus a fixed start-up time of about 2 minutes. Small exports look slower per GB because of that start-up time.

The three runs of each size were close together. The largest spread was at 500 GB: 9 hours 21 minutes, 9 hours 36 minutes and 9 hours 52 minutes.

## How does this compare with the old export?

| Workspace size | Old export (in the web request) | Queued export (release 2026.5) |
|----------------|----------------------------------|--------------------------------|
| 1 GB | 4 minutes | 3 minutes |
| 10 GB | 21 minutes | 14 minutes |
| 50 GB | Failed: the request timed out | 58 minutes |
| 100 GB and more | Failed: the request timed out | Completed |

The old export failed for every tested size from 50 GB upwards, because the web request timed out before the ZIP was complete. The queued export completed every size. For small workspaces it is also faster, by about one third at 10 GB.

## What happens when many exports run at the same time?

Several workspaces of 10 GB each started an export at the same moment. The pool had 8 workers, and one worker handles one export at a time.

| Exports started together | Average wait in `queued` | Average time in `running` | Last export `ready` after |
|--------------------------|--------------------------|---------------------------|---------------------------|
| 4 | Under 10 seconds | 14 minutes | 14 minutes |
| 8 | Under 10 seconds | 15 minutes | 16 minutes |
| 16 | 8 minutes | 15 minutes | 31 minutes |
| 32 | 23 minutes | 15 minutes | 62 minutes |

Up to 8 exports at once, nothing waits, because there are 8 workers. Above that, exports wait in `queued` until a worker is free. With 32 exports the average wait was 23 minutes and the last one was `ready` after 62 minutes. Running 8 exports at once slowed each one by only about 1 minute, so the workers do not get in each other's way.

Other checks in this part:

- **One export per workspace.** While an export was `queued` or `running`, a second request for the same workspace was sent 200 times. All 200 were refused with `ERR_CONFLICT`.
- **Order.** Jobs were taken in the order in which they were requested.
- **Regions.** A short check in `eu-central` and `ap-south` staging with 10 GB gave 14 and 15 minutes. Each region has its own queue and workers; data does not leave its region during an export.
- **Large jobs block workers.** One 500 GB export keeps one of the 8 workers busy for more than 9 hours. Four such exports would halve the pool for a working day.

## What happens when a worker fails during an export?

A worker was stopped 12 times in the middle of a 10 GB export: 6 times with a normal shutdown and 6 times abruptly, as in a crash.

| How the worker was stopped | Tests | Job taken over by another worker | Job stayed in `running` |
|----------------------------|-------|----------------------------------|-------------------------|
| Normal shutdown (worker gives the lease back) | 6 | 6, within 2 minutes | 0 |
| Abrupt stop (worker cannot give the lease back) | 6 | 4, after the lease ran out (about 5 minutes) | 2 |
| **Total** | **12** | **10** | **2** |

Ten of 12 interrupted jobs were finished by another worker. Two were not. In both cases the worker had been stopped abruptly at the moment it was renewing its lease, and the lease was left in a state that no other worker would take over. Both jobs still showed `running` six hours later, when the test was ended and they were reset by hand.

For the customer, a stuck job is worse than a failed one. The page shows "Running" without end, and because only one export per workspace is allowed, a new export cannot be started.

## What was the missing timeout?

The benchmark found that an export had **no upper time limit**. The status `failed` could be set only when the storage reported an error. A job that simply never finished stayed `running` for ever.

The gap had already been noted at the code freeze for release 2026.5 on 2026-06-30, when a test was stopped by the test runner and not by the product. The benchmark confirmed it with real stuck jobs.

Recommendations made on 2026-07-15:

1. Mark an export as `failed` when it has run for longer than 24 hours. The slowest measured export (500 GB) took 9 hours 36 minutes, so 24 hours leaves a wide margin.
2. Fix the lease so that an abruptly stopped worker always loses it.
3. Alert the on-call engineer when any export has been `running` for more than 12 hours.
4. Tell the requester when an export fails, and let them start a new one.

Both fixes were planned for release 2026.6 on 2026-08-18. They were not treated as urgent, because the stuck jobs had appeared only when a worker was stopped on purpose.

## How does this relate to INC-2026-004?

On 2026-07-22, seven days after the benchmark ended, the same thing happened in production. An export worker lost its job lease, exports stayed in `running`, and customers could not start new ones. The incident lasted 9 hours 40 minutes and was rated P2.

- The cause matches finding 1 and finding 2 of this benchmark: the lease problem from the 2026.5 rewrite, and no timeout.
- The fix shipped as planned in release 2026.6: exports running longer than 24 hours are marked `failed`. The runbook `docs/runbooks/stuck-export.md` was written.
- What should have been done differently: the two stuck jobs in the benchmark were a clear warning. An alert (recommendation 3) could have been added within a day, without waiting for a release, and would have shortened the incident.

## What were the findings?

| No. | Finding | Severity | Status |
|-----|---------|----------|--------|
| 1 | An export has no upper time limit and can stay `running` for ever | High | Fixed in release 2026.6: `failed` after more than 24 hours |
| 2 | An abruptly stopped worker can leave a lease that no other worker takes over (2 of 6 tests) | High | Fixed in release 2026.6 |
| 3 | Large exports hold a worker for hours and can make small exports wait | Medium | Open: separate workers for exports above 100 GB are planned for 2027 |
| 4 | Workspaces above about 1,250 GB would not finish within 24 hours at the measured speed | Low | Open: 3 workspaces were above 1,000 GB in July 2026; the Accounts team contacts those customers before an export |

There were four findings. The two high findings are fixed. Finding 4 follows from the new limit: at 0.87 GB per minute, 24 hours are enough for about 1,250 GB. Enterprise accounts get 1 TB of storage per seat, so a few workspaces can be larger than that.

## What should be done next?

1. Repeat the benchmark after the worker pools are split by export size.
2. Add a 1 TB test workspace, so the largest realistic size is measured and not estimated.
3. Run the failure tests (a stopped worker, a lost lease) in every region each quarter, together with the replica promotion test.

Last reviewed: 2026-11-26
