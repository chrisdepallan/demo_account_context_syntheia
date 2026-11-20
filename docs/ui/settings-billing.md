# Settings → Billing

Only the **Owner** and **Billing admins** see this page.

## How do I update the payment method?

Go to **Settings → Billing → Payment method → Update**. The new card is checked with a temporary $0 authorization. If the account is `past_due`, updating the method triggers an immediate retry; paying the balance restores full access within **5 minutes**.

## Which payment methods can I choose?

Cards (Visa, Mastercard, Amex, Discover) on all paid plans. PayPal on Starter to Business (not in India). UPI for Indian accounts. ACH and SEPA bank transfer on annual plans over $1,000 / €1,000. Invoice with net-30 terms on Enterprise.

## Where do I download invoices?

**Settings → Billing → Invoices**. Every invoice is available as a PDF and kept for **7 years**. Invoice IDs look like `INV-2026-004812`.

## How do I change the company name, address or VAT ID on invoices?

Edit them in **Settings → Billing → Billing details** (company name, billing address, VAT/GST ID, PO number). Changes apply to future invoices only. To reissue an invoice from the last **12 months**, contact support.

## How do I add a billing email address?

**Settings → Billing → Billing contacts**. Add up to **5 extra addresses**. They receive invoices and payment alerts but cannot log in unless they are also members.

## How do I change plan or seats?

Upgrade, downgrade or change seats from **Settings → Billing**.

- **Upgrade** takes effect immediately; the prorated difference is charged at once.
- **Downgrade** takes effect at the end of the billing period. It is blocked while usage (members, storage) exceeds the lower plan's limits.
- **Adding seats** is charged immediately, prorated by day. **Removing seats** is credited on the next invoice.

## How do I cancel the subscription?

**Settings → Billing → Cancel subscription**. The plan stays active until the end of the paid period, then moves to Free.

## What does the account look like when a payment fails?

- **Day 0** – account becomes `past_due`; Owner and Billing admins are emailed. Everything still works.
- **Days 1, 3, 7, 14** – automatic retries.
- **Day 14** – account becomes `read_only`: users can log in but not edit.
- **Day 44** – downgraded to Free; members over the Free limit become guests.

Source: `services/billing/docs/*.md`, `services/accounts/docs/plans-and-limits.md` in `demo_account_context`.

Last reviewed: 2026-11-20
