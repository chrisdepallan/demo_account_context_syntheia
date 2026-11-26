"""Acme Cloud sample modules.

Packages:

- ``common``         shared enums, errors, IDs, clock and money helpers
- ``accounts``       accounts, plans, members, roles, account state machine
- ``workspaces``     workspaces, regions, storage, exports
- ``billing``        subscriptions, proration, invoices, dunning, refunds
- ``auth``           passwords, lockout, MFA, sessions, SSO
- ``api_keys``       key creation, scopes, rotation, revocation
- ``support``        tickets, priorities, SLA targets, escalation
- ``notifications``  email templates and the outbox
- ``audit``          append-only audit log with plan-based retention

Everything is in memory and uses only the standard library. All business
values come from ``docs/reference/constants-and-glossary.md``.
"""

__version__ = "2026.8"
