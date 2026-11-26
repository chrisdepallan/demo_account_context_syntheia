# Manual Test Suite: Workspace and Export

Covers workspace creation and regions, **Settings → Workspace → Export**, and the storage, upload and version-history limits shown on **Settings → Usage**. Run in a sandbox. Test files are generated filler files; do not upload real documents. Time is moved with **Sandbox tools → Advance clock** in the admin console. The storage meter is recalculated every **15 minutes**, so wait for a refresh before reading it.

## TC-WS-001: A new workspace defaults to us-east

**Preconditions:** Pro account with 1 workspace. Signed in as an Admin.

**Steps:**
1. Select **Workspaces → New workspace**.
2. Enter a name, leave the region as offered and create.

**Expected result:** The region field is preset to `us-east` (Virginia). The workspace is created with an ID like `ws_4H8P2L` and appears on **Settings → Usage** with its region.

**Priority:** High

## TC-WS-002: eu-central is offered on Business but not on Pro

**Preconditions:** One Pro account and one Business account.

**Steps:**
1. On each account, select **Workspaces → New workspace** and open the region list.
2. On Business, create a workspace in `eu-central`.

**Expected result:** Pro lists `us-east` only. Business lists `us-east` and `eu-central` (Frankfurt) and not `ap-south`. The Business workspace is created in `eu-central`.

**Priority:** High

## TC-WS-003: ap-south is offered on Enterprise only

**Preconditions:** One Business account and one Enterprise account.

**Steps:**
1. On each account, select **Workspaces → New workspace** and open the region list.
2. On Business, send a create request for `ap-south` directly.

**Expected result:** Enterprise lists `us-east`, `eu-central` and `ap-south` (Mumbai). Business does not list `ap-south`, and the direct request returns `ERR_PLAN_REQUIRED`.

**Priority:** Medium

## TC-WS-004: The region of a workspace cannot be changed

**Preconditions:** Business account with a workspace in `us-east`. Signed in as the Owner.

**Steps:**
1. Open **Settings → Workspace**.
2. Look for a way to edit the region.
3. Send a direct request to set the region to `eu-central`.

**Expected result:** The region is shown as read-only text with the note that it is fixed at creation. The direct request is refused with `ERR_VALIDATION`. The workspace stays in `us-east`.

**Priority:** High

## TC-WS-005: A fourth workspace is refused on Pro

**Preconditions:** Pro account with **3** workspaces.

**Steps:**
1. Select **Workspaces → New workspace**, enter a name and create.

**Expected result:** Creation is refused with `ERR_LIMIT_EXCEEDED` (Pro allows **3**). The message links to **Settings → Billing**. The same check refuses a second workspace on Free and Starter (limit **1**).

**Priority:** High

## TC-WS-006: An export moves from queued to running to ready

**Preconditions:** Workspace with about 1 GB of files. Signed in as Admin A. No export running.

**Steps:**
1. Go to **Settings → Workspace → Export** and start an export.
2. Refresh the page until the status stops changing.
3. Check Admin A's inbox and the Owner's inbox.

**Expected result:** The export gets an ID like `exp_6J4D8S2A` and shows `queued`, then `running`, then `ready` with a download link. Admin A, the requester, gets the `export_ready` email; the Owner does not. The audit log shows `export.started` with Admin A as actor.

**Priority:** High

## TC-WS-007: A second export in the same workspace is refused

**Preconditions:** An export in `queued` or `running` in workspace 1. The account has a second workspace.

**Steps:**
1. In workspace 1, start another export from **Settings → Workspace → Export**.
2. In workspace 2, start an export.

**Expected result:** Step 1 is refused with `ERR_CONFLICT`, because only one export per workspace can run. Step 2 is accepted; the limit is per workspace, not per account.

**Priority:** High

## TC-WS-008: The download link expires after 7 days

**Preconditions:** An export in `ready`.

**Steps:**
1. Advance the clock **6 days 23 hours** and open the download link.
2. Advance **2 more hours** and open the link again.
3. Open **Settings → Workspace → Export**.

**Expected result:** Step 1 downloads the ZIP. Step 2 is refused. Step 3 shows the export as `expired` with no download button. A new export can be started.

**Priority:** High

## TC-WS-009: An export running longer than 24 hours is marked failed

**Preconditions:** An export held in `running` by pausing the export worker in the sandbox.

