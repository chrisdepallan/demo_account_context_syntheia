"""ID formats: prefixed IDs, invoice numbers and support ticket numbers."""

from __future__ import annotations

import re

import pytest

from acme_cloud.common.ids import ALPHABET, ID_LENGTHS, IdGenerator, is_valid_id, new_id


@pytest.mark.parametrize(
    ("prefix", "length"),
    [("acc", 8), ("ws", 6), ("usr", 8), ("rf", 10), ("pm", 10), ("key", 8),
     ("exp", 8), ("evt", 12), ("wh", 8), ("sso", 6)],
)
def test_prefixed_ids_have_the_documented_length(ids, prefix, length):
    """An account ID is ``acc_`` + 8 characters, a workspace ID ``ws_`` + 6, and so on."""
    value = ids.new(prefix)
    assert re.fullmatch(rf"{prefix}_[A-Z0-9]{{{length}}}", value)
    assert ID_LENGTHS[prefix] == length
    assert is_valid_id(value, prefix)


def test_ids_avoid_characters_that_are_easy_to_confuse():
    """I, O, 0 and 1 are never used, so IDs can be read aloud on a support call."""
    assert not set("IO01") & set(ALPHABET)
    assert len(ALPHABET) == 32


def test_same_seed_gives_the_same_ids():
    first, second = IdGenerator(seed=7), IdGenerator(seed=7)
    assert [first.new("acc") for _ in range(3)] == [second.new("acc") for _ in range(3)]


def test_ids_from_one_generator_are_different(ids):
    assert len({ids.new("usr") for _ in range(200)}) == 200


def test_unknown_prefix_is_rejected(ids):
    with pytest.raises(ValueError):
        ids.new("zzz")


def test_invoice_ids_use_the_year_and_a_six_digit_sequence(ids):
    assert ids.new_invoice_id(2026) == "INV-2026-000001"
    assert ids.new_invoice_id(2026) == "INV-2026-000002"


def test_ticket_ids_use_a_five_digit_sequence(ids):
    assert ids.new_ticket_id() == "SUP-10001"
    assert ids.new_ticket_id() == "SUP-10002"


def test_new_id_uses_the_shared_generator():
    assert is_valid_id(new_id("ws"), "ws")


@pytest.mark.parametrize(
    ("value", "prefix"),
    [("acc_7F3K9Q2M", "acc"), ("ws_4H8P2L", "ws"), ("usr_2B6N8R4V", "usr"),
     ("rf_8M2K4Q9X7T", "rf"), ("pm_9XK2M4QH7T", "pm"), ("key_5T9W3E7Y", "key"),
     ("exp_6J4D8S2A", "exp"), ("evt_3G7H2K9M4P6Q", "evt"), ("wh_8C2V6B4N", "wh"),
     ("sso_7Q3W9E", "sso"), ("INV-2026-004812", "invoice"), ("SUP-58213", "ticket")],
)
def test_examples_from_the_facts_sheet_are_valid(value, prefix):
    assert is_valid_id(value, prefix)


@pytest.mark.parametrize(
    ("value", "prefix"),
    [("acc_7F3K9Q2", "acc"),        # too short
     ("acc_7F3K9Q2MX", "acc"),      # too long
     ("acc_7f3k9q2m", "acc"),       # lower case
     ("acc_7F3K9Q2O", "acc"),       # letter O is not in the alphabet
     ("ws_4H8P2L", "acc"),          # wrong prefix
     ("7F3K9Q2M", None),            # no prefix
     ("zzz_7F3K9Q2M", None),        # unknown prefix
     ("INV-26-004812", "invoice"),  # two-digit year
     ("INV-2026-4812", "invoice"),  # sequence not padded
     ("SUP-582134", "ticket"),      # six digits
     (12345, None)],                # not a string
)
def test_malformed_ids_are_invalid(value, prefix):
    assert not is_valid_id(value, prefix)


def test_validation_without_a_prefix_accepts_any_known_prefix():
    assert is_valid_id("ws_4H8P2L")
    assert is_valid_id("acc_7F3K9Q2M")
