from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aog_recovery.operations.contracts import ImpactLevel, RecoveryCandidate, RecoveryOptionKind
from aog_recovery.operations.validation import (
    AircraftAssignment,
    ConstraintState,
    CrewStationConstraint,
    ImpactThresholds,
    OperationalFlight,
    OperationalSnapshot,
    RouteDisruption,
    SubstituteAircraft,
    validate_candidate,
)

DEPARTURE = datetime(2026, 10, 21, 15, 30, tzinfo=UTC)
ARRIVAL = DEPARTURE + timedelta(hours=1)
REQUIREMENT_TO_TEST = {
    "ARD-OPS-002": (
        "test_feasible_swap_is_deterministic",
        "test_assignment_overlap_blocks_candidate_with_resource_explanation",
        "test_missing_schedule_or_fleet_evidence_remains_unknown",
    ),
    "ARD-OPS-008": (
        "test_assignment_overlap_blocks_candidate_with_resource_explanation",
        "test_unavailable_crew_constraint_blocks_candidate",
    ),
    "ARD-OPS-003": ("test_disruption_thresholds_classify_impact_deterministically",),
}


def flight() -> OperationalFlight:
    return OperationalFlight(
        flight_id="FX401",
        route="MEM-IND",
        origin_station="MEM",
        destination_station="IND",
        aircraft_type="A320",
        assigned_tail_id="FX123",
        departure_at=DEPARTURE,
        arrival_at=ARRIVAL,
    )


def candidate() -> RecoveryCandidate:
    return RecoveryCandidate(
        option_id="swap-fx207",
        kind=RecoveryOptionKind.SWAP,
        description="Evaluate spare tail FX207",
        substitute_tail_id="FX207",
    )


def snapshot(
    *,
    assignments: tuple[AircraftAssignment, ...] | None = None,
    substitute_aircraft: tuple[SubstituteAircraft, ...] | None = None,
    crew_constraints: tuple[CrewStationConstraint, ...] | None = None,
    disruptions: tuple[RouteDisruption, ...] = (),
    missing_evidence: tuple[str, ...] = (),
) -> OperationalSnapshot:
    return OperationalSnapshot(
        flights=(flight(),),
        assignments=assignments
        if assignments is not None
        else (
            AircraftAssignment(
                tail_id="FX123",
                flight_id="FX401",
                start_at=DEPARTURE,
                end_at=ARRIVAL,
            ),
        ),
        substitute_aircraft=substitute_aircraft
        if substitute_aircraft is not None
        else (
            SubstituteAircraft(
                tail_id="FX207",
                aircraft_type="A320",
                station_id="MEM",
                available_from=DEPARTURE - timedelta(hours=1),
                available_until=ARRIVAL + timedelta(hours=1),
            ),
        ),
        crew_station_constraints=crew_constraints
        if crew_constraints is not None
        else (
            CrewStationConstraint(
                flight_id="FX401",
                resource_id="crew-MEM-401",
                state=ConstraintState.AVAILABLE,
            ),
        ),
        disruptions=disruptions,
        missing_evidence=missing_evidence,
        impact_thresholds=ImpactThresholds(
            medium_delay_minutes=30,
            high_delay_minutes=120,
            critical_delay_minutes=300,
        ),
    )


def test_requirement_to_test_map_covers_validation_requirements() -> None:
    assert set(REQUIREMENT_TO_TEST) == {"ARD-OPS-002", "ARD-OPS-008", "ARD-OPS-003"}
    assert all(test_names for test_names in REQUIREMENT_TO_TEST.values())


def test_feasible_swap_is_deterministic() -> None:
    operational_snapshot = snapshot()

    first = validate_candidate(candidate(), ("FX401",), operational_snapshot)
    second = validate_candidate(candidate(), ("FX401",), operational_snapshot)

    assert first == second
    assert first.feasible is True
    assert first.impact_level is ImpactLevel.LOW
    assert first.affected_routes == ("MEM-IND",)
    assert first.findings == ()


def test_assignment_overlap_blocks_candidate_with_resource_explanation() -> None:
    overlap_start = DEPARTURE + timedelta(minutes=30)
    operational_snapshot = snapshot(
        assignments=(
            AircraftAssignment(
                tail_id="FX123",
                flight_id="FX401",
                start_at=DEPARTURE,
                end_at=ARRIVAL,
            ),
            AircraftAssignment(
                tail_id="FX207",
                flight_id="FX812",
                start_at=overlap_start,
                end_at=ARRIVAL + timedelta(hours=1),
            ),
        )
    )

    result = validate_candidate(candidate(), ("FX401",), operational_snapshot)

    assert result.feasible is False
    conflict = next(
        finding for finding in result.findings if finding.code == "substitute_assignment_conflict"
    )
    assert conflict.affected_resource == "FX207"
    assert "FX812" in conflict.description


def test_unavailable_crew_constraint_blocks_candidate() -> None:
    operational_snapshot = snapshot(
        crew_constraints=(
            CrewStationConstraint(
                flight_id="FX401",
                resource_id="crew-MEM-401",
                state=ConstraintState.UNAVAILABLE,
                reason="Crew duty-time limit would be exceeded.",
            ),
        )
    )

    result = validate_candidate(candidate(), ("FX401",), operational_snapshot)

    assert result.feasible is False
    assert any(
        finding.code == "crew_or_station_unavailable"
        and finding.affected_resource == "crew-MEM-401"
        for finding in result.findings
    )


def test_disruption_thresholds_classify_impact_deterministically() -> None:
    disruption = RouteDisruption(
        disruption_id="disruption-MEM-IND",
        route="MEM-IND",
        starts_at=DEPARTURE - timedelta(minutes=15),
        ends_at=ARRIVAL + timedelta(minutes=15),
        delay_minutes=180,
    )

    result = validate_candidate(candidate(), ("FX401",), snapshot(disruptions=(disruption,)))

    assert result.impact_level is ImpactLevel.HIGH


def test_missing_schedule_or_fleet_evidence_remains_unknown() -> None:
    missing_flight_snapshot = OperationalSnapshot(
        flights=(),
        assignments=(),
        substitute_aircraft=(),
        crew_station_constraints=(),
        disruptions=(),
        missing_evidence=(),
        impact_thresholds=ImpactThresholds(
            medium_delay_minutes=30,
            high_delay_minutes=120,
            critical_delay_minutes=300,
        ),
    )
    missing_flight_result = validate_candidate(
        candidate(),
        ("FX401",),
        missing_flight_snapshot,
    )
    missing_fleet_snapshot = snapshot(
        substitute_aircraft=(),
        missing_evidence=("fleet-availability",),
    )
    missing_fleet_result = validate_candidate(candidate(), ("FX401",), missing_fleet_snapshot)

    assert missing_flight_result.feasible is None
    assert "flight-schedule:FX401" in missing_flight_result.missing_evidence
    assert missing_fleet_result.feasible is None
    assert "fleet-availability" in missing_fleet_result.missing_evidence


def test_threshold_and_flight_contracts_reject_invalid_data() -> None:
    with pytest.raises(ValidationError, match="strictly increasing"):
        ImpactThresholds(
            medium_delay_minutes=120,
            high_delay_minutes=120,
            critical_delay_minutes=300,
        )

    with pytest.raises(ValidationError, match="arrival_at must be after"):
        OperationalFlight(
            flight_id="FX401",
            route="MEM-IND",
            origin_station="MEM",
            destination_station="IND",
            aircraft_type="A320",
            assigned_tail_id="FX123",
            departure_at=ARRIVAL,
            arrival_at=DEPARTURE,
        )
