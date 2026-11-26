# Runbook: Stuck Export

**For:** support agents (finding and reporting a stuck export) and the on-call engineer (clearing it).

This runbook grew out of INC-2026-004 (2026-07-22, P2, 9 hours 40 minutes). Release 2026.5 had rewritten the workspace export as a queued job. Two weeks later, export workers lost their job leases and the exports stayed in `running` with no worker building them. There was no timeout, so they never ended. Because only one export per workspace may run at a time, those workspaces could not start a new export either. Since release 2026.6 an export that runs longer than 24 hours is marked `failed` automatically, and an alert warns much earlier.

## What are the symptoms of a stuck export?

- A customer says the export in **Settings → Workspace → Export** has shown "running" for many hours and no email has arrived.
- A customer tries to start an export and gets `ERR_CONFLICT`: "an export is already running for this workspace".
- The alert `export-running-too-long` fires. It fires when any export has been `running` for more than 6 hours.
- The export queue length in **Admin console → Operations → Queues** keeps growing.

## How long should an export normally take?

Most exports finish in under 1 hour. A workspace with several hundred GB of files can take up to about 10 hours. Time spent in `queued` depends on how busy the workers are and is normally under 15 minutes.

So a `running` export is not stuck just because it is slow. Use the lease, not the clock, to decide.

## How do I confirm an export is stuck?

1. Open **Admin console → Workspace → Exports** for the workspace (ID such as `ws_4H8P2L`).
2. Find the export (ID such as `exp_6J4D8S2A`) and read four values: status, start time, worker, and last lease renewal.
3. A healthy worker renews its lease every 60 seconds. Compare the last renewal with the current time:

| Status | Last lease renewal | Meaning |
|--------|--------------------|---------|
| `running` | Less than 5 minutes ago | Healthy. The export is still being built. Wait. |
| `running` | More than 5 minutes ago | Stuck. No worker is building it. |
| `queued` | Not applicable, and queued for more than 1 hour | Workers are not taking jobs. Treat as a worker problem. |
| `failed` | Any | Not stuck. The customer can start a new export. |

4. Check **Admin console → Operations → Queues → Export workers**. If 3 or more exports in the same region are stuck at once, it is a worker problem and not a single bad job.

## What do I do, step by step?

**Support agent**

1. Confirm with the table above. If the export is healthy, tell the customer it is still being built and give them the start time.
2. If it is stuck, page the on-call engineer with the workspace ID, the export ID and the last lease renewal time. Support agents cannot change an export's status.
3. Link the ticket (for example `SUP-58213`) to the incident if one is opened.

**On-call engineer**

1. Acknowledge the page within 5 minutes.
2. One stuck export: open **Admin console → Workspace → Exports**, select the export and choose **Requeue**. The status goes back to `queued`, a worker takes the job again, and the customer does not need to do anything.
3. If the requeued export is stuck again within 30 minutes, choose **Mark failed** and escalate to the Accounts team. Something in that workspace's data is breaking the worker.
4. Three or more stuck exports in one region: open an incident with priority P2. Go to **Admin console → Operations → Queues → Export workers** and select **Restart workers** for that region. Then requeue each stuck export.
5. Check after 10 minutes that every requeued export shows a lease renewal less than 5 minutes old.
6. Do not wait for the 24-hour timeout to clean up. It is a safety net. A customer should not wait a day to learn that their export failed.

Never copy a customer's files out by hand as a replacement for the export. Customer content is handled only by the export job.

## What happens if nobody does anything?

After 24 hours in `running` the export is marked `failed`. The one-export rule then no longer blocks the workspace, and the customer can start a new export. Nothing is lost except time: an export only reads data.

The 24 hours are counted from the moment the export became `running`. Time spent in `queued` is not included.

## What do I tell the customer?

- Healthy but slow: "Your export started at <time> and is still being built. Large workspaces can take several hours. You will get an email when it is ready, and the download link will work for 7 days."
- Stuck and requeued: "Your export had stopped because of a fault on our side. We have restarted it. You do not need to do anything; you will get an email when it is ready."
- Marked failed: "Your export could not be completed. Please start a new one from **Settings → Workspace → Export**. Your data is not affected."
- They need the data before closing the account: remind them that a closed account can be restored for 30 days, so they should not close it until the export is downloaded.

Only the Owner and Admins can start an export. If a Member asks, point them to their Admin.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| One export stuck | On-call engineer | 1 business hour of confirming |
| Three or more stuck in one region | On-call engineer opens a P2 incident | At once |
| Requeued export is stuck again | Accounts team | Same business day |
| Workers do not come back after a restart | Platform team lead | 30 minutes |
| Enterprise customer blocked from leaving or moving region | Raise the ticket to P2; first response in 2 hours | At once |

## What happens after the incident?

1. Confirm that no export in any region has a lease renewal older than 5 minutes.
2. Reply on every linked ticket.
3. For a P2, write the incident report under `reports/incidents/` within 5 business days. Record how many exports were stuck, for how long, and whether `export-running-too-long` fired.
4. If any export reached the 24-hour timeout without a person noticing, open a follow-up for the Platform team to review the alert.

## Related links

- Incident: `reports/incidents/INC-2026-004-stuck-exports.md`
- Releases: `reports/releases/2026.5.md` (queued export), `reports/releases/2026.6.md` (24-hour timeout)
- Decision: `docs/architecture/adr/0007-exports-run-as-queued-jobs.md`
- Code: `src/acme_cloud/workspaces/export.py`, `src/acme_cloud/workspaces/service.py`
- UI: `docs/ui/settings-workspace.md` ("How do I export workspace data?")
- Data model: `docs/architecture/data-model.md` ("What is stored for a Workspace and an Export?")

Last reviewed: 2026-11-26
