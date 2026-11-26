# INC-2026-003: SAML Logins Rejected Because of Clock Skew

Blameless postmortem. All data is fictional sample data for Acme Cloud.

| Field | Value |
|-------|-------|
| Incident ID | INC-2026-003 |
| Date | 2026-05-06 (Wednesday) |
| Priority | P2 |
| Duration | 2 h 25 min (07:40 to 10:05 UTC) |
| Regions | `eu-central` |
| Customers affected | 38 workspaces in 29 accounts; 613 users; 1,140 rejected logins |
| Detected by | Customer reports to support (first ticket at 07:58 UTC) |
| Owning team | Identity team (owns `auth`) |
| Supporting team | Platform team (infrastructure) |

## What happened?

On 2026-05-06, SAML logins for 38 workspaces were rejected with the message "SAML response signature invalid". The failures happened only when a login was handled by one of two auth nodes in `eu-central`.

The clocks on those two nodes were 4 minutes behind. The allowed clock skew on SAML assertions is 3 minutes. The nodes saw each new assertion as "issued in the future" and rejected it.

The signatures and the certificates were valid the whole time. The error message pointed in the wrong direction, and that cost about an hour.

## What was the customer impact?

- 38 workspaces in 29 accounts had at least one rejected SAML login. All were on Business or Enterprise, because SSO needs the Business plan or higher.
- 613 users were rejected at least once. In total 1,140 logins were rejected.
- `eu-central` had six auth nodes. Two were affected, so about one login in three failed. A user who tried again often got in. This made the problem look random.
- 22 of the 38 workspaces had **Enforce SSO** turned on. Their users had no password login to fall back on. Only the Owner could use the break-glass login with password and MFA.
- 6 customers uploaded their certificate again under **Settings → Security → SSO**, because support advised it. This was not needed and did not help.
- Users with an existing session were not affected. Password logins and API keys were not affected. `us-east` was not affected.
- 31 support tickets were opened.

## What is the timeline?

All times are UTC on 2026-05-06.

| Time | Event |
|------|-------|
| 07:38 | Planned host maintenance pauses two of the six auth nodes in `eu-central`. They resume with clocks 4 minutes behind. The time sync service does not restart on either node. |
| 07:40 | First SAML login is rejected with "SAML response signature invalid". |
| 07:58 | First support ticket. |
| 08:20 | Support answers with the standard advice for this message: the identity provider rotated its certificate, upload the new one. |
| 08:47 | A third customer replies that their certificate did not change. The support team lead escalates to the Identity team. |
| 08:55 | The Identity team's on-call engineer declares a P2 incident. |
| 09:10 | Logs show that all rejections come from two nodes. The other four nodes accept logins for the same workspaces. |
| 09:25 | First theory: the two nodes run a different build. The builds are compared and are identical. |
| 09:48 | A time check on the two nodes shows clocks 4 min 6 s and 4 min 2 s behind. |
| 09:55 | Mitigation: both nodes are taken out of the load balancer. SAML logins succeed for all workspaces. |
| 10:05 | The time sync service is restarted on both nodes. Clocks are correct. The nodes are put back. Incident resolved. |
| 10:30 | Support sends a correction to all 31 tickets: no certificate change is needed. |

## What was the root cause?

Clock drift of 4 minutes on two auth nodes, above the 3-minute allowed skew.

There were two parts:

1. **Infrastructure.** After the host maintenance at 07:38, the two nodes resumed with the time of the moment they were paused. The time sync service should have corrected this within seconds. It had stopped and was not set to restart by itself.
2. **Application.** The SAML check in `src/acme_cloud/auth/sso.py` compares the assertion's validity window with the node's clock, with 3 minutes of tolerance. An assertion issued "4 minutes in the future" fails this check. The code reported every failed assertion check with the same customer message, "SAML response signature invalid", although the signature was fine.

## Why was it not caught earlier?

- There was no alert on clock drift. Node health checks tested CPU, memory and HTTP answers, not time.
- The SSO error-rate alert looked at all six nodes together. A failure rate near 33% for SAML in one region stayed below the 50% threshold.
- The unit tests for clock skew passed. They tested the 3-minute rule itself (2 min 59 s accepted, 3 min 1 s rejected), not what message the customer sees.
- The same maintenance had run in `us-east` the week before without a problem, because the time sync service restarted there.

## What went well?

- Once the logs were grouped by node, the two bad nodes were found in 15 minutes.
- Removing the nodes from the load balancer fixed logins at once and was safe: four nodes were enough for the morning load.
- No data was at risk. The failure mode was "reject a valid login", never "accept an invalid one".
- The break-glass login for Owners worked as designed for the 22 workspaces with Enforce SSO.

## What went badly?

- Detection came from customers, 18 minutes after the first failure. The incident was declared 75 minutes after the first failure.
- The error message matched a known cause (certificate rotation, see `docs/ui/settings-security.md`). Support followed the documented advice, which was wrong for this case, and 6 customers changed a working configuration.
- 23 minutes went into comparing builds before anyone checked the time on the nodes.
- No runbook existed for SSO login failures, so the checks were done in no fixed order.

## What are the action items?

| Action | Owning team | Due date | Status | Shipped in |
|--------|-------------|----------|--------|------------|
| Clock drift alert: page the on-call engineer when any node is more than 30 seconds away from the reference time. | Platform team | 2026-05-26 | Done | 2026.4 |
| Write the runbook `docs/runbooks/sso-login-failures.md`. Step 1 is "group failures by node"; step 2 is "check node time". | Identity team | 2026-05-26 | Done | 2026.4 |
| Write the real reason for a rejected assertion to the auth log (signature, validity window, audience). The customer message is unchanged. | Identity team | 2026-05-26 | Done | 2026.4 |
| Make the time sync service restart by itself on every node and take a node out of rotation while its drift is above 30 seconds. | Platform team | 2026-05-26 | Done | 2026.4 |
| Alert on the SSO failure rate per node, not only per region. | Identity team | 2026-05-26 | Done | 2026.4 |
| Add a note to the support reply for "signature invalid": check the status page and the node logs before advising a certificate upload. | Support Tools team | 2026-05-13 | Done | Not tied to a release |

The first two rows are the follow-up listed in `docs/reference/release-and-incident-index.md`.

## Why is the alert at 30 seconds when the allowed skew is 3 minutes?

The 3-minute skew is the limit at which customers are affected. The alert has to fire long before that. At 30 seconds the on-call engineer is paged while every login still works, and the node is taken out of rotation automatically. The allowed skew for customers stays at 3 minutes; it was not changed.

## What is related?

- Runbook: `docs/runbooks/sso-login-failures.md`
- Code module: `src/acme_cloud/auth/sso.py`
- Release that shipped the fix: `reports/releases/2026.4.md`
- Index: `docs/reference/release-and-incident-index.md`
- UI doc: `docs/ui/settings-security.md` ("How do I fix SAML response signature invalid?")
- SSO values (ACS URL, Entity ID, allowed skew): `docs/reference/constants-and-glossary.md`

Last reviewed: 2026-11-26
