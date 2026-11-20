# Settings → Members

Owners and Admins manage people on this page.

## How do I invite a member?

1. Go to **Settings → Members → Invite**.
2. Enter one or more email addresses (up to **50 per batch**).
3. Choose a role and send.

Invitations expire after **7 days** and can be resent from the same page.

## Why can't I invite more members?

The plan's member limit is reached: Free **3**, Starter **10**, Pro **100**, Business **500**, Enterprise unlimited. Add seats or upgrade in **Settings → Billing**. Guests do not use seats; each paid seat allows **5 guests**.

## How do I remove a member?

Go to **Settings → Members**, choose the member and select **Remove**. Access ends immediately. Their content stays in the workspace and is reassigned to the person who removed them. The freed seat is credited on the next invoice, prorated by day.

## How do I reset a member's MFA?

**Settings → Members → choose the member → Reset MFA**. Use this when someone lost both their MFA device and backup codes. If the person locked out is the only Admin or the Owner, support must do it (up to **2 business days**).

## Who can do what?

| Action | Owner | Admin | Billing admin | Member | Guest |
|--------|-------|-------|---------------|--------|-------|
| Create and edit projects | Yes | Yes | No | Yes | No |
| Comment | Yes | Yes | No | Yes | Yes |
| Invite / remove members | Yes | Yes | No | No | No |
| Change security settings (SSO, MFA policy) | Yes | Yes | No | No | No |
| View and pay invoices | Yes | No | Yes | No | No |
| Change plan or payment method | Yes | No | Yes | No | No |
| Transfer ownership | Yes | No | No | No | No |
| Close the account | Yes | No | No | No | No |

Source: `services/accounts/docs/members-and-roles.md` in `demo_account_context`.

Last reviewed: 2026-11-20
