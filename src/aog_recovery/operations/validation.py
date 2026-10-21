from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from aog_recovery.contracts.base import ContractModel
from aog_recovery.operations.contracts import (
    ImpactLevel,
    RecoveryCandidate,
    RecoveryOptionKind,
)

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConstraintState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class OperationalFlight(ContractModel):
    flight_id: NonEmptyString
    route: NonEmptyString
    origin_station: NonEmptyString
    destination_station: NonEmptyString
    aircraft_type: NonEmptyString
    assigned_tail_id: NonEmptyString
    departure_at: AwareDatetime
    arrival_at: AwareDatetime

    @model_validator(mode="after")
    def require_positive_flight_duration(self) -> OperationalFlight:
        if self.arrival_at <= self.departure_at:
            raise ValueError("arrival_at must be after departure_at")
        return self


class AircraftAssignment(ContractModel):
    tail_id: NonEmptyString
    flight_id: NonEmptyString
    start_at: AwareDatetime
    end_at: AwareDatetime

    @model_validator(mode="after")
    def require_positive_assignment_duration(self) -> AircraftAssignment:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class SubstituteAircraft(ContractModel):
    tail_id: NonEmptyString
    aircraft_type: NonEmptyString
    station_id: NonEmptyString
    available_from: AwareDatetime
    available_until: AwareDatetime

    @model_validator(mode="after")
    def require_positive_availability_window(self) -> SubstituteAircraft:
        if self.available_until <= self.available_from:
            raise ValueError("available_until must be after available_from")
        return self


class CrewStationConstraint(ContractModel):
    flight_id: NonEmptyString
    resource_id: NonEmptyString
    state: ConstraintState
    reason: NonEmptyString | None = None

    @model_validator(mode="after")
    def explain_unavailable_constraint(self) -> CrewStationConstraint:
        if self.state is ConstraintState.UNAVAILABLE and self.reason is None:
            raise ValueError("unavailable crew or station constraints require a reason")
        return self


class RouteDisruption(ContractModel):
    disruption_id: NonEmptyString
    route: NonEmptyString
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    delay_minutes: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def require_positive_disruption_window(self) -> RouteDisruption:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ImpactThresholds(ContractModel):
    medium_delay_minutes: Annotated[int, Field(gt=0)]
    high_delay_minutes: Annotated[int, Field(gt=0)]
    critical_delay_minutes: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def require_increasing_thresholds(self) -> ImpactThresholds:
        if not (self.medium_delay_minutes < self.high_delay_minutes < self.critical_delay_minutes):
            raise ValueError("impact delay thresholds must be strictly increasing")
        return self

    def classify(self, delay_minutes: int) -> ImpactLevel:
        if delay_minutes >= self.critical_delay_minutes:
            return ImpactLevel.CRITICAL
        if delay_minutes >= self.high_delay_minutes:
            return ImpactLevel.HIGH
        if delay_minutes >= self.medium_delay_minutes:
            return ImpactLevel.MEDIUM
        return ImpactLevel.LOW


class OperationalSnapshot(ContractModel):
    flights: tuple[OperationalFlight, ...]
    assignments: tuple[AircraftAssignment, ...]
    substitute_aircraft: tuple[SubstituteAircraft, ...]
    crew_station_constraints: tuple[CrewStationConstraint, ...]
    disruptions: tuple[RouteDisruption, ...]
    missing_evidence: tuple[NonEmptyString, ...]
    impact_thresholds: ImpactThresholds

    @model_validator(mode="after")
    def require_unique_snapshot_ids(self) -> OperationalSnapshot:
        for field_name, values in (
            ("flight_id", tuple(flight.flight_id for flight in self.flights)),
            ("tail_id", tuple(aircraft.tail_id for aircraft in self.substitute_aircraft)),
            (
                "disruption_id",
                tuple(disruption.disruption_id for disruption in self.disruptions),
            ),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"snapshot {field_name} values must be unique")
        return self


class ValidationFinding(ContractModel):
    code: NonEmptyString
    affected_resource: NonEmptyString
    description: NonEmptyString
    blocks_feasibility: bool


