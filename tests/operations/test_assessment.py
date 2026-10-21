from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aog_recovery.operations.assessment import (
    OptionCostRates,
    assess_candidate_impact,
    estimate_delay_minutes,
    estimate_option_cost,
)
from aog_recovery.operations.contracts import ImpactLevel, RecoveryCandidate, RecoveryOptionKind
from aog_recovery.operations.validation import ImpactThresholds, OperationalFlight

DEPARTURE = datetime(2026, 10, 21, 15, 30, tzinfo=UTC)
FLIGHT = OperationalFlight(
    flight_id="FX401",
    route="MEM-IND",
    origin_station="MEM",
    destination_station="IND",
    aircraft_type="A320",
    assigned_tail_id="FX123",
    departure_at=DEPARTURE,
    arrival_at=DEPARTURE + timedelta(hours=1),
)
THRESHOLDS = ImpactThresholds(
    medium_delay_minutes=30,
    high_delay_minutes=120,
    critical_delay_minutes=300,
)
REQUIREMENT_TO_TEST = {
    "ARD-OPS-003..005": (
        "test_repair_eta_and_impact_classification_are_deterministic",
        "test_cost_calculations_keep_currency_and_line_items",
        "test_unavailable_cost_component_is_not_substituted_with_zero",
    ),
}


def test_requirement_to_test_map_covers_cost_and_impact_requirements() -> None:
    assert all(test_names for test_names in REQUIREMENT_TO_TEST.values())


def test_repair_eta_and_impact_classification_are_deterministic() -> None:
    candidate = RecoveryCandidate(
        option_id="repair-late",
        kind=RecoveryOptionKind.REPAIR,
        description="Repair completes after departure",
        repair_eta=DEPARTURE + timedelta(minutes=90),
    )

    first = assess_candidate_impact(candidate, (FLIGHT,), THRESHOLDS)
    second = assess_candidate_impact(candidate, (FLIGHT,), THRESHOLDS)

    assert estimate_delay_minutes(candidate, (FLIGHT,)) == 90
    assert first == second
    assert first.delay_minutes == 90
    assert first.impact_level is ImpactLevel.MEDIUM


def test_cost_calculations_keep_currency_and_line_items() -> None:
    candidate = RecoveryCandidate(
        option_id="swap-fx207",
        kind=RecoveryOptionKind.SWAP,
        description="Swap with a short delay",
        substitute_tail_id="FX207",
        delay_minutes=15,
    )
    rates = OptionCostRates(
        currency="USD",
        delay_per_minute=Decimal("0.50"),
        swap_flat_cost=Decimal("120.00"),
        unprotected_package_exposure=Decimal("2.00"),
    )

    estimate = estimate_option_cost(candidate, 15, 3, rates)

    assert estimate.total == Decimal("133.50")
    assert estimate.currency == "USD"
    assert {item.description for item in estimate.line_items} == {
        "Aircraft swap",
        "Estimated delay",
        "Unprotected package exposure",
    }
    assert all(item.currency == "USD" for item in estimate.line_items)


def test_unavailable_cost_component_is_not_substituted_with_zero() -> None:
    candidate = RecoveryCandidate(
        option_id="delay-90",
        kind=RecoveryOptionKind.DELAY,
        description="Delay affected flight",
        delay_minutes=90,
    )
    rates = OptionCostRates(
        currency="USD",
        delay_per_minute=Decimal("1.25"),
        swap_flat_cost=None,
        unprotected_package_exposure=None,
    )

    estimate = estimate_option_cost(candidate, 90, 300, rates)

    assert estimate.total is None
    assert estimate.unavailable_reason is not None
    assert estimate.missing_evidence == ("unprotected-package-exposure-rate",)
    assert len(estimate.line_items) == 1
    assert estimate.line_items[0].amount == Decimal("112.50")
