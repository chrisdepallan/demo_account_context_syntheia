# ADR 0001: One Owner per account

## Status

Accepted.

## Date

2025-02-10

## Context

An account is the billing and legal owner of everything inside it: workspaces, members, invoices and the contract with Acme Cloud. Some actions on an account are final or expensive to undo:

- closing the account, which leads to permanent deletion on day 31;
- handing the account to someone else;
- acting as the last resort login when single sign-on is broken.

Early designs let any Admin do all of these. Support then had no clear answer to two common questions: "who is allowed to close this account?" and "two Admins disagree, whose instruction do we follow?". The second question came up most often when a company was splitting up or when an employee was leaving on bad terms.

We also needed one person whom the product can always reach about billing failures and closure, without first working out which of several people is responsible.

## Decision

Every account has **exactly one Owner** at all times.

- The role `owner` is held by one Member. The account cannot exist with zero Owners or with two.
- The person who creates the account is its first Owner.
- Two permissions belong to the Owner alone: `account.transfer` and `account.close`. The Owner also has every permission an Admin has, plus `billing.read` and `billing.manage`.
- The Owner changes only through an ownership transfer. The target must already be an Admin and must accept within **7 days**. On acceptance the previous Owner becomes an Admin, so the count stays at one.
- The Owner cannot be removed from the account and cannot lower their own role. They must transfer ownership first.
- When **Enforce SSO** is on, the Owner keeps password plus MFA as a break-glass login. Everyone else on the verified domain must use SSO.

The rule is enforced in `src/acme_cloud/accounts/ownership.py` and `src/acme_cloud/accounts/members.py`, and the permission table is in `src/acme_cloud/accounts/permissions.py`.

## Alternatives considered

### Several Owners per account

Any number of members could hold the Owner role, as long as at least one remained.

Rejected because it does not answer the dispute question. If two Owners give opposite instructions (one closes the account, the other asks support to restore it), support has no rule to follow. It also widens the break-glass exception under Enforce SSO: every extra Owner is one more password login that bypasses the identity provider.

### No Owner role; Admins hold all powers

Closure and transfer would be ordinary Admin permissions.

Rejected because Admin is given out freely, often to team leads and IT staff, so that they can invite members and change security settings. Giving each of them the power to delete the whole account is too risky. We would have needed a second approval step on closure, which is the Owner role under another name.

### Owner is an organisation contact, not a member

The legal owner would be a company record with a contact email, separate from any user.

Rejected because a contact that cannot log in cannot confirm actions inside the product. Every closure and transfer would have become a support ticket.

## Consequences

Good:

- There is always one clear answer to "who can close or transfer this account?".
- Billing and closure emails (`trial_ending`, `account_closed`, `key_expiring`) have one certain recipient.
- The Enforce SSO break-glass exception covers one login only.
- Support can refuse account-level requests from anyone who is not the Owner without needing judgement.

Costs:

- If the Owner leaves the company or cannot be reached, the account is stuck until support acts. This needs a manual process with written confirmation from a company officer, and takes up to **5 business days**. See `docs/runbooks/unreachable-owner-transfer.md`.
- If the Owner loses their MFA device and backup codes, no one inside the account can reset it for them. Support must do it, in up to **2 business days**. See `docs/runbooks/mfa-reset-for-locked-out-owner.md`.
- Transfers need two steps (request, then acceptance). Until release 2026.8 a transfer took effect at once; the 7-day acceptance step was added so that nobody becomes Owner, and so becomes responsible for billing, without agreeing to it.
- Owners who want a deputy for billing must use the `billing_admin` role. A Billing admin can pay and change the plan but cannot close or transfer the account.

## Related

- Code: `src/acme_cloud/accounts/ownership.py`, `src/acme_cloud/accounts/permissions.py`, `src/acme_cloud/accounts/members.py`
- Role table: `docs/reference/constants-and-glossary.md`, section "What are the roles and what can each do?"
- UI: `docs/ui/settings-account.md` (transfer ownership, close account), `docs/ui/settings-members.md` (who can do what), `docs/ui/settings-security.md` (Enforce SSO)
- Runbooks: `docs/runbooks/unreachable-owner-transfer.md`, `docs/runbooks/mfa-reset-for-locked-out-owner.md`
- Release: `reports/releases/2026.8.md` (acceptance within 7 days)
- Audit events: `ownership.transfer_requested`, `ownership.transferred`

Last reviewed: 2026-11-26
