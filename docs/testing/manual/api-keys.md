# Manual Test Suite: API Keys

Covers **Settings → API keys** and the key behaviour seen through the REST API: creation, scopes, expiry, rotation, revocation and rate limits. Run in a sandbox with `acme_test_` keys against `https://sandbox.api.acme-cloud.example/v1`. Send keys in the header `Authorization: Bearer <api key>`. Never paste a full key into test results; record the key ID (for example `key_5T9W3E7Y`) and the last 4 characters only. Time is moved with **Sandbox tools → Advance clock** in the admin console.

## TC-KEY-001: A new key is shown once

**Preconditions:** Pro account with fewer than 25 keys. Signed in as an Admin.

**Steps:**
1. Go to **Settings → API keys → Create key**.
2. Enter a name, choose `projects:read` and an expiry of **90 days**, and create.
3. Copy the key, close the dialog and reopen the key's row.

**Expected result:** The dialog shows the full key once: prefix `acme_test_` in the sandbox, followed by **32** characters. Afterwards the row shows only the name, the key ID, the last **4** characters, the scopes and the expiry date. There is no way to display the full key again. The audit log shows `api_key.created`.

**Priority:** High

## TC-KEY-002: Sandbox and production keys have different prefixes

**Preconditions:** One key created in the sandbox and one in a production test account.

**Steps:**
1. Compare the prefixes.
2. Call `GET /projects` on the production URL with the sandbox key.

**Expected result:** The sandbox key starts with `acme_test_` and the production key with `acme_live_`. The cross-environment call returns HTTP 401 `ERR_UNAUTHENTICATED`.

**Priority:** Medium

## TC-KEY-003: A 26th active key is refused

**Preconditions:** Workspace with **24** active keys and 2 revoked keys.

**Steps:**
1. Create a key. Then create one more.
2. Revoke one key and create again.

**Expected result:** The 25th key is created. The 26th is refused with `ERR_LIMIT_EXCEEDED` (up to **25 active keys** per workspace). Revoked keys do not count, so after step 2 creation succeeds.

**Priority:** High

## TC-KEY-004: A key cannot act outside its scopes

**Preconditions:** A key with `projects:read` only.

**Steps:**
1. Call `GET /projects` with the key.
2. Call `POST /projects` with the key.
3. Call `GET /members` with the key.

**Expected result:** Step 1 returns HTTP 200. Steps 2 and 3 return HTTP 403 `ERR_PERMISSION_DENIED`, because the key lacks `projects:write` and `members:read`.

**Priority:** High

## TC-KEY-005: The billing:read scope is offered to the Owner only

**Preconditions:** Starter account. One Owner and one Admin.

**Steps:**
1. As the Admin, go to **Settings → API keys → Create key** and read the scope list.
2. As the Owner, do the same.

**Expected result:** The Admin sees six scopes: `projects:read`, `projects:write`, `files:read`, `files:write`, `members:read`, `members:write`. The Owner also sees `billing:read`.

**Priority:** Medium

## TC-KEY-006: Expiry options are 30, 90, 180 and 365 days, or never

**Preconditions:** Pro account with **Require key expiry** off. Signed in as an Admin.

**Steps:**
1. Go to **Settings → API keys → Create key** and open the expiry list.
2. Create a key with **30 days**.

**Expected result:** The list holds exactly **30, 90, 180, 365 days** and **Never**. The new key's expiry date is 30 days from today.

**Priority:** Medium

## TC-KEY-007: Require key expiry hides the Never option

**Preconditions:** Pro account. One existing key set to never expire. Signed in as an Admin.

**Steps:**
1. Turn on **Settings → Security → Require key expiry**.
2. Go to **Settings → API keys → Create key** and open the expiry list.
3. Send a create request with no expiry through a direct request.

**Expected result:** The audit log shows `policy.changed`. **Never** is not in the list. The direct request is refused with `ERR_VALIDATION`. The existing never-expiring key keeps working and is marked in the list as having no expiry.

**Priority:** High

## TC-KEY-008: The Owner is emailed 14 days before a key expires

**Preconditions:** A key created by an Admin with a **30-day** expiry.

**Steps:**
1. Advance the clock **15 days** and check the Owner's and the Admin's inboxes.
2. Advance **1 more day** and check again.

**Expected result:** Nothing after step 1. After step 2 (14 days before expiry) the **Owner** has one `key_expiring` email. The Admin who created the key has none.

**Priority:** Medium

## TC-KEY-009: An expired key is rejected

**Preconditions:** A key with a 30-day expiry and the scope `projects:read`.

**Steps:**
1. Advance the clock to one minute before expiry and call `GET /projects`.
2. Advance two minutes and call again.

