# ADR 0007: Exports run as queued jobs

## Status

Accepted. Replaces the synchronous export.

## Date

2026-05-12

## Context

Owners and Admins can export a workspace from **Settings → Workspace → Export**. The export is a ZIP file with JSON and the original files. It matters more than its place in the menu suggests: because a workspace's region is fixed at creation (ADR 0002), export is the only way to move a workspace to another region, and it is the customer's own backup before closing an account.

Until release 2026.5 the export was synchronous. The browser sent one request, the API built the ZIP while the request stayed open, and the response was the file. This worked for small workspaces and failed for large ones:

- Pro and higher plans allow single files of up to 5 GB and 50 GB or more of storage per seat. Building such a ZIP took longer than the API's 15-minute request limit, so the largest customers could never finish an export.
- A closed browser tab or a dropped connection threw the whole export away.
- Nothing stopped an Admin from clicking **Export** several times. Each click started another full build, and a few impatient clicks could slow the region's API nodes for everyone.
- Support could not see whether an export was in progress, because there was no record of it.

## Decision

A workspace export is a **queued background job** with a stored record and a status.

- Starting an export creates an Export record with an ID such as `exp_6J4D8S2A` and the status `queued`. The request returns at once.
- An export worker in the workspace's region takes the job, sets it to `running` and builds the ZIP.
- When the ZIP is complete the status becomes `ready`, the requester receives the `export_ready` email, and the `export.ready` webhook event is sent.
- The download link is valid for **7 days**. After that the status becomes `expired` and the ZIP is deleted.
- **One export per workspace** may be `queued` or `running`. A second request returns `ERR_CONFLICT` (HTTP 409).
- A job that cannot be completed ends as `failed`. The customer can then start a new one.
- The audit log records `export.started` and `export.downloaded`.
- Starting an export needs the `workspace.export` permission, held by the Owner and Admins.

The statuses are `queued`, `running`, `ready`, `expired` and `failed`. The code is in `src/acme_cloud/workspaces/export.py`.

## Alternatives considered

### Keep the synchronous export and raise the time limit

The request limit would go from 15 minutes to several hours, with the ZIP streamed as it is built.

Rejected because long-held requests are fragile: any deploy, node restart or network break ends them, and the customer starts again from zero. It does nothing about repeated clicks or about support having no record to look at.

### Queue exports, but allow several at once per workspace

Each click would create its own job.

Rejected because two exports of the same workspace started minutes apart are almost always a mistake. Parallel exports multiply the load of the most expensive operation in the product without giving the customer anything new. One at a time also makes the status easy to show: a workspace is either exporting or it is not.

### Nightly snapshots instead of on-demand exports

Every workspace would get an automatic ZIP each night, and **Export** would hand out the latest one.

Rejected because it does the heavy work for every workspace every night, though few customers ever download an export. The file would also be up to a day old, which is wrong for the "export, then close the account" case.

## Consequences

Good:

- Export size is no longer limited by a request timeout. Large workspaces can be exported.
- The customer can close the browser and come back; the email tells them when the file is ready.
- Load is bounded: at most one job per workspace, taken from a queue at the pace the workers can handle.
- Support and on-call engineers can see every export and its status in **Admin console → Workspace → Exports**.

Costs:

- There is new machinery to run: a queue, workers, and job leases. A worker holds a lease on its job and renews it every 60 seconds. If the lease is not renewed for 5 minutes, the job is treated as abandoned and returned to the queue.
- The first version got this wrong. On 2026-07-22, two weeks after release 2026.5, export workers lost their job leases and the affected exports stayed in `running` with nobody working on them. There was no timeout, so they never ended, and the one-export rule then blocked those workspaces from starting a new export. This was INC-2026-004 and lasted 9 hours 40 minutes.
- The fix shipped in release 2026.6: an export that runs longer than **24 hours** is marked `failed`, which frees the workspace to start another. The alert `export-running-too-long` warns the on-call engineer when any export has been `running` for more than 6 hours. See `docs/runbooks/stuck-export.md`.
- "One export per workspace" is now a user-visible rule that needs explaining. The dashboard disables the **Export** button while an export is `queued` or `running`.
- An export is a snapshot of the moment the worker reads each item, not of the moment the button was pressed. Changes made while it runs may or may not be in the ZIP.
- A `failed` export leaves no partial file. The customer has to start again.

## Related

- Code: `src/acme_cloud/workspaces/export.py`, `src/acme_cloud/workspaces/service.py`
- Rules: `docs/reference/constants-and-glossary.md`, section "What are the member and workspace rules?"
- UI: `docs/ui/settings-workspace.md` ("How do I export workspace data?")
- ADR: `docs/architecture/adr/0002-workspace-region-is-fixed-at-creation.md`
- Runbook: `docs/runbooks/stuck-export.md`
- Incident: `reports/incidents/INC-2026-004-stuck-exports.md`
- Releases: `reports/releases/2026.5.md` (queued export), `reports/releases/2026.6.md` (24-hour timeout)

Last reviewed: 2026-11-26
