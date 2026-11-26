# Access Review: Admin Console, First Half of 2026

This report reviews who had access to the internal admin console at `https://admin.acme-cloud.example` on 2026-06-30, which console role each staff account held, and who could issue refunds at which approval tier. It also checks every refund issued from 2026-01-01 to 2026-06-30 against the approval rules. All data is fictional sample data. Staff are referred to by role, not by name.

## What was reviewed, and by whom?

| Item | Value |
|------|-------|
| Period reviewed | 2026-01-01 to 2026-06-30 |
| Snapshot of accounts and roles | 2026-06-30 |
| Review carried out | 2026-07-06 to 2026-07-17 |
| Reviewers | The Support Tools team lead, an engineer from the Platform team and the billing manager |
| Staff accounts reviewed | 73 |
| Refunds checked | 487 (all refunds of the period), total $242,110 |
| Findings | 7: one high, three medium, three low |
| Status on 2026-11-26 | All 7 findings fixed |

The review covered 73 staff accounts and all 487 refunds of the first half of 2026. It produced 7 findings. None of them led to a refund outside policy, but two of them could have.

## Which console roles exist, and what can each do?

The admin console is owned by the Support Tools team. Staff sign in through the company's single sign-on with MFA. A staff account has exactly one console role.

| Console role | Who holds it | Can view accounts | Can issue refunds | Can change console roles |
|--------------|--------------|-------------------|-------------------|--------------------------|
| Support agent | Support agents | Yes | Yes, up to $500 | No |
| Support team lead | Support team leads | Yes | Yes, up to $5,000; approves all goodwill refunds | No |
| Billing manager | The billing manager and a deputy | Yes | Yes, any amount | No |
| Console administrator | Engineers of the Support Tools team | Yes | No | Yes |
| Read-only | Customer Success Managers, on-call engineers | Yes | No | No |

Only three roles can issue refunds, and the limit rises with the role. Console administrators manage roles but must not be able to move money, so that no single person can both grant a right and use it.

Rules that apply to every role: staff never ask for or accept a customer's password, full card number or MFA code; they never reset MFA or change the Owner based on email alone; and they never share one customer's data with another unless both are in the same workspace.

## Who can issue a refund at which tier?

| Refund amount | Approver required | Accounts with this right on 2026-06-30 | Accounts that should have had it |
|---------------|-------------------|----------------------------------------|----------------------------------|
| Up to $500 | Any support agent | 57 | 50 |
| $500.01 to $5,000 | Support team lead | 11 | 7 |
| Over $5,000 | Billing manager | 2 | 2 |

On the snapshot date, 11 accounts could approve refunds between $500.01 and $5,000, but only 7 should have been able to: 5 team leads and the 2 billing manager accounts. The four extra accounts are explained in findings 1, 2 and 3. For refunds over $5,000 the list was correct: only the billing manager and the deputy.

A higher role includes the lower tiers. That is why 57 accounts could issue a refund of up to $500: 45 support agents, 7 accounts with the team lead role, 2 billing manager accounts, 1 shared test account and the 2 console administrators from finding 1. Only 50 should have had the right: 43 support agents, 5 team leads and the 2 billing manager accounts.

Goodwill refunds need team-lead approval at any amount and are limited to one per account per 12 months.

## How many staff accounts were there, by role?

| Console role | Accounts on 2026-06-30 | Accounts after the fixes |
|--------------|------------------------|--------------------------|
| Support agent | 45 | 43 |
| Support team lead | 7 | 5 |
| Billing manager | 2 | 2 |
| Console administrator | 5 | 5 |
| Read-only | 13 | 8 |
| Shared test account (agent rights) | 1 | 0 |
| **Total** | **73** | **63** |

There were 73 accounts on the snapshot date and 63 after the fixes. Ten accounts were removed: 4 of staff who had moved to other teams, 5 unused read-only accounts and 1 shared test account. One account was moved from team lead back to support agent.

## What did the review find?

| ID | Severity | Finding | Fixed on |
|----|----------|---------|----------|
| AR-2026-H1-01 | High | 2 console administrators also had the team-lead refund right | 2026-07-07 |
| AR-2026-H1-02 | Medium | 4 accounts belonged to staff who had left the support team | 2026-07-08 |
| AR-2026-H1-03 | Medium | 1 support agent kept the team lead role 11 weeks after covering for a team lead | 2026-07-08 |
| AR-2026-H1-04 | Medium | The goodwill limit was checked per calendar year, not per 12 months | 2026-07-28 |
| AR-2026-H1-05 | Low | 9 refunds had no ticket number in the reason field | 2026-07-28 |
| AR-2026-H1-06 | Low | 5 read-only accounts had not been used for more than 90 days | 2026-07-08 |
| AR-2026-H1-07 | Low | 1 shared test account with agent rights had no named owner | 2026-07-07 |

