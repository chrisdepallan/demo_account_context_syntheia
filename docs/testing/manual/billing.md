# Manual Test Suite: Billing

Covers **Settings → Billing**: trial conversion, plan and seat changes, proration, payment methods, dunning, invoices and billing contacts. Run in a sandbox with the payment processor in test mode. Payment methods are referred to as "a valid test card from the sandbox processor" or by token (for example `pm_9XK2M4QH7T`); never type or record a real card. Time is moved with **Sandbox tools → Advance clock** in the admin console. Unless a case says otherwise, the tester is the Owner and the billing period has **30 days**.

## TC-BILL-001: A trial account adds a payment method and becomes active

**Preconditions:** New account, `trialing` on Pro, day 5 of 14, 4 members.

**Steps:**
1. Go to **Settings → Billing → Payment method → Update**.
2. Add a valid test card from the sandbox processor.
3. Choose **Pro**, **monthly**, and confirm.

**Expected result:** A charge of **$80.00** (4 seats × $20) succeeds. The state becomes `active`, the trial banner disappears, and an invoice with an ID like `INV-2026-004812` appears under **Invoices**. The `invoice_ready` email is sent.

**Priority:** High

## TC-BILL-002: A trial ends without a payment method and moves to Free

**Preconditions:** New account, `trialing`, no payment method, 5 members.

**Steps:**
1. Advance the clock to **3 days** before the trial end and check the Owner's inbox.
2. Advance the clock past day **14**.
3. Open **Settings → Billing** and **Settings → Members**.

**Expected result:** Step 1: the Owner has the `trial_ending` email. After step 2 the plan is **Free**, the state is `active` and nothing is charged. Three people keep the member role and two are guests. No data is deleted.

**Priority:** High

## TC-BILL-003: An upgrade is charged at once, prorated

**Preconditions:** Starter monthly, **5** seats, **15** whole days left in the period.

**Steps:**
1. Go to **Settings → Billing** and select **Change plan**.
2. Choose **Pro** and confirm.

**Expected result:** The plan is Pro immediately. The charge is **$30.00**: ($20 − $8) × 5 seats × 15/30. Pro controls such as **Require MFA** appear at once. The audit log shows `plan.changed`.

**Priority:** High

## TC-BILL-004: A downgrade takes effect at the end of the billing period

**Preconditions:** Pro monthly, 6 members, 1 workspace, storage under 60 GB, 10 days left.

**Steps:**
1. Go to **Settings → Billing**, select **Change plan**, choose **Starter** and confirm.
2. Check the plan today.
3. Advance the clock past the period end.

**Expected result:** Step 2: the plan is still Pro, with a note that Starter starts on the renewal date. No refund or credit is given. Step 3: the plan is Starter and the renewal charge is **$48.00** (6 × $8).

**Priority:** High

## TC-BILL-005: A downgrade is blocked while usage exceeds the lower plan

**Preconditions:** Pro monthly with **14** members.

**Steps:**
1. Go to **Settings → Billing**, select **Change plan** and choose **Starter**.
2. Remove 4 members in **Settings → Members** and repeat step 1.

**Expected result:** Step 1 is refused with `ERR_LIMIT_EXCEEDED` and names the member limit of **10**. After step 2 the downgrade is accepted and scheduled for the period end.

**Priority:** High

## TC-BILL-006: The annual price is 10 times the monthly price

**Preconditions:** `trialing` account with a payment method ready, 3 members.

**Steps:**
1. Go to **Settings → Billing** and open the plan chooser.
2. Switch between **monthly** and **annual** for Starter, Pro and Business.

**Expected result:** Per seat: Starter **$8 / $80**, Pro **$20 / $200**, Business **$45 / $450**. Choosing Pro annual for 3 seats shows a total of **$600.00**. Enterprise shows "Contact sales" with no price.

**Priority:** Medium

## TC-BILL-007: Adding seats is charged immediately, prorated by day

**Preconditions:** Pro monthly, 12 seats, **20** whole days left.

**Steps:**
1. Go to **Settings → Billing** and select **Change seats**.
2. Add **3** seats and confirm.

**Expected result:** A charge of **$40.00** is taken at once (3 × $20 × 20/30). The seat count is 15. The audit log shows `seats.changed`. In a 31-day period with 10 days left, one added seat costs **$6.45** ($20 × 10/31, rounded to the nearest cent).

**Priority:** High

## TC-BILL-008: A card update is checked with a $0 authorization

**Preconditions:** `active` Pro account with a stored payment method.

**Steps:**
1. Go to **Settings → Billing → Payment method → Update**.
2. Enter a valid test card from the sandbox processor and save.

**Expected result:** The processor log shows a temporary **$0 authorization** and no charge. The page shows the new method by brand and last 4 digits only. The audit log shows `payment_method.updated` with a `pm_` token in the metadata and no card number anywhere.

**Priority:** High

## TC-BILL-009: A declined card shows ERR_PAYMENT_FAILED

**Preconditions:** `trialing` account, no payment method.

**Steps:**
1. Go to **Settings → Billing → Payment method → Update**.
2. Enter a declining test card from the sandbox processor, choose Pro monthly and confirm.

**Expected result:** The page shows `ERR_PAYMENT_FAILED` and asks for another method. The state stays `trialing`. No invoice is created.

