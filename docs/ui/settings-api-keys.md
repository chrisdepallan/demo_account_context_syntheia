# Settings → API keys

Owners and Admins on **Starter and above**. Free accounts do not see this page.

## How do I create an API key?

1. Go to **Settings → API keys → Create key**.
2. Enter a name, choose scopes and pick an expiry.
3. Copy the key. The full key is shown **only once**; store it in a secrets manager straight away.

Production keys start with `acme_live_`, sandbox keys with `acme_test_`. A workspace can have up to **25 active keys**.

## Which scopes can I choose?

`projects:read`, `projects:write`, `files:read`, `files:write`, `members:read`, `members:write`, and `billing:read` (Owner and Billing admin only). Pick only the scopes the integration needs.

## Which expiry options are offered?

30, 90, 180 or 365 days, or never. "Never" is hidden when an Admin has turned on **Require key expiry**. Owners are emailed **14 days** before a key expires.

## How do I rotate a key?

Select **Rotate** next to the key. A new key is issued and the old one keeps working for **24 hours**.

## How do I revoke a leaked key?

Select **Revoke** next to the key. It stops working within **60 seconds**. Then check the audit log (Pro and above) for requests made with it.

Source: `services/auth/docs/api-keys.md` in `demo_account_context`.

Last reviewed: 2026-11-20
