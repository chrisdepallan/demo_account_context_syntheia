# ADR 0002: Workspace region is fixed at creation

## Status

Accepted.

## Date

2025-03-04

## Context

Acme Cloud stores workspace content in a data region. When this decision was made there were two regions: `us-east` (Virginia) and `eu-central` (Frankfurt). A third, `ap-south` (Mumbai), was added in release 2026.4.

Customers choose a region for two reasons. Some want their data close to their users, for speed. Others have a contract or a law that says their data must stay in a certain place. The second group needs a promise they can show to an auditor: "this workspace's content is in Frankfurt and has never been anywhere else".

A workspace is not one row in one table. It has projects, files of up to 5 GB each, version history of up to a year or more, exports, API keys and webhook endpoints. Moving all of that between regions while people are working in it is a large and risky operation.

## Decision

A workspace's region is chosen when the workspace is created and **cannot be changed afterwards**.

- The region is one of `us-east`, `eu-central` or `ap-south`. The default is `us-east`.
- The plan limits the choice: `us-east` on all plans, `eu-central` on Business and Enterprise, `ap-south` on Enterprise only. Choosing a region the plan does not include returns `ERR_PLAN_REQUIRED`.
- There is no update operation for the region, in the dashboard, the API or the admin console. Support cannot change it either.
- To move, the customer exports the workspace from **Settings → Workspace → Export**, creates a new workspace in the other region, and adds the exported data to it.
- A later plan downgrade does not move or remove an existing workspace. It only stops new workspaces from being created in a region the lower plan does not include.
- A database failover promotes a standby replica inside the same region. Content never leaves its region because of a failure.

The region list and plan checks are in `src/acme_cloud/workspaces/regions.py`; the `Region` enum is in `src/acme_cloud/common/enums.py`.

## Alternatives considered

### Live migration between regions

An Owner could pick a new region and the system would copy the data across while the workspace stayed in use.

Rejected for three reasons. First, during the copy the data exists in two regions, which breaks the residency promise for exactly the customers who care most. Second, keeping files, versions and API key caches consistent across two regions during a move needs machinery far beyond the value of a rarely used feature. Third, a half-finished migration would be a new kind of incident with no simple rollback.

### Migration by support request, with downtime

Support would schedule a maintenance window, lock the workspace, copy it and unlock it in the new region.

Rejected because it is the export-and-recreate path with more manual steps and more staff access to customer data. The export feature already gives customers a way to do this themselves, at a time they choose, without anyone at Acme Cloud handling the content.

### Replicate every workspace to all regions

All content would live everywhere, and the "region" would only decide where requests are served from.

Rejected because it removes data residency completely, and multiplies storage cost by the number of regions.

## Consequences

Good:

- The residency statement is simple and always true: a workspace's content is stored in one region for its whole life.
- No code path writes workspace content across regions, so a whole class of consistency bugs cannot happen.
- Region failover stays a local operation. The `eu-central` outage of INC-2026-005 affected only `eu-central` workspaces.

Costs:

- A customer who picks the wrong region must export and start again. Workspace IDs, API keys, webhook endpoints and SSO connections belong to the old workspace and must be created again in the new one.
- The create-workspace screen has to make the choice very clear, because it cannot be undone.
- An account that upgrades to Business does not get its existing `us-east` workspace moved to `eu-central`. The upgrade only makes `eu-central` available for new workspaces.
- The export must be complete enough to act as the migration tool. This raised the importance of export reliability and is one reason exports were rewritten as queued jobs (ADR 0007).
- Account, billing and identity records are global, with their primary copy in `us-east`. The fixed-region promise covers workspace content, not invoices or login records. Customer-facing text must say "workspace data", not "all data".

## Related

- Code: `src/acme_cloud/workspaces/regions.py`, `src/acme_cloud/workspaces/service.py`, `src/acme_cloud/common/enums.py`
- UI: `docs/ui/settings-workspace.md` ("Can I change a workspace's region?"), `docs/ui/feature-availability.md`
- Architecture: `docs/architecture/overview.md` ("How are regions set up?")
- ADR: `docs/architecture/adr/0007-exports-run-as-queued-jobs.md`
- Runbook: `docs/runbooks/region-failover.md`
- Incident: `reports/incidents/INC-2026-005-eu-central-failover.md`
- Release: `reports/releases/2026.4.md` (`ap-south` region)

Last reviewed: 2026-11-26
