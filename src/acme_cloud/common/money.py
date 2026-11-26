"""Money as whole cents, so no float rounding reaches an invoice."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SUPPORTED_CURRENCIES = ("USD", "EUR")
_SYMBOLS = {"USD": "$", "EUR": "€"}


@dataclass(frozen=True, order=True)
class Money:
    """An amount in the smallest unit (cents) of one currency."""

    cents: int
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.cents, int):
            raise TypeError("Money.cents must be an int; use Money.from_major for decimals")
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency: {self.currency}")

    @classmethod
    def from_major(cls, amount: int | float | str | Decimal, currency: str = "USD") -> "Money":
        """Build from dollars or euros: ``Money.from_major("19.99")``."""
        cents = (Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return cls(int(cents), currency)

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        return cls(0, currency)

    def _check(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(f"currency mismatch: {self.currency} and {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.cents - other.cents, self.currency)

    def __mul__(self, factor: int) -> "Money":
        if not isinstance(factor, int):
            raise TypeError("multiply Money by an int; use prorate() for fractions")
        return Money(self.cents * factor, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.cents, self.currency)

    def prorate(self, numerator: int, denominator: int) -> "Money":
        """Return ``self * numerator / denominator``, rounded half up to a cent.

        Used for day-based proration: ``price.prorate(days_left, days_in_period)``.
        """
        if denominator <= 0:
            raise ValueError("denominator must be positive")
        exact = Decimal(self.cents) * Decimal(numerator) / Decimal(denominator)
        return Money(int(exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), self.currency)

    @property
    def is_zero(self) -> bool:
        return self.cents == 0

    @property
    def is_negative(self) -> bool:
        return self.cents < 0

    def __str__(self) -> str:
        sign = "-" if self.cents < 0 else ""
        whole, part = divmod(abs(self.cents), 100)
        return f"{sign}{_SYMBOLS[self.currency]}{whole:,}.{part:02d}"