**Steps:**
1. Advance the clock **23 hours 59 minutes** and read the status.
2. Advance **2 more minutes** and read the status.
3. Start a new export in the same workspace.

**Expected result:** Step 1: still `running`. Step 2: `failed`. Step 3 is accepted, because the failed export no longer blocks the workspace. (Regression for **INC-2026-004**, when exports stayed in `running` with no timeout.)

**Priority:** High

## TC-WS-010: The export ZIP holds JSON and the original files

**Preconditions:** An export in `ready` for a workspace with known projects, comments and files.

**Steps:**
1. Download the ZIP from **Settings → Workspace → Export**.
2. Unpack it and compare with the workspace.

**Expected result:** The ZIP holds JSON files for projects, comments and members, and every original file with its name and content unchanged. No passwords, API keys or payment data are in the export. The audit log shows `export.downloaded`.

**Priority:** Medium

## TC-WS-011: A Member cannot start an export

**Preconditions:** Signed in as a Member.

**Steps:**
1. Open the Settings menu.
2. Send a direct request to start an export.

**Expected result:** **Workspace** is not in the Settings menu. The direct request returns `ERR_PERMISSION_DENIED`, because Members do not have `workspace.export`. No export is created.

**Priority:** High

## TC-WS-012: Starter accepts a 250 MB file and refuses a larger one

**Preconditions:** Starter account with free storage. Signed in as a Member.

**Steps:**
1. Upload a file of exactly **250 MB** (256,000 KB).
2. Upload a file of **251 MB**.

**Expected result:** The 250 MB file uploads. The 251 MB file is refused before the upload starts, with `ERR_LIMIT_EXCEEDED`.

**Priority:** High

## TC-WS-013: Pro accepts a 5 GB file

**Preconditions:** Pro account with at least 10 GB free.

**Steps:**
1. Upload a file of exactly **5 GB** (5,120 MB).
2. Upload a file of **5.1 GB**.

**Expected result:** The 5 GB file uploads. The larger file is refused with `ERR_LIMIT_EXCEEDED`.

**Priority:** Medium

## TC-WS-014: A storage warning is sent at 90%

**Preconditions:** Starter account with **2** seats (**20 GB** total) and 17.5 GB used. One Admin exists.

**Steps:**
1. Upload files until usage is just over **18 GB**.
2. Wait for the meter to refresh and open **Settings → Usage**.
3. Upload another 100 MB.

**Expected result:** The meter shows 90% or more in amber. The Owner and the Admin each get one `storage_warning` email. Uploads still work, and step 3 does not send a second warning.

**Priority:** Medium

## TC-WS-015: Uploads are blocked at 100% and files stay editable

**Preconditions:** Account from TC-WS-014.

**Steps:**
1. Upload files until usage reaches **20 GB**.
2. Try one more upload.
3. Edit and save an existing file.

**Expected result:** The meter is red. Step 2 is refused with `ERR_LIMIT_EXCEEDED` and "Storage is full". The Owner and Admin get `storage_full`. Step 3 succeeds.

**Priority:** High

## TC-WS-016: A storage pack lifts the upload block at once

**Preconditions:** Account from TC-WS-015, at 100%.

**Steps:**
1. As the Owner, go to **Settings → Billing → Storage packs → Add pack** and buy **1** pack.
2. Upload a 100 MB file straight away.
3. Open **Settings → Usage**.

**Expected result:** The pack costs **$10/month**, prorated for the rest of the period. The upload succeeds without waiting. The total is now **120 GB**.

**Priority:** High

## TC-WS-017: Version history on Starter goes back 30 days

**Preconditions:** Starter account. A file with a version saved today.

**Steps:**
1. Advance the clock **29 days**, save a new version, open the file and select **Version history**.
2. Advance **2 more days** and open **Version history** again.

**Expected result:** Step 1 lists both versions and the first can be restored. In step 2 the first version, now 31 days old, is gone; the current version remains.

**Priority:** Medium

## TC-WS-018: A Guest can comment but not edit

**Preconditions:** A Guest invited to one project.

**Steps:**
1. As the Guest, add a comment to the project.
2. Try to edit the project and to upload a file.

**Expected result:** The comment is saved. Editing and uploading are refused with `ERR_PERMISSION_DENIED`. The Guest sees no Settings pages.

**Priority:** Medium

Last reviewed: 2026-11-26
