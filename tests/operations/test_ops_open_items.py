import json
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.readiness import ReadinessEstimate, SourcingMethod
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import (
    CandidateOption,
    CapacityReservation,
    OperationsOutcome,
    OptionKind,
    ReroutePolicy,
)
from aog_recovery.operations.rules import find_replacement_flights
from aog_recovery.operations.synthetic import (
    T0,
    at,
    default_adapters,
    default_alternate_flights,
    default_case,
    default_schedule,
    delay_option,
    request_for,
)

CUTOFF = at(17, 30)
EVALUATED_DEFAULT = T0 + timedelta(minutes=10)


def reservation(
    flight: str, packages: int, reference: str = "ml-shipment-1"
) -> CapacityReservation:
    return CapacityReservation(
        flight_number=flight,
        packages=packages,
        reserved_by=AgentRole.MATERIALS_LOGISTICS,
        reference=reference,
    )


# --- need-by time on the case -------------------------------------------------------------------


def test_case_need_by_is_optional_and_must_be_timezone_aware() -> None:
    case = default_case()
    assert case.need_by is None
    with_need = case.model_copy(update={"need_by": at(18)})
    assert type(case).model_validate(with_need.model_dump()).need_by == at(18)
    with pytest.raises(ValidationError):
        type(case).model_validate({**case.model_dump(), "need_by": datetime(2026, 10, 21, 18)})


# --- reserved flight capacity (shared with Materials & Logistics) -------------------------------


def flights_with(reserved: dict[str, int] | None) -> dict[str, tuple[int, bool, str | None]]:
    found = find_replacement_flights(
        default_schedule().flights[:1],
        default_alternate_flights(),
        ReroutePolicy(),
        EVALUATED_DEFAULT,
        CUTOFF,
        reserved,
    )
    return {f.flight_number: (f.available_capacity, f.bookable, f.restriction) for f in found}


def test_reserved_capacity_reduces_what_is_available() -> None:
    assert flights_with(None)["FX505"] == (150, True, None)
    assert flights_with({"FX505": 100})["FX505"] == (50, True, None)


def test_fully_reserved_flight_is_not_usable_and_says_why() -> None:
    capacity, bookable, why = flights_with({"FX505": 150})["FX505"]
    assert (capacity, bookable) == (0, False)
    assert why == "capacity fully reserved by another recovery action"
    over = flights_with({"FX505": 999})["FX505"]
    assert over[0] == 0 and over[1] is False


def test_reservations_on_other_flights_do_not_matter() -> None:
    assert flights_with({"FX999": 50})["FX505"] == (150, True, None)


def test_reservations_flow_through_the_agent_and_are_recorded() -> None:
    request = request_for(delay_option(at(19))).model_copy(
        update={
            "reserved_capacity": (
                reservation("FX505", 100, "ml-1"),
                reservation("FX505", 50, "ml-2"),
            )
        }
    )
    outcome = OperationsAgent(default_adapters()).assess(request)
    assert outcome.assessment is not None
    [option] = outcome.assessment.recovery_options
    assert (option.package.own_flight_count, option.package.partner_flight_count) == (0, 500)
    assert option.package.unprotected_count == 700
    flight = next(f for f in outcome.assessment.available_flights if f.flight_number == "FX505")
    assert flight.restriction == "capacity fully reserved by another recovery action"
    assert any("FX505 (150)" in a for a in outcome.assessment.assumptions)


def test_reservation_contract_is_strict() -> None:
    data = reservation("FX505", 10).model_dump()
    for broken in ({**data, "packages": 0}, {**data, "extra": 1}, {**data, "reserved_by": "x"}):
        with pytest.raises(ValidationError):
            CapacityReservation.model_validate(broken)


def test_json_request_with_reservations_is_accepted() -> None:
    request = request_for(delay_option(at(19))).model_copy(
        update={"reserved_capacity": (reservation("FX505", 20),)}
    )
    payload = json.loads(request.model_dump_json())
    outcome = OperationsAgent(default_adapters()).assess_payload(payload)
    assert isinstance(outcome, OperationsOutcome)


# --- sourcing method pass-through (ARD-CTL-018) -------------------------------------------------


def test_sourcing_method_is_carried_and_shown_in_the_rationale() -> None:
    estimate = ReadinessEstimate.from_lead_time_hours(
        at(12), 3, AgentRole.MATERIALS_LOGISTICS, ("evidence-ml-9",)
    )
    candidate = CandidateOption.with_readiness(
        "OPT-P120",
        OptionKind.REPAIR_ALTERNATE,
        "Repair with P-120",
        estimate,
        SourcingMethod.EXPEDITE,
    )
    assert candidate.sourcing_method is SourcingMethod.EXPEDITE
    outcome = OperationsAgent(default_adapters()).assess(request_for(candidate))
    assert outcome.assessment is not None
    assert "Sourcing: expedite." in outcome.assessment.recovery_options[0].rationale


def test_sourcing_method_is_optional_and_validated() -> None:
    assert delay_option().sourcing_method is None
    outcome = OperationsAgent(default_adapters()).assess(request_for(delay_option()))
    assert outcome.assessment is not None
    assert "Sourcing:" not in outcome.assessment.recovery_options[0].rationale
    with pytest.raises(ValidationError):
        CandidateOption.model_validate(
            {**delay_option().model_dump(), "sourcing_method": "teleport"}
        )
