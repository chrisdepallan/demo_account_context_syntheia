# Runbook: Ownership Transfer When the Owner Is Unreachable

**For:** support agents. A support team lead approves every transfer.

Every account has exactly one Owner, and normally only the Owner can hand the account to someone else (**Settings → Account → Transfer ownership**). When the Owner has left the company, is seriously ill, has died, or simply does not answer, the account is stuck: nobody can close it or transfer it, and if the Owner was also the only person with billing access, nobody can pay. Support can then move ownership to an existing Admin. The promise to the customer is **up to 5 business days**. This runbook did not come out of an incident; it is the cost of the one-Owner rule recorded in `docs/architecture/adr/0001-one-owner-per-account.md`.

## When does this runbook apply?

All of these must be true:

- The person asking is an **Admin** of the account and is signed in when they ask.
- The Owner cannot or will not act. If the Owner can sign in, they must do the transfer themselves.
- The Admin who is to become Owner agrees.

It does not apply when:

- The Owner is reachable but locked out by MFA. Use `docs/runbooks/mfa-reset-for-locked-out-owner.md`.
- The person asking is a Member, Guest, Billing admin or someone outside the account. Ask them to find an Admin.
- The account has no Admin at all. Escalate to the support team lead on the first day; this needs the Accounts team.
- Two Admins each ask to become Owner. Stop and escalate. Support does not choose between them.

## What are the symptoms?

- An Admin writes that the Owner has left and that they need to manage billing or close the account.
- The account is `past_due` or `read_only` and the people still using it do not see **Settings → Billing**, because they are not the Owner or a Billing admin.
- An ownership transfer was requested earlier and expired after 7 days without being accepted.

## How do I confirm the situation?

1. Open **Admin console → Account → Members**. Note the Owner (user ID such as `usr_2B6N8R4V`) and check that the requester has the role Admin.
2. Open **Admin console → Account → Audit log** and filter on the Owner. Note the date of the Owner's last `login.succeeded`. An Owner who signed in this week is not unreachable.
3. Look for recent `ownership.transfer_requested` events. An open request from the Owner means the Owner is active; ask the Admin to accept it.
4. Check **Admin console → Account → Overview** for the account state and the dunning day. If the account reaches day 14 (`read_only`) or day 44 (downgrade to Free) within the next 5 business days, tell the team lead today.

## What do I do, step by step?

**Business day 1**

1. Open a ticket (ID such as `SUP-58213`) with priority P3, or P2 if the account is already `read_only`.
2. Confirm that the request was made by a signed-in Admin, through in-app chat or a ticket opened from the dashboard. If it arrived by plain email, ask them to send it again while signed in.
3. Email the Owner at their registered address: an Admin has asked for ownership to be moved, and the Owner can either object, or sign in and transfer ownership themselves. This is contact attempt 1.
4. Ask the Admin for **written confirmation from a company officer**. The letter must:
   - be on the company's letterhead and signed by an officer, such as a director, chief executive, chief financial officer or company secretary;
   - give the officer's name and job title;
   - name the account by its account ID (such as `acc_7F3K9Q2M`) or its exact account name;
   - name the Admin who is to become Owner, with their email address;
   - say that the current Owner is no longer able to act for the company;
   - be sent as a PDF from an email address on the company's own domain.

**Business day 3**

5. Email the Owner again. This is contact attempt 2. If the account has a billing contact address that belongs to the Owner, send it there as well.

**When the letter has arrived and both attempts are made**

6. Check the letter against the list in step 4. If the account has a verified domain, the sender's domain must match it.
7. If the Owner has replied and objects, stop. Tell the team lead. Support does not transfer ownership against a reachable Owner.
8. Select **Admin console → Account → Members → Change owner → Request approval**. Attach the letter, and enter the ticket ID and the dates of both contact attempts.
9. The support team lead reviews and approves. The lead must not be the agent who handled the ticket.
10. After approval, select **Change owner** and pick the Admin. The change takes effect at once. The 7-day acceptance step is skipped, because the Admin asked for the transfer in writing.
11. The previous Owner becomes an Admin. If that person has left the company, tell the new Owner to remove them in **Settings → Members**. Their content is then reassigned to the new Owner.
12. Confirm that the audit log shows `ownership.transferred` with a support actor.

Do not ask for or accept a copy or number of any personal identity document, from the Admin or the officer. The letter, the sending domain and the signed-in request are the evidence. If the customer sends such a document anyway, remove it from the ticket.

## What if the company is very small?

Sometimes the Admin asking is also the only officer of the company, so the letter is signed by the person who benefits from it. The letter is still required. In addition, the Admin must pass check B (DNS record) or check D (account facts) from `docs/runbooks/mfa-reset-for-locked-out-owner.md`. If the account has no verified domain and the email addresses are on a public mail service, the team lead decides and may refuse.

## What do I tell the customer?

- At the start: "Only the Owner can transfer an account. Because your Owner cannot be reached, we can do it for you, but we need written confirmation from an officer of your company. The process takes up to 5 business days."
- About the Owner: "We will write to the current Owner twice, so that they have the chance to respond."
- About billing in the meantime: "Until the transfer is complete we cannot change the plan or payment method for you. Invoices and payment emails continue to go to the Owner, the Billing admins and the billing contacts."
- Afterwards: "You are now the Owner of the account. The previous Owner is now an Admin. You can remove them in **Settings → Members**. Please also check **Settings → Billing → Payment method**."

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| Letter received and both contact attempts made | Support team lead, for approval | Same business day |
| The Owner replies and objects | Support team lead; the process stops | At once |
| Two Admins make competing requests | Support team lead | At once |
| The account has no Admin | Support team lead, then the Accounts team | Business day 1 |
| The account will become `read_only` or be downgraded before the transfer can finish | Support team lead and the billing manager | Business day 1 |
| The letter looks altered, or the domain does not match | Support team lead and the Identity team | At once |

If the customer replies "escalate", a team lead reviews the ticket within 1 business day. The requirement for the letter does not change.

## What happens afterwards?

1. Close the ticket with the dates of both contact attempts, the date the letter arrived, the approver's role and the time of the change. Keep the letter attached to the ticket.
2. Suggest that the new Owner appoints a second Admin and a Billing admin, so that the account does not depend on one person again.
3. If the request was refused, record the reason in a note on the account.

## Related links

- Decision: `docs/architecture/adr/0001-one-owner-per-account.md`
- UI: `docs/ui/settings-account.md` ("How do I transfer account ownership?"), `docs/ui/settings-members.md`
- Admin console rules: `docs/ui/internal/admin-console.md` ("What must support never do from the console?")
- Code: `src/acme_cloud/accounts/ownership.py`, `src/acme_cloud/accounts/members.py`, `src/acme_cloud/support/escalation.py`
- Release: `reports/releases/2026.8.md` (acceptance within 7 days for normal transfers)
- Other runbooks: `docs/runbooks/mfa-reset-for-locked-out-owner.md`, `docs/runbooks/account-stuck-in-past-due.md`
- No incident report is linked to this runbook.

Last reviewed: 2026-11-26
