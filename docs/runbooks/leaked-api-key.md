# Runbook: Leaked API Key

**For:** support agents (helping the customer) and the on-call engineer (when a revoked key keeps working).

This runbook was written after INC-2026-006 (2026-10-15, P3, 5 days to detect). In `ap-south`, revoked API keys kept working for up to 15 minutes instead of 60 seconds, because the key cache lifetime had been set to 900 seconds in that region's configuration. Since release 2026.8 the cache lifetime is fixed at 60 seconds in code and cannot differ between regions. The change to this process is step 4 below: after a revocation we now check that the key is refused in all three regions, and no longer assume it.

## What counts as a leaked key?

A key is leaked when anyone who should not have it may have seen it. Common cases:

- the key was committed to a code repository, public or private;
- it was pasted into a chat, a ticket, an email or a document;
- it was printed in logs or shown in a screenshot;
- a laptop or server holding it was lost or broken into;
- a person who knew it has left the company.

Treat "may have been seen" the same as "was seen". Revoking costs minutes; a misused key can change or copy a workspace's data.

## What are the symptoms?

- The customer reports the leak themselves.
- The customer sees API activity they do not recognise in the audit log.
- Acme Cloud staff find a string starting with `acme_live_` somewhere public.
- A workspace's request count rises sharply and its integrations start to receive `ERR_RATE_LIMITED` (HTTP 429).

## How do I identify the key without seeing it?

Never ask the customer to send the key, and never paste one into a ticket. If a customer sends one anyway, remove it from the ticket and treat the key as leaked.

1. Ask for the key's name or its last 4 characters. Both are shown in **Settings → API keys**.
2. Open **Admin console → Account → API keys**. It lists each key's ID (such as `key_5T9W3E7Y`), name, prefix (`acme_live_` or `acme_test_`), last 4 characters, scopes, expiry and last-used time.
3. Match the key and note its ID and scopes. The scopes tell you what an attacker could do: `files:read` means files could be copied; `members:write` means members could be added or removed.

Sandbox keys (`acme_test_`) cannot reach production data. They should still be revoked, but without urgency.

## What do I do, step by step?

1. **Have the key revoked, not rotated.** Rotation keeps the old key working for 24 hours, which is the opposite of what is needed. The customer's Owner or Admin goes to **Settings → API keys**, selects **Revoke** next to the key and confirms.
2. **If no Owner or Admin can do it quickly**, support can revoke. The request must come from an Owner or Admin of the account, through a ticket opened while signed in. Then select **Admin console → Account → API keys → Revoke** and enter the ticket ID, for example `SUP-58213`, as the reason.
3. **If staff found the key in public and the customer does not answer**: email the Owner and all Admins. If there is no reply within 1 business hour and the key is still publicly visible, the support team lead may approve a revocation by support.
4. **Check the revocation in every region.** Wait 60 seconds, then select **Admin console → Account → API keys → Check key status**. It asks the API nodes in `us-east`, `eu-central` and `ap-south` whether they still accept the key. All three must answer "revoked".
5. **If any region still accepts the key 2 minutes after revocation**, page the on-call engineer. This is a platform fault of the kind seen in INC-2026-006.
6. **Review what the key did.** On Pro and above, the Owner or an Admin opens the audit log, or the agent opens **Admin console → Account → Audit log**, and filters by the key ID from the earliest time the leak could have happened. Look for `member.invited`, `member.removed`, `export.started`, `export.downloaded` and `api_key.created`. Starter accounts have no audit log; tell the customer this plainly.
7. **Check for keys created with the leaked key.** A key cannot create other keys through the API, but a person who also had a login could. Revoke any key the customer does not recognise.
8. **Create a replacement** in **Settings → API keys → Create key** with only the scopes the integration needs and an expiry of 90 days or less. The full key is shown once.
9. **Recommend Require key expiry.** An Owner or Admin turns it on in **Settings → Security → Require key expiry**. It blocks keys that never expire.

## What does the on-call engineer do when a revoked key still works?

1. Acknowledge the page within 5 minutes. Open a P2 incident: a security control is not working as promised.
2. In **Admin console → Operations → Queues → Key cache**, select **Flush** for the region that still accepts the key. The key is refused as soon as the flush finishes.
3. Run **Check key status** again. All three regions must answer "revoked".
4. Find out why the cache held the key for longer than 60 seconds. Compare the running release in each region; a region that is one release behind is the first suspect.
5. Escalate to the Identity team within 30 minutes, even if the flush worked.

## What do I tell the customer?

- "Please revoke the key now in **Settings → API keys**. It will stop working within 60 seconds. Do not use **Rotate** for a leaked key, because the old key would keep working for 24 hours."
- "We cannot see or recover your key. We store only a hash and the last 4 characters."
- "Your integration will fail with `ERR_UNAUTHENTICATED` until you give it the new key."
- "The key had these scopes: <list>. The audit log shows what was done with it since <time>."
- If they subscribe to webhooks: "You will receive an `api_key.revoked` event for this key."
- If the key was in a public repository: "Removing the file is not enough. The key remains in the repository history, so it must be revoked."

## When and to whom do I escalate?

| Situation | Escalate to | Within |
|-----------|-------------|--------|
| Revoked key accepted in any region after 2 minutes | On-call engineer | At once |
| Audit log shows data exported or members changed by the leaked key | Support team lead; treat the ticket as P1 (data at risk) | At once |
| Customer does not answer and the key is public | Support team lead | 1 business hour |
| Cache flush did not help | Identity team | At once |

## What happens after the incident?

1. Add the key ID, the revocation time and the result of **Check key status** to the ticket.
2. Confirm that the audit log has an `api_key.revoked` event for the key.
3. For a platform fault, write the incident report under `reports/incidents/` within 5 business days.
4. Suggest that the customer scans their repositories for the prefixes `acme_live_` and `acme_test_`.

## Related links

- Incident: `reports/incidents/INC-2026-006-key-revocation-delay.md`
- Releases: `reports/releases/2026.8.md` (cache lifetime fixed in code), `reports/releases/2026.2.md` (**Require key expiry**)
- Decision: `docs/architecture/adr/0005-hash-api-keys-and-show-them-once.md`
- Code: `src/acme_cloud/api_keys/service.py`, `src/acme_cloud/api_keys/rotation.py`, `src/acme_cloud/api_keys/scopes.py`
- UI: `docs/ui/settings-api-keys.md` ("How do I revoke a leaked key?"), `docs/ui/settings-security.md`
- Audit log design: `docs/architecture/adr/0008-audit-log-is-append-only.md`

Last reviewed: 2026-11-26
