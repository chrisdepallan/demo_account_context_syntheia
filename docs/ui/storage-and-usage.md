# Settings → Usage

**Settings → Usage** shows how much of the plan the account is using: storage, members, seats, guests and workspaces. **Owners** and **Admins** see this page. Storage packs are bought by the Owner or a Billing admin in **Settings → Billing**.

## Where do I see how much storage we use?

Go to **Settings → Usage**. The **storage meter** at the top shows used storage against the account total, for example "412 GB of 600 GB (69%)". Below it, a table lists storage per workspace.

The meter is recalculated every **15 minutes**. Changes to seats, plan or storage packs change the total at once.

## How much storage does each plan include?

| Plan | Storage |
|------|---------|
| Free | **2 GB** in total |
| Starter | **10 GB** per seat |
| Pro | **50 GB** per seat |
| Business | **200 GB** per seat |
| Enterprise | **1 TB** per seat |

Storage is pooled. It is one total for the whole account, not a personal quota per member.

## How is the storage total worked out?

Total = seats × storage per seat + storage packs × 100 GB.

Example: a Pro account with **12 seats** has 12 × 50 GB = **600 GB**. With **2 storage packs** it has **800 GB**. Guests do not add storage because they do not use seats.

The dashboard counts 1 GB as 1,024 MB and 1 TB as 1,024 GB.

## What counts towards storage?

- Every file in every workspace of the account.
- Older versions of files that are still inside the plan's version history window.

Comments, project settings and the audit log do not count. Export ZIP files do not count either.

## What happens at 90% storage?

The meter turns amber and a banner appears on **Settings → Usage**. The Owner and Admins get the `storage_warning` email, once, when usage first crosses **90%**. Nothing is blocked. In the example above (800 GB total) the warning comes at **720 GB**.

## What happens at 100% storage?

The meter turns red and **uploads are blocked** for everyone in the account. Uploading shows "Storage is full" (error code `ERR_LIMIT_EXCEEDED`). The Owner and Admins get the `storage_full` email.

Existing files **stay editable**. Nothing is deleted, and downloads and exports keep working.

## How do I get uploads working again?

Any of these lifts the block immediately:

1. **Buy a storage pack**: **Settings → Billing → Storage packs → Add pack** (Owner or Billing admin).
2. **Add seats**: **Settings → Billing** (Owner or Billing admin). Each seat adds the plan's per-seat storage.
3. **Upgrade the plan**: **Settings → Billing**. Upgrades take effect immediately.

You can also delete files you no longer need. The meter catches up within **15 minutes**.

## What is a storage pack?

A storage pack adds **100 GB for $10/month**. Packs are available on **any paid plan** and you can buy **any number** of them. Free accounts cannot buy packs.

- Adding a pack is charged immediately, prorated by day for the rest of the billing period.
- Removing a pack takes effect at the end of the billing period. It is blocked if usage would then be above the new total.
- Packs appear as their own line on the invoice.

## How large can one uploaded file be?

| Plan | Maximum file size |
|------|-------------------|
| Free | **250 MB** |
| Starter | **250 MB** |
| Pro | **5 GB** |
| Business | **5 GB** |
| Enterprise | **5 GB** |

A larger file is rejected before the upload starts, with "File is too large for your plan" (`ERR_LIMIT_EXCEEDED`). The limit applies to each file, in the dashboard and through the API. Storage packs do not change it; only the plan does.

## How long is version history kept?

| Plan | Version history |
|------|-----------------|
| Free | **7 days** |
| Starter | **30 days** |
| Pro | **180 days** |
| Business | **1 year** |
| Enterprise | Unlimited |

Open a file and select **Version history** to see and restore older versions. Versions older than the window are removed automatically and stop counting towards storage. The current version of a file is never removed by this rule.

After a downgrade, the shorter window applies from the day the lower plan starts.

## Where do I see member, seat and guest counts?

The **People** section of **Settings → Usage** shows three counters:

- **Members** – people with the Owner, Admin, Billing admin or Member role, against the plan limit: Free **3**, Starter **10**, Pro **100**, Business **500**, Enterprise unlimited.
- **Seats** – paid seats, and how many are in use. Every member uses one seat. A pending invitation holds a seat until it is accepted or expires after **7 days**.
- **Guests** – guests in use against the guest allowance.

To change any of them, use **Settings → Members** (people) or **Settings → Billing** (seats).

## How many guests can we have?

Guests do not use seats. Each paid seat allows **5 guests**, so 12 seats allow **60 guests**. Free accounts allow **5 guests** in total. When the allowance is used up, inviting another guest fails with `ERR_LIMIT_EXCEEDED`; add a seat or remove a guest.

## Where do I see how many workspaces we have?

The **Workspaces** counter on **Settings → Usage** shows workspaces in use against the plan limit: Free and Starter **1**, Pro **3**, Business **10**, Enterprise unlimited. Each row shows the workspace ID (for example `ws_4H8P2L`), its region and its storage.

## Why can I not downgrade the plan?

A downgrade is blocked while **members**, **workspaces** or **storage** are above the lower plan's limits. **Settings → Usage** marks each counter that is over the target plan in red. Remove members, delete workspaces or delete files, then try again in **Settings → Billing**.

Example: a Pro account with 14 members cannot move to Starter (limit 10) until 4 members are removed or changed to guests.

## Does the API rate limit show on this page?

No. **Settings → Usage** covers storage, people and workspaces. API limits per key are fixed by plan: Starter **60**, Pro **300**, Business **1,000** and Enterprise **5,000** requests per minute. A key over its limit gets HTTP 429 with a `Retry-After` header.

## Why does a Member not see Settings → Usage?

The page is for Owners and Admins. Members and Guests who hit a limit see the error message only, and should ask an Admin. Billing admins see storage packs and seats in **Settings → Billing**, not this page.

Source: `docs/reference/constants-and-glossary.md` ("What are the plan limits?", "What are the billing rules?").

Last reviewed: 2026-11-26
