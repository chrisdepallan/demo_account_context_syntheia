# Manual Test Suite: Account and Members

Covers **Settings → Members** and **Settings → Account**: invitations, roles, guests, ownership transfer, closing and restoring an account. Run in a sandbox. All users have `@example.com` addresses. Where a case needs time to pass, a support agent uses **Sandbox tools → Advance clock** in the admin console. Rules and values come from `docs/reference/constants-and-glossary.md`.

## TC-ACCT-001: Owner invites a batch of 50 members

**Preconditions:** Business account, `active`, 10 members. Signed in as the Owner.

**Steps:**
1. Go to **Settings → Members → Invite**.
2. Paste **50** email addresses.
3. Choose the role **Member** and select **Send**.

**Expected result:** All 50 invitations are listed as pending. Each invitee gets the `invitation` email. The audit log shows 50 `member.invited` events.

**Priority:** High

## TC-ACCT-002: A batch of 51 invitations is rejected

**Preconditions:** As TC-ACCT-001.

**Steps:**
1. Go to **Settings → Members → Invite**.
2. Paste **51** email addresses and select **Send**.

**Expected result:** Nothing is sent. The form shows that a batch holds up to **50** addresses (`ERR_VALIDATION`). No `member.invited` event is written.

**Priority:** Medium

## TC-ACCT-003: An invitation expires after 7 days and can be resent

**Preconditions:** One pending invitation sent at a known time.

**Steps:**
1. Advance the sandbox clock by **6 days 23 hours** and open the invitation link.
2. Do not accept. Advance the clock by **2 more hours** and open the link again.
3. As an Admin, go to **Settings → Members**, find the invitation and select **Resend**.

**Expected result:** In step 1 the accept page opens. In step 2 the link shows "Invitation expired". After step 3 a new `invitation` email arrives and the new link is valid for **7 days**.

**Priority:** High

## TC-ACCT-004: Invite is blocked at the plan member limit

**Preconditions:** Starter account with **10** members (the Starter limit). Signed in as an Admin.

**Steps:**
1. Go to **Settings → Members → Invite**.
2. Enter one address, choose **Member** and select **Send**.

**Expected result:** The invitation is refused with `ERR_LIMIT_EXCEEDED` and a link to **Settings → Billing**. Inviting the same address as a **Guest** succeeds, because guests do not use seats.

**Priority:** High

## TC-ACCT-005: A Member cannot open Settings → Members

**Preconditions:** Signed in as a user with the Member role.

**Steps:**
1. Open the Settings menu.
2. Open the address of the **Settings → Members** page directly.

**Expected result:** The menu shows no **Members** entry. The direct address shows `ERR_PERMISSION_DENIED`. No member data is displayed.

**Priority:** High

## TC-ACCT-006: Removing a member ends access immediately

**Preconditions:** Member A is signed in in a second browser and owns at least one project. Signed in as Admin B.

**Steps:**
1. Go to **Settings → Members**, choose Member A and select **Remove**. Confirm.
2. In Member A's browser, open any project.

**Expected result:** Member A is signed out on the next action and cannot sign in to the account again. Member A's projects stay in the workspace and now belong to **Admin B**. The audit log shows `member.removed` and `seats.changed`.

**Priority:** High

## TC-ACCT-007: Changing a role changes the visible Settings pages

**Preconditions:** Member A has the Member role. Signed in as the Owner.

**Steps:**
1. Go to **Settings → Members**, choose Member A and change the role to **Billing admin**.
2. Sign in as Member A and open Settings.

**Expected result:** Member A sees **Settings → Billing** only. Member A can no longer create or edit projects. The audit log shows `member.role_changed` with the old role `member` and the new role `billing_admin`.

**Priority:** Medium

## TC-ACCT-008: Guest allowance is 5 per paid seat

**Preconditions:** Starter account with **2** seats and **10** guests. Signed in as an Admin.

**Steps:**
1. Go to **Settings → Members → Invite** and invite one more person as **Guest**.
2. Add one seat in **Settings → Billing** (as the Owner) and repeat step 1.

**Expected result:** Step 1 fails with `ERR_LIMIT_EXCEEDED` (2 seats × 5 = 10 guests). After the third seat the allowance is **15** and the invitation is sent.

**Priority:** Medium

## TC-ACCT-009: A Free account allows 5 guests in total

**Preconditions:** Free account with 3 members and **5** guests.

**Steps:**
1. As the Owner, invite a sixth guest from **Settings → Members → Invite**.

