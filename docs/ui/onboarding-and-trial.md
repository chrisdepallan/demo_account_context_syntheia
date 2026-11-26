# Onboarding and Trial

How a new customer signs up, what the 14-day trial includes, and what to set up first.

## How do I sign up?

1. Open `https://app.acme-cloud.example/signup`.
2. Enter your work email, a password (**12 to 128 characters**) and the account name.
3. Choose the region for your first workspace and select **Create account**.

You do not need a payment method. The person who signs up becomes the **Owner** of the new account. The account gets an ID such as `acc_7F3K9Q2M` and one workspace such as `ws_4H8P2L`.

## What does the trial include?

Every new account starts in the `trialing` state on **Pro for 14 days**. All Pro features and limits apply:

- Up to **100 members** and **3 workspaces**
- **50 GB** storage per seat and files up to **5 GB**
- API keys (300 requests per minute per key), **Require MFA**, the audit log and in-app live chat

Business and Enterprise features are not part of the trial: SSO, the web session length setting, phone support, and the `eu-central` and `ap-south` regions. There is one trial per account.

## Where do I see how many trial days are left?

A **trial banner** runs across the top of every dashboard page, for example "Pro trial: 9 days left". Everyone in the account sees it. For the Owner and Billing admins it has an **Add payment method** button that opens **Settings → Billing → Payment method**. The banner turns amber for the last **3 days**.

The same date is shown on **Settings → Billing** as "Trial ends on".

## Which email warns me that the trial is ending?

The `trial_ending` email. It goes to the **Owner**, **3 days** before the trial ends. It cannot be turned off. It is the only trial reminder by email; the banner counts down every day.

## What happens when the trial ends and I have added a payment method?

You do not have to wait for day 14. To keep a paid plan:

1. Go to **Settings → Billing → Payment method → Update** and add a card or another method.
2. Choose the plan (Starter, Pro or Business) and monthly or annual billing.
3. Confirm. The first charge is taken at once for the current number of seats.

When the charge succeeds the account moves from `trialing` to `active`, the banner disappears and an invoice is emailed. If the charge is declined you see `ERR_PAYMENT_FAILED`, the account stays `trialing`, and you can try another method.

Prices per seat: Starter **$8** monthly or **$80** annually; Pro **$20** or **$200**; Business **$45** or **$450**.

## What happens when the trial ends and there is no payment method?

At the end of day 14 the account moves to the **Free** plan and its state becomes `active`. Nothing is charged and **no data is deleted**. What changes:

- Pro-only controls disappear: **Settings → API keys**, **Settings → Audit log**, **Require MFA** and live chat. Existing API keys stop working, because Free has no API.
- **Members**: Free allows **3**. Members over the limit become guests; the Owner always keeps a seat.
- **Storage**: Free allows **2 GB** in total. If you use more, uploads are blocked but existing files stay editable.
- **Workspaces**: Free allows **1**. Extra workspaces stay visible but are read-only until you upgrade.
- **Version history** shortens to **7 days**, and the upload limit drops to **250 MB** per file.

You can upgrade at any time from **Settings → Billing**. An upgrade takes effect immediately and brings the controls back.

## What should I do first?

The **Get started** checklist appears on the dashboard home page for the Owner and Admins until all four steps are done or it is dismissed.

| Step | Where | Who |
|------|-------|-----|
| 1. Invite members | **Settings → Members → Invite** | Owner, Admin |
| 2. Set up MFA | **Profile → Security** | Every user |
| 3. Create a workspace | **Workspaces → New workspace** | Owner, Admin |
| 4. Choose region | Asked when the workspace is created | Owner, Admin |

## How do I invite my team?

Go to **Settings → Members → Invite**, enter up to **50 email addresses per batch**, choose a role and send. Invitations expire after **7 days** and can be resent. During the trial you can have up to 100 members; remember that Free allows only 3 if you do not plan to pay.

Give at least one more person the **Admin** role. Only an Admin can receive an ownership transfer, and a second Admin can reset another user's MFA without waiting for support.

## How do I set up MFA for myself?

Go to **Profile → Security** and add an authenticator app, a security key or passkey, or SMS codes. Save the **10 single-use backup codes** shown after setup. To make MFA compulsory for everyone, turn on **Settings → Security → Require MFA** (Pro and above); users get a **7-day** grace period from their next login.

## How do I create another workspace?

Select **Workspaces → New workspace**, enter a name and pick the region. The trial and Pro allow **3** workspaces, Free and Starter **1**, Business **10**, Enterprise unlimited.

## Which region should I choose?

| Region code | Location | Available on |
|-------------|----------|--------------|
| `us-east` | Virginia, USA | All plans (default) |
| `eu-central` | Frankfurt, Germany | Business and Enterprise |
| `ap-south` | Mumbai, India | Enterprise |

During the trial only `us-east` is offered, because the trial is on Pro. The region is **fixed at creation** and cannot be changed later. If you need `eu-central`, upgrade to Business first and then create the workspace there. To move existing data, export the workspace and create a new one in the other region.

## Can I extend the trial?

Not in the dashboard. The trial is 14 days. After that the account moves to Free and you can upgrade when you are ready; your data is kept.

## Can I cancel during the trial?

There is nothing to cancel, because nothing is charged. If you do not want the account, the Owner can close it under **Settings → Account → Close account**. A closed account can be restored for **30 days**.

## Why do I not see the trial banner?

- The account is already `active` on a paid plan or on Free.
- You joined an existing account by invitation. Only new accounts get a trial; an invited user never starts one.

Source: `docs/reference/constants-and-glossary.md` ("What are the plans and what do they cost?", "What are the account states and how do they change?").

Last reviewed: 2026-11-26
