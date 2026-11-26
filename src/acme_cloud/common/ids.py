"""ID generation and validation.

Formats (see ``docs/reference/constants-and-glossary.md``):

- prefixed IDs: ``acc_7F3K9Q2M``, ``ws_4H8P2L``, ``usr_2B6N8R4V`` and so on
- invoices: ``INV-2026-004812`` (year plus a 6-digit sequence)
- support tickets: ``SUP-58213`` (5-digit sequence)
"""

from __future__ import annotations

import random
import re

#: Characters used in the random part of an ID. I, O, 0 and 1 are left out
#: so IDs are easy to read aloud on a support call.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

#: Length of the random part for each prefix.
ID_LENGTHS = {
    "acc": 8,
    "ws": 6,
    "usr": 8,
    "rf": 10,
    "pm": 10,
    "key": 8,
    "exp": 8,
    "evt": 12,
    "wh": 8,
    "sso": 6,
    "inv": 8,   # invitation
    "sub": 8,   # subscription
    "ses": 12,  # session
    "tr": 8,    # ownership transfer request
}

_INVOICE_RE = re.compile(r"^INV-\d{4}-\d{6}$")
_TICKET_RE = re.compile(r"^SUP-\d{5}$")


class IdGenerator:
    """Makes IDs. Pass a ``seed`` to get the same IDs on every run (tests)."""

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)
        self._invoice_seq = 0
        self._ticket_seq = 10000

    def new(self, prefix: str) -> str:
        """Return a new prefixed ID such as ``acc_7F3K9Q2M``."""
        if prefix not in ID_LENGTHS:
            raise ValueError(f"unknown ID prefix: {prefix}")
        body = "".join(self._random.choice(ALPHABET) for _ in range(ID_LENGTHS[prefix]))
        return f"{prefix}_{body}"

    def new_invoice_id(self, year: int) -> str:
        """Return the next invoice ID for ``year``, such as ``INV-2026-000001``."""
        self._invoice_seq += 1
        return f"INV-{year}-{self._invoice_seq:06d}"

    def new_ticket_id(self) -> str:
        """Return the next support ticket ID, such as ``SUP-10001``."""
        self._ticket_seq += 1
        return f"SUP-{self._ticket_seq:05d}"


_default = IdGenerator()


def new_id(prefix: str) -> str:
    """Return a new prefixed ID from the shared, unseeded generator."""
    return _default.new(prefix)


def is_valid_id(value: str, prefix: str | None = None) -> bool:
    """Check that ``value`` is a well-formed ID.

    With ``prefix`` the ID must have that prefix. ``prefix`` may also be
    ``"invoice"`` or ``"ticket"`` for the two dashed formats.
    """
    if not isinstance(value, str):
        return False
    if prefix == "invoice":
        return bool(_INVOICE_RE.match(value))
    if prefix == "ticket":
        return bool(_TICKET_RE.match(value))
    head, sep, body = value.partition("_")
    if not sep or head not in ID_LENGTHS:
        return False
    if prefix is not None and head != prefix:
        return False
    return len(body) == ID_LENGTHS[head] and all(ch in ALPHABET for ch in body)
