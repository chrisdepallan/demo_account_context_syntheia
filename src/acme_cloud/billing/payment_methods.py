"""Payment methods: which types an account may use, and how they are stored.

Which method is allowed where:

- Cards (Visa, Mastercard, Amex, Discover): all paid plans.
- PayPal: Starter to Business. Not on Enterprise and not for accounts in India.
- UPI: accounts in India (country code ``IN``) only.
- ACH and SEPA bank transfer: annual plans whose period total is over $1,000
  (ACH, USD accounts) or over EUR 1,000 (SEPA, EUR accounts). Exactly 1,000
  is not enough.
- Invoice with net-30 terms: Enterprise only.
- Free: no payment method is needed, so none can be added.

How a method is stored (ADR 0004): only an opaque processor token such as
``pm_9XK2M4QH7T`` with the type and, for cards, the brand. The card number
never reaches this code: the customer types it into the processor's hosted
form and the processor hands back the token. There is no card-number field in
any model, log line or error.

Adding or updating a method runs a temporary $0 authorization at the
processor. A decline raises ``ERR_PAYMENT_FAILED`` and nothing is stored.
"""

from __future__ import annotations

from typing import Protocol

from acme_cloud.billing.models import (
    BillingInterval,
    ChargeOutcome,
    PaymentMethod,
    PaymentMethodType,
    ProcessorUnavailableError,
)
from acme_cloud.common.clock import Clock
from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import PaymentFailedError, ValidationError
from acme_cloud.common.ids import IdGenerator
from acme_cloud.common.money import Money

#: Card brands accepted on all paid plans.
CARD_BRANDS = ("visa", "mastercard", "amex", "discover")

#: ACH and SEPA need an annual period total strictly over 1,000.00.
BANK_TRANSFER_MINIMUM_CENTS = 100_000
BANK_TRANSFER_BY_CURRENCY = {"USD": PaymentMethodType.ACH, "EUR": PaymentMethodType.SEPA}

#: ISO country code of India: UPI is offered there and PayPal is not.
INDIA = "IN"

#: Enterprise invoices are due 30 days after issue.
INVOICE_NET_TERMS_DAYS = 30

#: Amount of the authorization used to check a new method.
AUTHORIZATION_CHECK_CENTS = 0


class PaymentProcessor(Protocol):
    """What billing needs from the external payment processor."""

    def authorize(self, token: str, amount: Money) -> ChargeOutcome: ...

    def charge(self, token: str, amount: Money) -> ChargeOutcome: ...

    def refund(self, reference: str, amount: Money) -> ChargeOutcome: ...


def allowed_method_types(
    plan: Plan, country: str, interval: BillingInterval, amount: Money,
) -> tuple[PaymentMethodType, ...]:
    """Payment method types an account may choose.

    ``amount`` is the total of one billing period; ``country`` is a
    two-letter ISO code such as ``US``, ``DE`` or ``IN``.
    """
    if not plan.is_paid:
        return ()
    in_india = country.strip().upper() == INDIA
    allowed = [PaymentMethodType.CARD]
    if Plan.STARTER.rank <= plan.rank <= Plan.BUSINESS.rank and not in_india:
        allowed.append(PaymentMethodType.PAYPAL)
    if in_india:
        allowed.append(PaymentMethodType.UPI)
    if interval is BillingInterval.ANNUAL and amount.cents > BANK_TRANSFER_MINIMUM_CENTS:
        allowed.append(BANK_TRANSFER_BY_CURRENCY[amount.currency])
    if plan is Plan.ENTERPRISE:
        allowed.append(PaymentMethodType.INVOICE)
    return tuple(allowed)


def require_method_allowed(
    method_type: PaymentMethodType, plan: Plan, country: str,
    interval: BillingInterval, amount: Money,
) -> None:
    """Raise ``ERR_VALIDATION`` when the method type is not offered to this account."""
    allowed = allowed_method_types(plan, country, interval, amount)
    if method_type not in allowed:
        raise ValidationError(
            f"{method_type.value} is not available for this plan, country or amount",
            method=method_type.value, allowed=[m.value for m in allowed])


def normalize_brand(method_type: PaymentMethodType, brand: str | None) -> str | None:
    """Return the lower-case card brand, or None for methods that are not cards."""
    if method_type is not PaymentMethodType.CARD:
        return None
    cleaned = (brand or "").strip().lower()
    if cleaned not in CARD_BRANDS:
        raise ValidationError("card brand must be Visa, Mastercard, Amex or Discover",
                              accepted=list(CARD_BRANDS))
    return cleaned


def add_payment_method(
    processor: PaymentProcessor, ids: IdGenerator, clock: Clock, account_id: str,
    method_type: PaymentMethodType, plan: Plan, country: str,
    interval: BillingInterval, amount: Money, brand: str | None = None,
) -> PaymentMethod:
    """Check and store a new payment method as a token.

    Steps: the type must be allowed for the plan, country, interval and
    amount; a card must have an accepted brand; then a $0 authorization is
    run. Invoice (net-30) has nothing to authorize.
    """
    require_method_allowed(method_type, plan, country, interval, amount)
    brand = normalize_brand(method_type, brand)
    token = ids.new("pm")
    if method_type is not PaymentMethodType.INVOICE:
        check = Money(AUTHORIZATION_CHECK_CENTS, amount.currency)
        outcome = processor.authorize(token, check)
        if outcome is ChargeOutcome.DECLINED:
            raise PaymentFailedError("the $0 authorization was declined", method=method_type.value)
        if outcome is ChargeOutcome.UNAVAILABLE:
            raise ProcessorUnavailableError("the payment processor is unavailable; try again")
    return PaymentMethod(token=token, account_id=account_id, type=method_type,
                         brand=brand, added_at=clock.now())
