# Runbook: Region Failover

**For:** the on-call engineer.

This runbook grew out of INC-2026-005 (2026-09-08, P1, 1 hour 12 minutes). The primary database in `eu-central` failed and the standby replica was not promoted automatically, so the dashboard was unavailable in `eu-central` until an engineer promoted it by hand. Since release 2026.7, automatic replica promotion is tested every quarter in every region, and this runbook gives the manual steps for when it still does not happen.

## How is a region built?

Each of the three regions (`us-east` in Virginia, `eu-central` in Frankfurt, `ap-south` in Mumbai) has a primary database and one standby replica in a second availability zone of the same region. "Failover" means promoting that standby to primary.

Failover never moves data to another region. A workspace's region is fixed at creation (`docs/architecture/adr/0002-workspace-region-is-fixed-at-creation.md`), and an `eu-central` workspace stays in Frankfurt even during an outage.

## What are the symptoms?

- The alert `region-db-primary-down` fires for one region.
- The dashboard at `https://app.acme-cloud.example` shows errors for users whose workspaces are in that region. Workspaces in other regions keep working.
- API calls for that region's workspaces return `ERR_INTERNAL` (HTTP 500).
- If the region is `us-east`, login and billing fail in all regions as well, because the primary copy of account, billing and identity records is in `us-east`.

## How do I confirm the primary is down?

1. Open **Admin console → Operations → Regions** and select the region.
2. Read three values: primary health, replica health, and replica lag in seconds.
3. The primary is down if its health check has failed for 60 seconds in a row.
4. Check whether automatic promotion has started. The screen shows "Promotion: in progress" with a start time. Automatic promotion should finish within 2 minutes of the primary going down.
5. If the primary and the replica are both down, this is not a failover. Go straight to escalation.

## What do I do, step by step?

1. **Acknowledge the page** within 5 minutes and open a P1 incident.
2. **Post on the status page** at `https://status.acme-cloud.example` within 15 minutes of the start. Name the region.
3. **Wait for automatic promotion**, but only until 5 minutes after the primary went down. If the screen shows "Promotion: complete", skip to step 7.
4. **Check replica lag** before promoting by hand:
   - Lag of 30 seconds or less: continue to step 5.
   - Lag above 30 seconds: stop. Promoting now would lose the most recent writes. Call the Platform team lead before doing anything else.
5. **Promote by hand.** Select **Admin console → Operations → Regions → Promote replica** for the region. Type the region code, for example `eu-central`, to confirm.
6. **Wait for the promotion to finish.** This normally takes under 2 minutes. The screen then shows the old replica as "primary".
7. **Check the region is serving.** On the same screen, **Run health check** must be green for the dashboard, API and auth nodes. Then check that the error rate in the region has returned to normal.
8. **Check the queues** in **Admin console → Operations → Queues** for the region. Exports that were `running` during the outage may have lost their worker. Requeue them as described in `docs/runbooks/stuck-export.md`.
9. **Do not bring the old primary back as primary.** Leave it out of service. It will be rebuilt as the new standby.
10. **Update the status page** when the health check has been green for 15 minutes.

## What is different when the region is `us-east`?

- The effect is wider: users in `eu-central` and `ap-south` cannot log in or change billing, although their workspace content is intact.
- Charges fail while the primary is down. They fail on our side, not at the payment processor, so processor outage mode does not start by itself. After promotion, open **Admin console → Operations → Payments → Outage review** and reverse any dunning failures recorded during the outage, as in `docs/runbooks/payment-processor-outage.md`.
- If a release is being deployed, stop it. Releases go to `us-east` first, and a release must not continue to the other regions during or after a failover on the same day.

## What do I tell the customer?

- During: "Workspaces in the <region> region are unavailable because of a database fault. We are switching to the standby database. Your data stays in <region>."
- After: "Service in <region> was restored at <time>. Changes saved before <start time> are intact. If you were editing at the moment of the fault, please check your last change."
- If asked whether data was moved abroad: "No. The standby database is in the same region. Data never leaves the region because of a failure."
- Exports and webhook deliveries that failed during the outage: exports are restarted by us; webhook deliveries are retried automatically for up to 24 hours.

Enterprise customers get a P1 first response within 30 minutes, 24/7. Their named Customer Success Manager should be told as soon as the incident is opened.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| Automatic promotion did not finish 5 minutes after the primary went down | You promote by hand; tell the Platform team lead | At once |
| Replica lag above 30 seconds | Platform team lead, before promoting | At once |
| Primary and replica both down | Platform team lead and the Accounts team | At once |
| Manual promotion fails or takes more than 10 minutes | Platform team lead | At once |
| Region is `us-east` | Billing team and Identity team as well | 15 minutes |

## What happens after the incident?

1. **Rebuild the standby.** The region runs without a standby until this is done. The Platform team rebuilds it within 24 hours. A second failure before then would be a full regional outage.
2. Confirm that replica lag on the new standby is under 30 seconds and that `region-db-primary-down` is clear.
3. Write the incident report under `reports/incidents/` within 5 business days. Record when the primary failed, whether automatic promotion started, when the replica was promoted, and replica lag at promotion.
4. If automatic promotion did not work, the next quarterly test for that region is brought forward to within 10 business days.

## How is automatic promotion tested?

Once a quarter, in each region, the Platform team stops the primary on purpose during a low-traffic window and measures how long promotion takes. The test passes if promotion finishes within 2 minutes with no manual action. Customers are told on the status page 3 business days before. A failed test is treated as a P2 incident, even though no customer was affected.

## Related links

- Incident: `reports/incidents/INC-2026-005-eu-central-failover.md`
- Release: `reports/releases/2026.7.md`
- Architecture: `docs/architecture/overview.md` ("How are regions set up?"), `docs/architecture/adr/0002-workspace-region-is-fixed-at-creation.md`
- Code: `src/acme_cloud/workspaces/regions.py`, `src/acme_cloud/common/enums.py`
- UI: `docs/ui/settings-workspace.md` (regions), `docs/ui/help-and-support.md` (status page)
- Other runbooks: `docs/runbooks/stuck-export.md`, `docs/runbooks/payment-processor-outage.md`

Last reviewed: 2026-11-26
