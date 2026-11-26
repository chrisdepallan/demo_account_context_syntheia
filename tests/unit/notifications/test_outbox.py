"""Outbox: idempotent sends (template + recipient + object ID) and lookup helpers."""

from __future__ import annotations

import pytest

from acme_cloud.common.errors import ValidationError
from acme_cloud.notifications.outbox import Outbox, idempotency_key

OWNER, CONTACT = "owner@example.com", "finance@example.com"
INVOICE = "INV-2026-004812"


@pytest.fixture
def outbox(clock):
    return Outbox(clock)


def test_send_delivers_one_message_per_recipient(outbox, clock):
    delivered = outbox.send("invoice_ready", [OWNER, CONTACT], invoice_id=INVOICE)
    assert [m.to for m in delivered] == [OWNER, CONTACT]
    assert len(outbox) == 2
    message = outbox.last()
    assert message.subject == f"Invoice {INVOICE} is ready"
    assert message.sent_at == clock.now()
    assert message.context == {"invoice_id": INVOICE}


def test_idempotency_key_is_template_recipient_and_object_id():
    assert idempotency_key("invoice_ready", " Owner@Example.com ", INVOICE) == (
        f"invoice_ready|owner@example.com|{INVOICE}")
    assert idempotency_key("invoice_ready", OWNER, None) is None


def test_retried_send_is_not_delivered_twice(outbox):
    """INC-2026-001: a queue retry must not email the invoice to billing contacts again."""
    first = outbox.send("invoice_ready", [OWNER, CONTACT], invoice_id=INVOICE)
    retry = outbox.send("invoice_ready", [OWNER, CONTACT], invoice_id=INVOICE)
    assert len(first) == 2 and retry == []
    assert outbox.count("invoice_ready", CONTACT) == 1
    assert outbox.suppressed == 2


def test_retry_delivers_only_to_recipients_who_did_not_get_it(outbox):
    outbox.send("invoice_ready", [OWNER], invoice_id=INVOICE)
    delivered = outbox.send("invoice_ready", [OWNER, CONTACT], invoice_id=INVOICE)
    assert [m.to for m in delivered] == [CONTACT]


@pytest.mark.parametrize(
    "template, to, object_id",
    [
        ("invoice_ready", OWNER, "INV-2026-004813"),   # another invoice
        ("invoice_ready", CONTACT, INVOICE),           # another recipient
        ("payment_failed", OWNER, INVOICE),            # another template
    ],
)
def test_a_different_template_recipient_or_object_is_a_new_email(outbox, template, to, object_id):
    outbox.send("invoice_ready", [OWNER], object_id=INVOICE)
    assert len(outbox.send(template, [to], object_id=object_id)) == 1


def test_recipient_comparison_ignores_case(outbox):
    outbox.send("invoice_ready", [OWNER], invoice_id=INVOICE)
    assert outbox.send("invoice_ready", ["OWNER@example.com"], invoice_id=INVOICE) == []


def test_explicit_object_id_wins_over_the_template_field(outbox):
    """payment_failed goes out after each failed retry: one object ID per attempt."""
    for attempt in (1, 2, 2):
        outbox.send("payment_failed", [OWNER], object_id=f"{INVOICE}:{attempt}", invoice_id=INVOICE)
    assert outbox.count("payment_failed") == 2
    assert outbox.was_delivered("payment_failed", OWNER, f"{INVOICE}:2")
    assert not outbox.was_delivered("payment_failed", OWNER, f"{INVOICE}:3")


def test_send_without_an_object_id_is_always_delivered(outbox):
    outbox.send("password_reset", ["user@example.com"], link="https://app.acme-cloud.example/r/1")
    outbox.send("password_reset", ["user@example.com"], link="https://app.acme-cloud.example/r/2")
    assert outbox.count("password_reset") == 2
    assert outbox.last().idempotency_key is None


def test_unknown_template_and_bad_address_are_rejected(outbox):
    with pytest.raises(ValidationError):
        outbox.send("weekly_digest", [OWNER])
    with pytest.raises(ValidationError):
        outbox.send("invoice_ready", ["not-an-address"], invoice_id=INVOICE)
    assert len(outbox) == 0


def test_a_single_address_may_be_passed_as_a_string(outbox):
    assert [m.to for m in outbox.send("trial_ending", OWNER, object_id="acc_7F3K9Q2M")] == [OWNER]


def test_lookup_helpers(outbox):
    outbox.send("invoice_ready", [OWNER, CONTACT], invoice_id=INVOICE)
    outbox.send("storage_warning", [OWNER], object_id="ws_4H8P2L")
    assert [m.template_key for m in outbox.sent_to(OWNER)] == ["invoice_ready", "storage_warning"]
    assert [m.to for m in outbox.by_template("invoice_ready")] == [OWNER, CONTACT]
    assert outbox.count() == 3 and outbox.count(to=CONTACT) == 1
    assert outbox.count("storage_warning", OWNER) == 1
    assert isinstance(outbox.messages, tuple) and len(outbox.messages) == 3
    assert Outbox.__len__(outbox) == 3


def test_empty_outbox_has_no_last_message(outbox):
    assert outbox.last() is None and outbox.suppressed == 0