**Expected result:** The invitation is refused with `ERR_LIMIT_EXCEEDED`. The limit on Free is **5 guests in total**, whatever the number of members.

**Priority:** Low

## TC-ACCT-010: Owner requests an ownership transfer to an Admin

**Preconditions:** Account with an Owner and Admin A. Signed in as the Owner.

**Steps:**
1. Go to **Settings → Account → Transfer ownership**.
2. Pick Admin A and confirm.

**Expected result:** The page shows a pending request with the expiry date, **7 days** ahead. Admin A gets the `ownership_transfer` email. The Owner is still the Owner. The audit log shows `ownership.transfer_requested`.

**Priority:** High

## TC-ACCT-011: Only Admins are offered as transfer targets

**Preconditions:** Account with an Owner, one Admin, one Billing admin, one Member and one Guest.

**Steps:**
1. As the Owner, go to **Settings → Account → Transfer ownership**.
2. Open the list of people.

**Expected result:** The list holds the **Admin** only. The Billing admin, Member and Guest are not offered.

**Priority:** Medium

## TC-ACCT-012: Accepted transfer makes the previous Owner an Admin

**Preconditions:** A pending request from TC-ACCT-010, **6 days** old.

**Steps:**
1. Sign in as Admin A and open the link in the `ownership_transfer` email.
2. Select **Accept**.
3. Open **Settings → Members**.

**Expected result:** Admin A is now the **Owner**. The previous Owner is an **Admin**. The account has exactly one Owner. The audit log shows `ownership.transferred`. The previous Owner no longer sees **Settings → Account** actions or **Settings → Billing**.

**Priority:** High

## TC-ACCT-013: An unanswered transfer request expires after 7 days

**Preconditions:** A pending request created at a known time. Admin A has not answered.

**Steps:**
1. Advance the sandbox clock to **7 days and 1 minute** after the request.
2. As Admin A, open the accept link.
3. As the Owner, open **Settings → Account**.

**Expected result:** The link shows that the request has expired. The Owner has not changed. **Transfer ownership** is available again and no `ownership.transferred` event exists.

**Priority:** High

## TC-ACCT-014: An Admin cannot see Transfer ownership or Close account

**Preconditions:** Signed in as an Admin.

**Steps:**
1. Open **Settings → Account**.

**Expected result:** Neither **Transfer ownership** nor **Close account** is shown. A direct request for either action returns `ERR_PERMISSION_DENIED`.

**Priority:** High

## TC-ACCT-015: Owner closes the account by typing its name

**Preconditions:** `active` Pro account on a monthly plan with two members signed in. Signed in as the Owner.

**Steps:**
1. Go to **Settings → Account → Close account**.
2. Type a wrong account name and try to confirm.
3. Type the exact account name and confirm.

**Expected result:** Step 2 keeps the confirm button disabled. After step 3 the subscription is cancelled, the state is `closed` and all members are signed out. The Owner gets the `account_closed` email with the **30-day** restore link. The audit log shows `account.closed`. No refund is issued for a monthly plan.

**Priority:** High

## TC-ACCT-016: Owner restores a closed account on day 30

**Preconditions:** Account closed in TC-ACCT-015. Its state before closure was `active`.

**Steps:**
1. Advance the sandbox clock to day **30** after closure.
2. As the Owner, open the restore link from the `account_closed` email and confirm.

**Expected result:** The account returns to its previous state, `active`. Members can sign in again and all data is present. The audit log shows `account.restored`.

**Priority:** High

## TC-ACCT-017: A closed account is deleted on day 31

**Preconditions:** A second account, closed and not restored.

**Steps:**
1. Advance the sandbox clock to day **31** after closure.
2. Open the restore link.
3. As a support agent, search for the account ID in the admin console.

**Expected result:** The restore link no longer works. The admin console shows the state `deleted` and offers no restore action. Deletion cannot be undone by anyone.

**Priority:** High

## TC-ACCT-018: A Billing admin sees Settings → Billing only

**Preconditions:** Signed in as a user with the Billing admin role.

**Steps:**
1. Open the Settings menu.
2. Try to create a project in a workspace.

**Expected result:** Settings lists **Billing** only; **Members**, **Security**, **Workspace**, **API keys**, **Audit log** and **Account** are absent. Creating a project is refused with `ERR_PERMISSION_DENIED`, because a Billing admin has no `projects.edit` permission.

**Priority:** Medium

Last reviewed: 2026-11-26
