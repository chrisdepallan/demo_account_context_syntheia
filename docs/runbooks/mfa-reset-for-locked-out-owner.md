# Runbook: MFA Reset for a Locked-Out Owner

**For:** support agents. A support team lead approves every reset.

This runbook covers the case where the account Owner, or the only Admin, has lost both their MFA device and their backup codes and cannot sign in. Nobody inside the account can fix it, so support must. The promise to the customer is a reset within **2 business days**. This runbook did not come out of an incident. It exists because an MFA reset is the easiest way for an attacker to take over an account, and the admin console rule "never reset MFA based on email alone" needs a concrete procedure behind it.

## When does this runbook apply?

| Who is locked out | Who resets MFA |
|-------------------|----------------|
| A Member, Guest or Billing admin | Any Owner or Admin, in **Settings → Members → choose the member → Reset MFA** |
| An Admin, when another Admin or the Owner can sign in | That other Admin or the Owner, in the same place |
| The only Admin, when the Owner cannot be reached | Support, with this runbook |
| The Owner | Support, with this runbook |

Send every case in the first two rows back to the customer's own Admins. It is faster for them and safer for everyone.

## What are the symptoms?

- The user's password is accepted, and they then stop at the MFA step.
- They no longer have their authenticator app or security key, and have none of their 10 backup codes.
- The ticket often arrives from a personal email address, because the user cannot reach their work tools. A request from an address that is not on the account proves nothing.

## How do I confirm it is an MFA problem and not something else?

1. Open **Admin console → Account → Members** and find the user (ID such as `usr_2B6N8R4V`). Confirm their role is Owner, or that they are the only Admin.
2. Open **Admin console → Account → Audit log** and filter on the user. Look at the last `login.succeeded`, `login.failed` and `login.locked` events.
3. If you see `login.locked`, the user is locked out by failed passwords, not by MFA. Five failed attempts in 15 minutes lock login for 15 minutes; ten in 1 hour lock it for 1 hour. A password reset from **Forgot password** unlocks it at once, and no support action is needed.
4. Check the SSO status in **Admin console → Account → Security → SSO**. If SSO is enforced, the Owner still signs in with password plus MFA (break-glass), so the MFA reset is still needed for the Owner.
5. Ask whether the user has one of their backup codes saved in a password manager or printed. One code is enough to sign in and enrol a new device from **Profile → Security**.

## How do I verify the person?

Email alone is never enough. The person must pass check A and one of checks B, C or D.

- **A. Reply from the registered address.** Send a message to the email address on the user's record and ask for a reply from that address. A message that only claims to come from that address does not count.
- **B. DNS record.** If the account has a verified domain, give them a new token and ask them to add the TXT record `acme-verify=<token>` to that domain. This is the same mechanism as SSO domain verification. Check the record yourself.
- **C. A second authenticated person.** A Billing admin or Admin of the same account confirms the request from inside the dashboard, through in-app chat or a ticket opened while signed in.
- **D. Account facts.** The person gives all three of these correctly: the ID of the most recent invoice (format `INV-2026-004812`), its total amount, and the month the account was created.

Do not ask for, and do not accept, any of the following: a password, an MFA code, a backup code, a full card number, or a copy or number of any identity document. If the customer sends one, remove it from the ticket and continue with the checks above.

If the person cannot pass check A because they have also lost access to their mailbox, this runbook stops. The path is then `docs/runbooks/unreachable-owner-transfer.md`, started by an Admin.

## What do I do, step by step?

1. Open a ticket if there is none (ID such as `SUP-58213`). Set the priority to P2 when the whole account is blocked from administration, otherwise P3.
2. Run the confirmation steps above. Rule out password lockout and saved backup codes.
3. Run verification: check A plus one of B, C or D. Record in the ticket which checks passed and when. Do not record the answers themselves.
4. Select **Admin console → Account → Members → choose the member → Reset MFA → Request approval**. Enter the ticket ID and the checks that passed.
5. The system emails the user's registered address, and every Admin and Billing admin of the account, saying that an MFA reset has been requested and will happen in 24 hours unless someone objects.
6. Wait **24 hours**. If anyone on the account objects, stop and tell the support team lead.
7. The support team lead reviews the ticket and approves. The lead must not be the agent who ran the verification.
8. After approval and the 24-hour wait, select **Reset MFA** on the same screen. This removes all of the user's MFA methods and backup codes and signs out all of their sessions.
9. Tell the user to sign in with their password. They are asked to set up MFA again and receive 10 new backup codes.
10. Confirm that the audit log shows `mfa.reset` with a support actor, followed by `mfa.enrolled` for the user.

The whole process fits inside 2 business days only if verification starts on the day the ticket arrives. Do not let the ticket wait for the customer without a reminder.

## What do I tell the customer?

- At the start: "For your security we cannot reset MFA on the basis of an email. We need to confirm that you control the account. This takes up to 2 business days."
- When asking for verification: explain checks A to D and let them choose between B, C and D.
- About the wait: "Everyone who administers your account has been told about the request. The reset will happen 24 hours after that message."
- Afterwards: "Your MFA has been reset. Please sign in, set up a new authenticator app or security key, and save the new backup codes somewhere other than the device itself."
- Advice: on Business and Enterprise, SMS is not offered to Owners and Admins. Suggest that they enrol two methods, for example an authenticator app and a security key, and appoint a second Admin.

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| Verification complete, approval needed | Support team lead | Same business day |
| Someone on the account objects during the 24-hour wait | Support team lead; the reset stops | At once |
| The request looks like an attack (pressure, changing story, new email address) | Support team lead and the Identity team | At once |
| The person cannot pass check A | Switch to `docs/runbooks/unreachable-owner-transfer.md` | Same business day |
| Enterprise account | Tell the named Customer Success Manager | When the ticket is opened |

A customer who is unhappy with the delay can reply "escalate". A team lead reviews the ticket within 1 business day, but the verification rules do not change.

## What happens afterwards?

1. Close the ticket with the list of checks passed, the approver's role and the time of the reset.
2. If the request was refused, record why, and add a note on the account so the next agent sees it.
3. If the account has only one Admin-level person, suggest that they add another.

## Related links

- UI: `docs/ui/settings-members.md` ("How do I reset a member's MFA?"), `docs/ui/login-and-profile.md` (MFA setup, backup codes, lockout)
- Admin console rules: `docs/ui/internal/admin-console.md` ("What must support never do from the console?")
- Code: `src/acme_cloud/auth/mfa.py`, `src/acme_cloud/auth/lockout.py`, `src/acme_cloud/support/conduct.py`
- Decision: `docs/architecture/adr/0001-one-owner-per-account.md`
- Other runbooks: `docs/runbooks/unreachable-owner-transfer.md`, `docs/runbooks/sso-login-failures.md`
- No incident report is linked to this runbook.

Last reviewed: 2026-11-26
