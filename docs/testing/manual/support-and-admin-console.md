# Manual Test Suite: Support and Admin Console

Covers the customer support entry points in the dashboard and the internal admin console at `https://admin.acme-cloud.example` (staff only): tickets, first-response targets, escalation, refunds and the identity processes. Run in a sandbox with staff test logins for a support agent, a support team lead and the billing manager. Tickets and customers are test data on `@example.com`. Business hours are Monday–Friday, 08:00–18:00 US Central Time; one business day is 10 business hours.

## TC-SUP-001: Live chat opens on Pro during business hours

**Preconditions:** Pro account. Sandbox clock set to Wednesday 10:00 US Central Time. Signed in as a Member.

**Steps:**
1. Select the **question-mark icon at the bottom right** of the dashboard.
2. Send a test message.

**Expected result:** The chat panel opens and the message is delivered. A ticket with an ID like `SUP-58213` is created and shown in the panel.

**Priority:** High

## TC-SUP-002: Live chat is not offered on Starter

**Preconditions:** Starter account. Clock inside business hours.

**Steps:**
1. Select the question-mark icon.

**Expected result:** The panel offers the help center `https://help.acme-cloud.example` and email `support@acme-cloud.example` only. There is no chat box. Live chat needs **Pro and above**.

**Priority:** Medium

## TC-SUP-003: Chat outside business hours offers email instead

**Preconditions:** Pro account. Clock set to Saturday 12:00 US Central Time.

**Steps:**
1. Select the question-mark icon.

**Expected result:** The panel says chat is open Monday–Friday, 08:00–18:00 US Central Time, and offers email and the help center. No chat session starts.

**Priority:** Low

## TC-SUP-004: A P1 ticket on Pro is due in 4 business hours

**Preconditions:** Pro account. Signed in to the admin console as a support agent.

**Steps:**
1. Create a ticket for the account with priority **P1** at Friday **17:00** US Central Time.
2. Read "First response due" on the ticket.
3. Create a second P1 ticket at Tuesday **09:00**.

**Expected result:** The first ticket is due **Monday 11:00** (1 hour on Friday plus 3 hours on Monday). The second is due **Tuesday 13:00**.

**Priority:** High

## TC-SUP-005: An Enterprise P1 ticket is due in 30 minutes at any hour

**Preconditions:** Enterprise account. Signed in as a support agent.

**Steps:**
1. Create a **P1** ticket at Saturday **23:10** US Central Time.
2. Read "First response due".

**Expected result:** Due Saturday **23:40**. Enterprise P1 is **30 minutes, 24/7**, and does not wait for business hours.

**Priority:** High

## TC-SUP-006: Starter and Free targets are counted in business days

**Preconditions:** One Starter and one Free account. Signed in as a support agent.

**Steps:**
1. Create a **P2** ticket on each account at Monday **08:00** US Central Time.
2. Read "First response due" on both.

**Expected result:** Starter: due **Tuesday 18:00** (2 business days, which is 20 business hours). Free: due **Wednesday 18:00** (3 business days).

**Priority:** Medium

## TC-SUP-007: Replying "escalate" sends the ticket to a team lead

**Preconditions:** An open P3 ticket. Clock at Thursday 15:00 US Central Time.

**Steps:**
1. As the customer, reply to the ticket with the single word "escalate".
2. As a support team lead, open the escalation queue in the admin console.

**Expected result:** The ticket is flagged as escalated and appears in the team lead's queue with a review due time of **Friday 15:00** (1 business day).

**Priority:** Medium

## TC-SUP-008: A support agent can approve a refund of $500.00

**Preconditions:** A paid invoice of **$900.00** with no earlier refunds. Signed in to the admin console as a support agent.

**Steps:**
1. Open the account and select **Invoices → Refund** on the invoice.
2. Choose partial, enter **$500.00** and the ticket number in the reason field, and submit.

**Expected result:** The refund is created with an ID like `rf_8M2K4Q9X7T` and the status `pending`, with no further approval needed.

**Priority:** High

## TC-SUP-009: A refund of $500.01 needs a team lead

**Preconditions:** Another paid invoice of **$900.00**. Signed in as a support agent.

**Steps:**
1. Select **Invoices → Refund**, enter **$500.01** and submit.
2. Sign in as a support team lead and approve the request.

**Expected result:** Step 1 does not create a refund; it creates an approval request for a team lead. After step 2 the refund is `pending`. The record shows both the agent and the approver.

**Priority:** High

## TC-SUP-010: A refund over $5,000 needs the billing manager

**Preconditions:** Two accounts, each with a paid annual invoice of **$9,000.00** (Business, 20 seats) and no earlier refunds.

**Steps:**
1. On the first invoice, as a support agent, request a refund of **$5,000.00**. As a team lead, approve it.
2. On the second invoice, as a support agent, request **$5,000.01**. As a team lead, try to approve it.
3. As the billing manager, approve it.

