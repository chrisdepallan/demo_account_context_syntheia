"""SupportService: open ticket, first response, escalate, identity verification."""

from __future__ import annotations

import pytest

from acme_cloud.common.enums import Plan
from acme_cloud.common.errors import (
    ConflictError, NotFoundError, PermissionDeniedError, PlanRequiredError,
)
from acme_cloud.common.ids import is_valid_id
from acme_cloud.support import service as service_module
from acme_cloud.support.models import Channel, Priority, TicketStatus
from acme_cloud.support.service import SupportService


@pytest.fixture
def service(clock, ids, audit, at_central) -> SupportService:
    clock.set(at_central(5, 10))  # Monday 2026-01-05, 10:00 Central
    return SupportService(clock, ids, audit=audit)


def open_ticket(service, plan=Plan.PRO, priority=Priority.P2, channel=Channel.EMAIL,
                message="Exports fail with an error."):
    return service.open_ticket("acc_TEST0001", "dana@example.com", "Exports fail", message,
                               priority, channel, plan)


def test_opening_a_ticket_gives_a_sup_id_and_a_first_response_due_time(service, at_central):
    ticket = open_ticket(service)                       # Pro P2: 8 business hours
    assert is_valid_id(ticket.id, "ticket")
    assert ticket.status is TicketStatus.OPEN
    assert ticket.opened_at == at_central(5, 10)
    assert ticket.first_response_due == at_central(5, 18)
    assert ticket.status_page_due is None
    assert service.get(ticket.id) is ticket


def test_ticket_opened_friday_1700_on_pro_p1_is_due_monday_1100(service, clock, at_central):
    clock.set(at_central(9, 17))
    assert open_ticket(service, priority=Priority.P1).first_response_due == at_central(12, 11)


def test_p1_ticket_gets_a_15_minute_status_page_deadline(service, at_central):
    ticket = open_ticket(service, Plan.ENTERPRISE, Priority.P1, Channel.PHONE)
    assert ticket.status_page_due == at_central(5, 10, 15)
    assert ticket.first_response_due == at_central(5, 10, 30)   # Enterprise P1: 30 minutes


@pytest.mark.parametrize("plan, channel", [
    (Plan.FREE, Channel.CHAT), (Plan.STARTER, Channel.CHAT), (Plan.PRO, Channel.PHONE),
])
def test_ticket_on_a_channel_the_plan_lacks_is_refused(service, plan, channel):
    with pytest.raises(PlanRequiredError):
        open_ticket(service, plan=plan, channel=channel)


def test_first_response_inside_the_target_meets_the_sla(service, clock):
    ticket = open_ticket(service)
    clock.advance(hours=7, minutes=59)
    assert service.record_first_response(ticket.id, "We are looking into it.") is True
    assert ticket.status is TicketStatus.PENDING
    assert not service.is_sla_breached(ticket.id)


def test_first_response_after_the_target_is_a_breach(service, clock):
    ticket = open_ticket(service)
    clock.advance(hours=8, minutes=1)
    assert service.is_sla_breached(ticket.id)
    assert service.record_first_response(ticket.id, "Sorry for the wait.") is False
    assert service.is_sla_breached(ticket.id)


def test_a_ticket_has_only_one_first_response(service):
    ticket = open_ticket(service)
    service.record_first_response(ticket.id, "Hello")
    with pytest.raises(ConflictError):
        service.record_first_response(ticket.id, "Hello again")


def test_customer_reply_escalate_sends_the_ticket_to_a_team_lead(service, clock, at_central):
    ticket = open_ticket(service)
    service.record_first_response(ticket.id, "Please clear your cache.")
    service.customer_reply(ticket.id, "That did not help.")
    assert ticket.status is TicketStatus.OPEN and not ticket.is_escalated

    clock.set(at_central(5, 15))
    service.customer_reply(ticket.id, "Escalate")
    assert ticket.status is TicketStatus.ESCALATED
    assert ticket.escalation_review_due == at_central(6, 15)   # 1 business day


def test_solved_ticket_cannot_be_escalated_and_unknown_ticket_is_not_found(service):
    ticket = open_ticket(service)
    ticket.status = TicketStatus.SOLVED
    with pytest.raises(ConflictError):
        service.escalate(ticket.id)
    with pytest.raises(NotFoundError):
        service.escalate("SUP-99999")


def test_secrets_in_customer_messages_are_removed_before_storing(service):
    ticket = open_ticket(service, message="My password is sample-secret-value, please log in.")
    stored = ticket.messages[0]
    assert "sample-secret-value" not in stored.body
    assert stored.flags == ("password",)
    service.customer_reply(ticket.id, "Thanks for the help!")
    assert ticket.messages[1].flags == ()


def test_owner_change_takes_up_to_5_business_days_and_needs_officer_confirmation(service,
                                                                                at_central):
    ticket = open_ticket(service, priority=Priority.P4)
    request = service.start_owner_change(ticket.id)
    assert service_module.OWNER_CHANGE_BUSINESS_DAYS == 5
    assert request.due_at == at_central(12, 10)          # Monday -> next Monday, 10:00
    assert "officer_written_confirmation" in request.steps

    service.complete_step(ticket.id, "ticket_from_account_email")
    with pytest.raises(PermissionDeniedError):           # email alone is never enough
        service.approve_verification(ticket.id, "agent-1")
    service.complete_step(ticket.id, "officer_written_confirmation")
    assert service.approve_verification(ticket.id, "agent-1").approved_at is not None


def test_mfa_reset_for_the_only_admin_or_owner_takes_up_to_2_business_days(service, audit,
                                                                           at_central):
    ticket = open_ticket(service, priority=Priority.P3)
    request = service.start_mfa_reset(ticket.id, is_only_admin_or_owner=True)
    assert service_module.MFA_RESET_BUSINESS_DAYS == 2
    assert request.due_at == at_central(7, 10)           # Monday -> Wednesday, 10:00
    assert request.remaining_steps == ["ticket_from_account_email", "identity_check_beyond_email"]

    with pytest.raises(PermissionDeniedError):
        service.approve_verification(ticket.id, "agent-1")
    service.complete_step(ticket.id, "identity_check_beyond_email")
    with pytest.raises(PermissionDeniedError):           # one step still missing
        service.approve_verification(ticket.id, "agent-1")
    service.complete_step(ticket.id, "ticket_from_account_email")
    service.approve_verification(ticket.id, "agent-1")
    assert audit.events == [("mfa.reset", "agent-1", "acc_TEST0001", None,
                             {"ticket_id": ticket.id, "via": "support"})]


def test_other_members_are_sent_to_their_own_admin_for_an_mfa_reset(service):
    ticket = open_ticket(service)
    with pytest.raises(PermissionDeniedError):
        service.start_mfa_reset(ticket.id, is_only_admin_or_owner=False)


def test_unknown_verification_step_is_not_found(service):
    ticket = open_ticket(service)
    with pytest.raises(NotFoundError):
        service.complete_step(ticket.id, "officer_written_confirmation")  # nothing started
    service.start_owner_change(ticket.id)
    with pytest.raises(NotFoundError):
        service.complete_step(ticket.id, "a_phone_call")
    with pytest.raises(NotFoundError):
        service.start_owner_change("SUP-99999")
