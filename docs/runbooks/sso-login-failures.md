# Runbook: SSO Login Failures

**For:** support agents (one workspace affected) and the on-call engineer (many workspaces affected).

This runbook grew out of INC-2026-003 (2026-05-06, P2, 2 hours 25 minutes). SAML logins were rejected with "signature invalid" for 38 workspaces. The cause was not a signature problem: the clocks on two auth nodes had drifted by 4 minutes, which is more than the 3 minutes of clock skew allowed on SAML assertions. Since release 2026.4 the alert `auth-clock-drift` fires when any auth node is more than 30 seconds off, long before logins fail.

## What are the symptoms?

- Users cannot sign in through SSO at `https://app.acme-cloud.example/login`.
- The login page shows "SAML response signature invalid", "SAML assertion expired or not yet valid", or "No SSO connection for this email domain".
- Password login may be unavailable too, because **Enforce SSO** disables it for everyone on the verified domain except the Owner.
- Tickets arrive from Business and Enterprise customers only. SSO is not available on lower plans.

## How do I tell a customer problem from a platform problem?

The first question is always: one workspace or many?

| What you see | Most likely cause | Who acts |
|--------------|-------------------|----------|
| One workspace, "signature invalid" | The identity provider rotated its certificate | Support agent with the customer |
| One workspace, "No SSO connection for this email domain" | The domain is not verified, or the user's email is on another domain | Support agent with the customer |
| One workspace, some users only | Wrong NameID format, or the user is not assigned to the app in the identity provider | Support agent with the customer |
| 5 or more workspaces within 10 minutes, any message | Platform problem: clock drift or an auth node fault | On-call engineer |
| Logins succeed and fail at random for the same user | Some auth nodes are healthy and some are not: clock drift | On-call engineer |

To confirm:

1. Open **Admin console → Account → Security → SSO**. It shows the SSO connection (ID such as `sso_7Q3W9E`), whether it is enabled and enforced, the verified domain, and the last 20 login errors with the auth node that handled each one.
2. Open **Admin console → Operations → Auth nodes**. It shows the clock drift of every auth node in every region and the count of SSO errors per workspace for the last hour.
3. If any node shows drift above 30 seconds, or 5 or more workspaces show errors in the same 10 minutes, it is a platform problem. Page the on-call engineer and go to the on-call steps below.

## What do I do when one workspace is affected? (support agent)

1. Read the last errors in **Admin console → Account → Security → SSO**.
2. For "signature invalid": ask an Owner or Admin whether the identity provider's certificate was renewed. They upload the new certificate in **Settings → Security → SSO**, select **Test connection**, and try again.
3. For a domain error: ask them to check that the DNS TXT record `acme-verify=<token>` is still present on the domain. Removing the record removes the verification.
4. For single users: ask them to check that the identity provider sends the NameID in the `emailAddress` format, and that the user is assigned to the Acme Cloud app.
5. Ask them to check the values copied into the identity provider:
   - ACS URL: `https://auth.acme-cloud.example/saml/acs/{workspace_id}`
   - Entity ID: `https://auth.acme-cloud.example/saml/{workspace_id}`
6. If nobody can get in to change the settings, the Owner uses the break-glass login: email and password plus MFA. The Owner is never blocked by **Enforce SSO**. The Owner can then fix the connection or turn **Enforce SSO** off for a while.
7. If the Owner has lost their MFA device as well, follow `docs/runbooks/mfa-reset-for-locked-out-owner.md`.

Support never turns off SSO or **Enforce SSO** for a customer. Only the customer's Owner or an Admin does that.

## What do I do when many workspaces are affected? (on-call engineer)

1. Acknowledge the page within 5 minutes. Open an incident: P2 if some logins still work, P1 if SSO login is failing for everyone in a region.
2. Open **Admin console → Operations → Auth nodes** and sort by clock drift.
3. For every node with drift above 30 seconds, select **Drain**. The node finishes its current requests and takes no new ones. Never drain the last healthy node in a region; if all nodes have drifted, escalate at once.
4. Check that errors stop. The error count per workspace should fall to zero within 5 minutes of draining.
5. Fix the time source on the drained nodes, check that drift is below 1 second, and select **Return to pool**.
6. If no node has drifted, look at the errors by connection type. Failures only on OIDC connections (added in release 2026.8) or only on SAML point to a fault in that code path. Escalate to the Identity team.
7. Post on the status page at `https://status.acme-cloud.example`. For a P1 this must happen within 15 minutes.

Do not raise the allowed clock skew above 3 minutes to make the errors go away. The limit protects against replayed assertions.

## What do I tell the customer?

- Certificate rotation: "Your identity provider is now signing with a new certificate. Please upload it in **Settings → Security → SSO** and select **Test connection**."
- Platform problem: "Some single sign-on logins are failing because of a fault on our side. Your SSO settings are correct; please do not change them. Your account Owner can still sign in with email, password and MFA."
- After the fix: "Single sign-on is working again. Users who saw an error can simply sign in again."

Tell customers not to rotate certificates or rebuild the connection during a platform incident. Changes made then often create a second, real problem.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| 5 or more workspaces failing in 10 minutes | On-call engineer | At once |
| All auth nodes in a region drifted, or draining did not help | Identity team | 15 minutes |
| One workspace, not solved after the checks above | Identity team, through the ticket | 1 business day |
| Enterprise customer fully locked out | Raise the ticket to P1; first response in 30 minutes, 24/7 | At once |

## What happens after the incident?

1. Confirm that `auth-clock-drift` is clear in all three regions.
2. Reply on every linked ticket.
3. For a P1 or P2, write the incident report under `reports/incidents/` within 5 business days, with the number of workspaces affected and the highest drift seen.
4. If the alert did not fire before logins failed, open a follow-up for the Platform team.

## Related links

- Incident: `reports/incidents/INC-2026-003-saml-clock-skew.md`
- Releases: `reports/releases/2026.4.md` (clock drift alert), `reports/releases/2026.8.md` (OIDC SSO)
- Code: `src/acme_cloud/auth/sso.py`, `src/acme_cloud/auth/policies.py`, `src/acme_cloud/auth/service.py`
- UI: `docs/ui/settings-security.md` ("How do I set up SAML SSO?", "How do I fix 'SAML response signature invalid'?"), `docs/ui/login-and-profile.md`
- Decision on the Owner's break-glass login: `docs/architecture/adr/0001-one-owner-per-account.md`
- Other runbooks: `docs/runbooks/mfa-reset-for-locked-out-owner.md`

Last reviewed: 2026-11-26