class CandidateValidation(ContractModel):
    option_id: NonEmptyString
    feasible: bool | None
    impact_level: ImpactLevel
    affected_flight_ids: tuple[NonEmptyString, ...]
    affected_routes: tuple[NonEmptyString, ...]
    findings: tuple[ValidationFinding, ...]
    missing_evidence: tuple[NonEmptyString, ...]


def _overlaps(
    first_start: datetime,
    first_end: datetime,
    second_start: datetime,
    second_end: datetime,
) -> bool:
    return first_start < second_end and second_start < first_end


def validate_candidate(
    candidate: RecoveryCandidate,
    affected_flight_ids: tuple[str, ...],
    snapshot: OperationalSnapshot,
) -> CandidateValidation:
    flights_by_id = {flight.flight_id: flight for flight in snapshot.flights}
    affected_flights = tuple(
        flights_by_id[flight_id] for flight_id in affected_flight_ids if flight_id in flights_by_id
    )
    findings: list[ValidationFinding] = []
    missing_evidence = list(snapshot.missing_evidence)

    for flight_id in affected_flight_ids:
        if flight_id not in flights_by_id:
            missing_evidence.append(f"flight-schedule:{flight_id}")
            findings.append(
                ValidationFinding(
                    code="missing_flight_schedule",
                    affected_resource=flight_id,
                    description=f"Schedule evidence for flight {flight_id} is unavailable.",
                    blocks_feasibility=False,
                )
            )

    affected_ids = set(affected_flight_ids)
    for flight in affected_flights:
        assignments = tuple(
            assignment
            for assignment in snapshot.assignments
            if assignment.flight_id == flight.flight_id
            and assignment.tail_id == flight.assigned_tail_id
        )
        if not assignments:
            missing_evidence.append(f"aircraft-assignment:{flight.flight_id}")
            findings.append(
                ValidationFinding(
                    code="missing_aircraft_assignment",
                    affected_resource=flight.assigned_tail_id,
                    description=(
                        f"Assignment evidence for flight {flight.flight_id} "
                        f"and tail {flight.assigned_tail_id} is unavailable."
                    ),
                    blocks_feasibility=False,
                )
            )
        for assignment in assignments:
            for other in snapshot.assignments:
                if (
                    other.tail_id == assignment.tail_id
                    and other.flight_id != assignment.flight_id
                    and other.flight_id not in affected_ids
                    and _overlaps(
                        assignment.start_at,
                        assignment.end_at,
                        other.start_at,
                        other.end_at,
                    )
                ):
                    findings.append(
                        ValidationFinding(
                            code="aircraft_assignment_overlap",
                            affected_resource=assignment.tail_id,
                            description=(
                                f"Tail {assignment.tail_id} has overlapping assignments "
                                f"for flights {assignment.flight_id} and {other.flight_id}."
                            ),
                            blocks_feasibility=True,
                        )
                    )

        for constraint in snapshot.crew_station_constraints:
            if constraint.flight_id != flight.flight_id:
                continue
            if constraint.state is ConstraintState.UNAVAILABLE:
                findings.append(
                    ValidationFinding(
                        code="crew_or_station_unavailable",
                        affected_resource=constraint.resource_id,
                        description=constraint.reason
                        or f"Resource {constraint.resource_id} is unavailable.",
                        blocks_feasibility=True,
                    )
                )
            elif constraint.state is ConstraintState.UNKNOWN:
                missing_evidence.append(f"crew-station:{constraint.resource_id}")
                findings.append(
                    ValidationFinding(
                        code="crew_or_station_unknown",
                        affected_resource=constraint.resource_id,
                        description=f"Availability of {constraint.resource_id} is unknown.",
                        blocks_feasibility=False,
                    )
                )

    if candidate.kind is RecoveryOptionKind.SWAP and affected_flights:
        substitute = next(
            (
                aircraft
                for aircraft in snapshot.substitute_aircraft
                if aircraft.tail_id == candidate.substitute_tail_id
            ),
            None,
        )
        if substitute is None:
            if "fleet-availability" in snapshot.missing_evidence:
                missing_evidence.append("fleet-availability")
                findings.append(
                    ValidationFinding(
                        code="fleet_availability_unknown",
                        affected_resource=candidate.substitute_tail_id or "unknown-tail",
                        description="Substitute aircraft availability could not be established.",
                        blocks_feasibility=False,
                    )
                )
            else:
                findings.append(
                    ValidationFinding(
                        code="substitute_aircraft_unavailable",
                        affected_resource=candidate.substitute_tail_id or "unknown-tail",
                        description="The requested substitute aircraft is not available.",
                        blocks_feasibility=True,
                    )
                )
        else:
            if any(flight.aircraft_type != substitute.aircraft_type for flight in affected_flights):
                findings.append(
                    ValidationFinding(
                        code="aircraft_type_mismatch",
                        affected_resource=substitute.tail_id,
                        description=(
                            f"Substitute tail {substitute.tail_id} is not compatible "
                            "with every affected flight."
                        ),
                        blocks_feasibility=True,
                    )
                )
            first_flight = affected_flights[0]
            if substitute.station_id != first_flight.origin_station:
                findings.append(
                    ValidationFinding(
                        code="substitute_station_mismatch",
                        affected_resource=substitute.station_id,
                        description=(
                            f"Substitute tail {substitute.tail_id} is at "
                            f"{substitute.station_id}, not {first_flight.origin_station}."
                        ),
                        blocks_feasibility=True,
                    )
                )
            for flight in affected_flights:
                if (
                    substitute.available_from > flight.departure_at
                    or substitute.available_until < flight.arrival_at
                ):
                    findings.append(
                        ValidationFinding(
                            code="substitute_outside_availability_window",
                            affected_resource=substitute.tail_id,
                            description=(
                                f"Substitute tail {substitute.tail_id} is not available "
                                f"for flight {flight.flight_id}'s full operating window."
                            ),
                            blocks_feasibility=True,
                        )
                    )
                for assignment in snapshot.assignments:
                    if (
                        assignment.tail_id == substitute.tail_id
                        and assignment.flight_id not in affected_ids
                        and _overlaps(
                            flight.departure_at,
                            flight.arrival_at,
                            assignment.start_at,
                            assignment.end_at,
                        )
                    ):
                        findings.append(
                            ValidationFinding(
                                code="substitute_assignment_conflict",
                                affected_resource=substitute.tail_id,
                                description=(
                                    f"Tail {substitute.tail_id} is assigned to flight "
                                    f"{assignment.flight_id} during {flight.flight_id}."
                                ),
                                blocks_feasibility=True,
                            )
                        )

    route_delays = tuple(
        disruption.delay_minutes
        for disruption in snapshot.disruptions
        if any(
            disruption.route == flight.route
            and _overlaps(
                disruption.starts_at,
                disruption.ends_at,
                flight.departure_at,
                flight.arrival_at,
            )
            for flight in affected_flights
        )
    )
    impact_level = snapshot.impact_thresholds.classify(max(route_delays, default=0))
    relevant_missing = {
        "flight-schedule",
        "route-schedule",
        "aircraft-assignment",
        "fleet-availability",
        "crew-station",
    }
    unique_missing = tuple(
        sorted(
            {
                item
                for item in missing_evidence
                if item in relevant_missing
                or item.startswith("flight-schedule:")
                or item.startswith("aircraft-assignment:")
                or item.startswith("crew-station:")
            }
        )
    )

    if any(finding.blocks_feasibility for finding in findings):
        feasible: bool | None = False
    elif unique_missing:
        feasible = None
    else:
        feasible = True

    return CandidateValidation(
        option_id=candidate.option_id,
        feasible=feasible,
        impact_level=impact_level,
        affected_flight_ids=tuple(flight.flight_id for flight in affected_flights),
        affected_routes=tuple(sorted({flight.route for flight in affected_flights})),
        findings=tuple(findings),
        missing_evidence=unique_missing,
    )