**Priority:** Medium

## TC-BILL-010: A failed renewal moves the account to past_due on day 0

**Preconditions:** `active` Pro monthly account whose stored test method will decline. One Billing admin and one billing contact exist.

**Steps:**
1. Advance the clock to the renewal date.
2. Sign in as a Member and edit a project.

**Expected result:** The state is `past_due`. The Owner, the Billing admin and the billing contact each get `payment_failed`. The Member can still edit; nothing is restricted on day 0.

**Priority:** High

## TC-BILL-011: Retries run on days 1, 3, 7 and 14

**Preconditions:** Account from TC-BILL-010, method still declining.

**Steps:**
1. Advance the clock one day at a time to day 14.
2. After each day, read the processor log.

**Expected result:** Exactly **four** retries, on days **1, 3, 7 and 14**. No retry on any other day. A `payment_failed` email follows each failed retry.

**Priority:** High

## TC-BILL-012: The account becomes read-only on day 14

**Preconditions:** Account from TC-BILL-011 on day 13, state `past_due`.

**Steps:**
1. Confirm a Member can still edit on day 13.
2. Advance to day 14 and let the retry fail.
3. As a Member, edit a project.

**Expected result:** After step 2 the state is `read_only`; the Owner and Billing admin get `account_read_only`. Step 3: the Member can log in and read, but the edit fails with `ERR_ACCOUNT_READ_ONLY`.

**Priority:** High

## TC-BILL-013: Paying the balance restores full access within 5 minutes

**Preconditions:** Account in `read_only` from TC-BILL-012.

**Steps:**
1. As the Billing admin, go to **Settings → Billing → Payment method → Update** and add a valid test card from the sandbox processor.
2. Note the time, then try an edit as a Member every minute.

**Expected result:** The update triggers a retry at once and the charge succeeds. The state is `active` and editing works within **5 minutes**.

**Priority:** High

## TC-BILL-014: Seat removal is credited on the next invoice

**Preconditions:** `active` Pro monthly account, **12** seats, 12 members, **12** whole days left in a 30-day period.

**Steps:**
1. As an Admin, go to **Settings → Members**, choose a member and select **Remove**.
2. As the Owner, go to **Settings → Billing** and check the seat count and the upcoming invoice.
3. Advance the clock to the renewal date and open **Settings → Billing → Invoices**.

**Expected result:** Seats drop to **11**. No refund is paid out today. The upcoming invoice shows a credit of **$8.00** ($20 × 12/30). The next invoice is **$212.00**: 11 seats × $20 = $220.00, minus the $8.00 credit.

**Priority:** High

## TC-BILL-015: Day 44 downgrades the account to Free

**Preconditions:** Account in `read_only`, never paid, with 6 members.

**Steps:**
1. Advance the clock to day **43** and check the plan.
2. Advance to day **44**.
3. Open **Settings → Members**.

**Expected result:** Day 43: still the paid plan, `read_only`. Day 44: plan **Free**, state `active`; the Owner and Billing admins get `account_downgraded`. Three people keep the member role; the other three are guests.

**Priority:** High

## TC-BILL-016: A sixth billing contact is rejected

**Preconditions:** `active` paid account with no billing contacts.

**Steps:**
1. Go to **Settings → Billing → Billing contacts**.
2. Add five addresses, for example `ap1@example.com` to `ap5@example.com`.
3. Add a sixth address.

**Expected result:** Five contacts are saved. The sixth is refused with `ERR_LIMIT_EXCEEDED` (up to **5 extra addresses**). The contacts cannot log in.

**Priority:** Medium

## TC-BILL-017: An invoice downloads as a PDF

**Preconditions:** Account with at least one paid invoice. Signed in as a Billing admin.

**Steps:**
1. Go to **Settings → Billing → Invoices**.
2. Select **Download** on the newest invoice.

**Expected result:** A PDF downloads. Its ID has the form `INV-<year>-<6 digits>`. It shows the company name and VAT/GST ID from **Billing details**, the seats, the amount and the payment method by brand and last 4 digits only.

**Priority:** Medium

## TC-BILL-018: A cancelled plan stays active until the period ends

**Preconditions:** `active` Pro monthly account, 10 days left.

**Steps:**
1. Go to **Settings → Billing → Cancel subscription** and confirm.
2. Check Pro features today.
3. Advance the clock past the period end.

**Expected result:** Step 2: the plan is still Pro and nothing is refunded. Step 3: the plan is **Free** and no charge is made.

**Priority:** High

## TC-BILL-019: An Admin cannot open Settings → Billing

**Preconditions:** Signed in as an Admin.

**Steps:**
1. Open the Settings menu.
2. Open the address of **Settings → Billing → Invoices** directly.

**Expected result:** **Billing** is not in the menu. The direct address shows `ERR_PERMISSION_DENIED`. No invoice or payment data is displayed.

**Priority:** High

## TC-BILL-020: PayPal is not offered on Enterprise

**Preconditions:** One Business account and one Enterprise account, both outside India.

**Steps:**
1. On each account, go to **Settings → Billing → Payment method → Update**.
2. Read the list of methods.

**Expected result:** Business lists cards and **PayPal**. Enterprise lists cards and invoice with net-30 terms, and no PayPal.

**Priority:** Low

Last reviewed: 2026-11-26
