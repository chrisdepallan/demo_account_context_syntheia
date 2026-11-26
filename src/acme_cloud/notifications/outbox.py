"""In-memory email outbox with idempotent sends.

Background (INC-2026-001, 2026-02-11): a retry in the notification queue was
not idempotent and invoice emails were sent twice to billing contacts. Since
release 2026.2 every send carries an idempotency key:

    template key + recipient + object ID

A send whose key was already delivered is suppressed, so a retried job
cannot email the same person about the same object twice.

How the object ID is found:

1. the ``object_id`` value in the send context, if given;
2. otherwise the template's own object field (``invoice_id`` for
   ``invoice_ready``, ``key_id`` for ``key_expiring``, ``export_id`` for
   ``export_ready``);
3. if neither is present the message has no idempotency key and is always
   delivered.

Callers that send the same template about the same object on purpose (an
invitation resend, ``payment_failed`` after each failed retry) pass a
different ``object_id`` for each occasion, for example ``INV-2026-000007:2``.

Recipients are compared in lower case. ``Outbox.send`` matches the
``notifier.send(template_key, to, **context)`` shape that other packages call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from acme_cloud.common.clock import Clock
from acme_cloud.common.errors import ValidationError
from acme_cloud.notifications.templates import get_template, render


@dataclass(frozen=True)
class OutboxMessage:
    """One delivered email."""

    template_key: str
    to: str
    subject: str
    body: str
    sent_at: datetime
    idempotency_key: str | None
    context: dict[str, Any] = field(default_factory=dict, compare=False)


def idempotency_key(template_key: str, recipient: str, object_id: object | None) -> str | None:
    """Build ``template|recipient|object ID``; None when there is no object ID."""
    if object_id is None or object_id == "":
        return None
    return f"{template_key}|{recipient.strip().lower()}|{object_id}"


class Outbox:
    """Collects emails instead of sending them; safe to call twice."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._messages: list[OutboxMessage] = []
        self._delivered_keys: set[str] = set()
        self.suppressed = 0   # duplicate sends that were not delivered

    def send(self, template_key: str, to: list[str], **context: Any) -> list[OutboxMessage]:
        """Deliver ``template_key`` to each address in ``to``.

        Returns the messages actually delivered. Addresses that already got
        this template for this object are skipped and counted in
        ``suppressed``. An unknown template raises ``ERR_VALIDATION``.
        """
        template = get_template(template_key)
        if isinstance(to, str):
            to = [to]
        object_id = context.get("object_id")
        if object_id is None and template.object_field:
            object_id = context.get(template.object_field)
        rendered = render(template_key, **context)
        delivered = []
        for address in to:
            address = address.strip().lower()
            if "@" not in address:
                raise ValidationError("recipient must be an email address")
            key = idempotency_key(template_key, address, object_id)
            if key is not None:
                if key in self._delivered_keys:
                    self.suppressed += 1
                    continue
                self._delivered_keys.add(key)
            message = OutboxMessage(template_key, address, rendered.subject, rendered.body,
                                    self._clock.now(), key, dict(context))
            self._messages.append(message)
            delivered.append(message)
        return delivered

    # -- lookup helpers -----------------------------------------------------
    @property
    def messages(self) -> tuple[OutboxMessage, ...]:
        """All delivered messages, oldest first."""
        return tuple(self._messages)

    def sent_to(self, address: str) -> list[OutboxMessage]:
        """Messages delivered to one address."""
        address = address.strip().lower()
        return [m for m in self._messages if m.to == address]

    def by_template(self, template_key: str) -> list[OutboxMessage]:
        """Messages delivered with one template."""
        return [m for m in self._messages if m.template_key == template_key]

    def count(self, template_key: str | None = None, to: str | None = None) -> int:
        """Number of delivered messages, optionally for one template and/or address."""
        found = self._messages if template_key is None else self.by_template(template_key)
        if to is not None:
            found = [m for m in found if m.to == to.strip().lower()]
        return len(found)

    def was_delivered(self, template_key: str, to: str, object_id: object) -> bool:
        """True when this template was already delivered to ``to`` for ``object_id``."""
        return idempotency_key(template_key, to, object_id) in self._delivered_keys

    def last(self) -> OutboxMessage | None:
        return self._messages[-1] if self._messages else None

    def __len__(self) -> int:
        return len(self._messages)