There were 7 findings: 1 high, 3 medium and 3 low. All were fixed by 2026-07-28.

### AR-2026-H1-01: console administrators with a refund right

Two of the five console administrators could approve refunds up to $5,000. The right had been added in 2025 to test the refund screen and was never removed. A console administrator can also change roles, so these two accounts could have granted and used refund rights without a second person. Neither account issued or approved any refund in the period. The right was removed on 2026-07-07. The console now refuses to combine the console administrator role with any refund right.

### AR-2026-H1-02: accounts of staff who had moved teams

Three support agents and one team lead had moved to other teams between February and May 2026. Their console accounts were still active. None of the four accounts was used after the move date. The accounts were removed on 2026-07-08. Since 2026-08-03 the console checks the staff directory every night and disables the account of anyone who is no longer in a team that needs it.

### AR-2026-H1-03: a temporary role that stayed

One support agent was given the team lead role in March 2026 to cover a team lead's leave. The cover ended on 2026-04-17, but the role stayed until the review, 11 weeks later. In those 11 weeks the agent approved 6 refunds between $500.01 and $5,000, with a total of $9,840. A team lead and the billing manager reviewed all six afterwards. All six were inside the refund policy. The role was corrected on 2026-07-08. Temporary roles now need an end date of at most 30 days and end automatically.

### AR-2026-H1-04: goodwill limit counted by calendar year

The console blocked a second goodwill refund in the same calendar year. The rule is one per account per 12 months. Two accounts received a goodwill refund in late 2025 and another in the first half of 2026, less than 12 months apart. Both second refunds were under $200 and both had team-lead approval. The check was changed to a rolling 12 months on 2026-07-28.

### AR-2026-H1-05: missing ticket numbers

The process requires the support ticket number (for example `SUP-58213`) in the reason field of every refund. Nine of 487 refunds (1.8%) had free text only. The matching tickets were found by hand for all nine. Since 2026-07-28 the field must contain a ticket number in the form `SUP-` plus 5 digits before the refund can be saved.

### AR-2026-H1-06 and AR-2026-H1-07: unused and shared accounts

Five read-only accounts had not signed in for more than 90 days; they were removed, and accounts are now disabled automatically after 90 days without a login. A shared account used by engineers for testing in the production console had agent rights and no named owner. It had issued no refunds. It was removed, and refund testing now happens only in the staging console.

## Were the refunds of the period approved at the right tier?

| Refund amount | Refunds | Total amount | Approved at the required tier or higher |
|---------------|---------|--------------|-----------------------------------------|
| Up to $500 | 412 | $74,160 | 412 |
| $500.01 to $5,000 | 68 | $113,750 | 68 (62 by team leads, 6 by the agent in finding AR-2026-H1-03) |
| Over $5,000 | 7 | $54,200 | 7 |
| **Total** | **487** | **$242,110** | **487** |

Yes, as far as the console roles at the time are concerned. Every one of the 487 refunds was approved by an account that held the required role. Six approvals came from an account that should no longer have held the team lead role; those six were reviewed and confirmed.

Other checks on the 487 refunds:

- No refund was larger than the paid amount of its invoice minus earlier refunds.
- All 33 goodwill refunds (19 in Q1 and 14 in Q2) had team-lead approval. Two broke the 12-month limit (finding AR-2026-H1-04).
- All 7 refunds over $5,000 were approved by the billing manager or the deputy.
- Every refund produced a `refund.issued` audit event with the acting staff account.
- The quarterly totals match the quarterly service reports: 255 refunds and $130,970 in Q1, 232 refunds and $111,140 in Q2.

## What changed in the process after this review?

1. Role changes in the console need two people: one console administrator requests the change and another approves it.
2. Temporary roles end automatically after at most 30 days.
3. The console is checked against the staff directory every night.
4. Accounts are disabled after 90 days without a login.
5. The reason field of a refund must contain a ticket number.
6. The goodwill limit is checked over a rolling 12 months.
7. Access is reviewed every half year. The review for the second half of 2026 is planned for January 2027.

The external penetration test in September 2026 also looked at the admin console and found that staff sessions had no idle timeout. That is a separate finding, fixed in release 2026.8; see `reports/security/2026-penetration-test-summary.md`.

Last reviewed: 2026-11-26