**Expected result:** Step 1 returns HTTP 200. Step 2 returns HTTP 401 `ERR_UNAUTHENTICATED`. The row in **Settings → API keys** shows "Expired", and the key no longer counts towards the 25.

**Priority:** High

## TC-KEY-010: After Rotate, the old key works for 24 hours

**Preconditions:** A working key. Signed in as an Admin.

**Steps:**
1. Go to **Settings → API keys** and select **Rotate** next to the key. Copy the new key.
2. Call `GET /projects` with the old key and with the new key.
3. Advance the clock **23 hours 59 minutes** and call with the old key.
4. Advance **2 more minutes** and call with the old key.

**Expected result:** Both keys work in steps 2 and 3. In step 4 the old key returns `ERR_UNAUTHENTICATED`; the new key still works. The audit log shows `api_key.rotated`.

**Priority:** High

## TC-KEY-011: A revoked key stops working within 60 seconds

**Preconditions:** A working key. A script that calls `GET /projects` every 5 seconds and logs the status. Run this case in each regional sandbox: `us-east`, `eu-central` and `ap-south`.

**Steps:**
1. Start the script.
2. Go to **Settings → API keys** and select **Revoke** next to the key. Note the time.
3. Let the script run for 2 minutes.

**Expected result:** In every region the first HTTP 401 `ERR_UNAUTHENTICATED` comes no later than **60 seconds** after the revoke, and no call succeeds after that. The audit log shows `api_key.revoked`. (Regression for **INC-2026-006**, when revoked keys worked for up to 15 minutes in `ap-south`.)

**Priority:** High

## TC-KEY-012: A revoked key cannot be restored

**Preconditions:** The key revoked in TC-KEY-011.

**Steps:**
1. Open the key's row in **Settings → API keys**.

**Expected result:** The row shows "Revoked" with the date and the person who revoked it. There is no **Rotate** or restore action.

**Priority:** Low

## TC-KEY-013: Settings → API keys is not shown on Free

**Preconditions:** Free account. Signed in as the Owner.

**Steps:**
1. Open the Settings menu.
2. Open the address of **Settings → API keys** directly.

**Expected result:** **API keys** is not in the menu. The direct address shows `ERR_PLAN_REQUIRED` with a link to **Settings → Billing**.

**Priority:** High

## TC-KEY-014: A Member cannot manage keys

**Preconditions:** Pro account. Signed in as a Member.

**Steps:**
1. Open the Settings menu.
2. Open the address of **Settings → API keys** directly.

**Expected result:** **API keys** is not in the menu and the direct address shows `ERR_PERMISSION_DENIED`. No key names or IDs are displayed.

**Priority:** High

## TC-KEY-015: A Starter key is limited to 60 requests per minute

**Preconditions:** Starter account with one key.

**Steps:**
1. Send **60** `GET /projects` calls within one minute.
2. Send a 61st call in the same minute.
3. Wait the number of seconds in `Retry-After` and call again.

**Expected result:** The first 60 calls return HTTP 200. The 61st returns HTTP 429 `ERR_RATE_LIMITED` with a `Retry-After` header in seconds. Step 3 returns HTTP 200.

**Priority:** High

## TC-KEY-016: The rate limit follows the plan after an upgrade

**Preconditions:** The Starter account from TC-KEY-015.

**Steps:**
1. As the Owner, upgrade to **Pro** in **Settings → Billing**.
2. Send **300** calls within one minute with the same key, then one more.

**Expected result:** All 300 calls return HTTP 200 and the 301st returns HTTP 429. The limit is per key: a second key has its own 300.

**Priority:** Medium

## TC-KEY-017: Key events reach a webhook endpoint

**Preconditions:** Pro account with one webhook endpoint subscribed to `api_key.created` and `api_key.revoked`.

**Steps:**
1. Create a key, then revoke it.
2. Read the requests received by the endpoint.

**Expected result:** Two deliveries arrive, `api_key.created` and `api_key.revoked`. Each has an `Acme-Signature` header that verifies with HMAC-SHA256. The payload holds the key ID and the last 4 characters, never the key itself.

**Priority:** Medium

## TC-KEY-018: Changes made with a key are listed under that key in the audit log

**Preconditions:** Pro account. A key with `members:write`. Signed in as an Admin.

**Steps:**
1. With the key, invite `new.member@example.com` through the API.
2. Go to **Settings → Audit log** and set the **Actor** filter to the key.
3. Revoke the key and repeat step 2.

**Expected result:** The filter lists a `member.invited` event whose actor is the key ID (for example `key_5T9W3E7Y`), not a user. After the revoke the event is still listed; revoking a key does not remove its history.

**Priority:** Medium

Last reviewed: 2026-11-26