**Expected result:** The team lead can approve **$5,000.00**. For **$5,000.01** the team lead has no approve button and the request waits for the billing manager. After step 3 the refund is `pending`.

**Priority:** High

## TC-SUP-011: A refund cannot exceed the paid amount minus earlier refunds

**Preconditions:** A paid invoice of **$240.00** with one earlier refund of **$100.00**.

**Steps:**
1. Select **Invoices → Refund** and enter **$140.01**.
2. Enter **$140.00**.

**Expected result:** Step 1 is refused with `ERR_VALIDATION`; the form shows the refundable amount of **$140.00**. Step 2 is accepted.

**Priority:** High

## TC-SUP-012: An annual plan closed within 30 days is refunded in full

**Preconditions:** Two accounts on Pro annual, 5 seats, paid **$1,000.00**. Account A bought 30 days ago; account B bought 31 days ago.

**Steps:**
1. The Owner of each account closes it in **Settings → Account → Close account**.
2. Open both accounts in the admin console.

**Expected result:** Account A has a refund of **$1,000.00**. Account B has no refund. Neither needed a goodwill approval.

**Priority:** High

## TC-SUP-013: A second goodwill refund within 12 months is blocked

**Preconditions:** An account with one goodwill refund 11 months ago. Signed in as a support team lead.

**Steps:**
1. Select **Invoices → Refund**, tick **Goodwill** and submit **$20.00**.
2. Advance the clock 2 months and repeat.

**Expected result:** Step 1 is refused: one goodwill refund per account per **12 months**. Step 2 is accepted. A support agent without team-lead approval cannot submit a goodwill refund at any amount.

**Priority:** Medium

## TC-SUP-014: A refund moves from pending to succeeded

**Preconditions:** A `pending` refund from TC-SUP-008. A webhook endpoint subscribed to `refund.succeeded`.

**Steps:**
1. Let the sandbox processor confirm the refund.
2. Open the refund in the admin console and the customer's audit log.

**Expected result:** The status is `succeeded`. The audit log shows `refund.issued` with **Acme Cloud support** as actor. The webhook `refund.succeeded` is delivered. The reply template tells the customer the amount and the **5–10 business day** timeline.

**Priority:** Medium

## TC-SUP-015: Support resets MFA for a locked-out Owner

**Preconditions:** An Owner who has lost the MFA device and backup codes. A ticket is open.

**Steps:**
1. As a support agent, open the account and select **Members → Reset MFA** for the Owner.
2. Try to submit without completing the identity check.
3. Complete the identity check and submit.

**Expected result:** Step 2 is refused; an email request alone is not enough. After step 3 the Owner is asked to set up MFA at the next login, and the audit log shows `mfa.reset` with **Acme Cloud support** as actor. The ticket shows a target of **2 business days**.

**Priority:** High

## TC-SUP-016: The unreachable-Owner process needs a company officer's confirmation

**Preconditions:** An account whose Owner has left. An Admin has opened a ticket.

**Steps:**
1. As a support agent, open the account and start **Change Owner**.
2. Try to submit without an attached written confirmation.
3. Attach the confirmation, choose the Admin and submit for team-lead approval.

**Expected result:** Step 2 is refused. After step 3 and approval, the Admin is the Owner and the audit log shows `ownership.transferred`. The ticket shows a target of **5 business days**. No 7-day acceptance step applies to this process.

**Priority:** Medium

## TC-SUP-017: An invoice older than 12 months cannot be reissued

**Preconditions:** An account with one invoice 11 months old and one 13 months old.

**Steps:**
1. In the admin console, select **Invoices → Reissue** on the 11-month-old invoice.
2. Do the same on the 13-month-old invoice.

**Expected result:** Step 1 creates a reissued PDF with the current billing details. Step 2 offers no reissue; the original PDF is still downloadable (invoices are kept **7 years**).

**Priority:** Low

## TC-SUP-018: A customer login cannot open the admin console

**Preconditions:** A customer Owner account. Not signed in as staff.

**Steps:**
1. Open `https://admin.acme-cloud.example` and sign in with the customer Owner's login.

**Expected result:** Access is refused with `ERR_PERMISSION_DENIED`. No account data is shown. Only staff logins work.

**Priority:** High

## TC-SUP-019: The console shows no secrets or card numbers

**Preconditions:** Signed in as a support agent. An account with a stored payment method, API keys and MFA.

**Steps:**
1. Open the account's payment, API key and member views.

**Expected result:** The payment method appears as a token such as `pm_9XK2M4QH7T` with brand and last 4 digits. API keys show the key ID and last 4 characters. There is no field that shows or accepts a password, a full card number or an MFA code.

**Priority:** High

Last reviewed: 2026-11-26
