"""Deterministic Operations rules (ARD-OPS-002/003/008/009, ARD-CTL-019, ARD-NFR-003).

Pure functions of validated models and settings. Names follow the proposal's tool names so a
later MCP wrapper can expose them unchanged (MCP is deferred, ARD-TEC-006).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aog_recovery.operations.models import (
    IMPACT_ORDER,
    AircraftRecord,
    AircraftStatus,
    AllocationPath,
    AlternateFlightData,
    CandidateOption,
    CarrierType,
    ConflictCode,
    CostBreakdown,
    CrewCoverage,
    EtaBasis,
    FleetAvailabilityData,
    FlightRecord,
    FlightScheduleData,
    ImpactLevel,
    OperationsRequest,
    OptionKind,
    PackageAllocation,
    PackageGroup,
    PackageLoadData,
    PackageOutcome,
    PackageServiceLevel,
    RecoveryOptionAssessment,
    ReplacementFlight,
    ReroutePolicy,
    RouteConflict,
    Viability,
)
from aog_recovery.operations.settings import OperationsSettings


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def _hhmm(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%H:%MZ")


# --- validate_flight_schedule ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScheduleValidation:
    flights: tuple[FlightRecord, ...]
    missing_flight_numbers: tuple[str, ...]
    assignment_mismatches: tuple[str, ...]


def validate_flight_schedule(
    request: OperationsRequest, data: FlightScheduleData
) -> ScheduleValidation:
    by_number = {flight.flight_number: flight for flight in data.flights}
    found = tuple(
        by_number[number] for number in request.affected_flight_numbers if number in by_number
    )
    missing = tuple(number for number in request.affected_flight_numbers if number not in by_number)
    mismatches = tuple(
        flight.flight_number
        for flight in found
        if flight.assigned_aircraft_id != request.case.aircraft_id
    )
    return ScheduleValidation(
        flights=found, missing_flight_numbers=missing, assignment_mismatches=mismatches
    )


# --- timing and conflicts ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FlightTiming:
    flight_number: str
    feasible_departure: datetime
    delay_minutes: int


def compute_timings(
    flights: tuple[FlightRecord, ...], ready_at: datetime
) -> tuple[FlightTiming, ...]:
    timings: list[FlightTiming] = []
    for flight in flights:
        feasible = max(flight.scheduled_departure, ready_at)
        if flight.crew_coverage is CrewCoverage.DELAYED and flight.crew_available_from:
            feasible = max(feasible, flight.crew_available_from)
        timings.append(
            FlightTiming(
                flight_number=flight.flight_number,
                feasible_departure=feasible,
                delay_minutes=max(0, _minutes(feasible - flight.scheduled_departure)),
            )
        )
    return tuple(timings)


def _conflict(
    option_id: str, code: ConflictCode, resources: tuple[str, ...], description: str
) -> RouteConflict:
    return RouteConflict(
        conflict_id=f"conflict-{option_id}-{code.value}-{'+'.join(resources)}",
        code=code,
        option_id=option_id,
        resource_ids=resources,
        description=description,
    )


def _crew_gap_conflicts(option_id: str, flights: tuple[FlightRecord, ...]) -> list[RouteConflict]:
    return [
        _conflict(
            option_id,
            ConflictCode.CREW_COVERAGE_GAP,
            (flight.flight_number, f"crew:{flight.flight_number}"),
            f"No crew coverage for {flight.flight_number}; the flight cannot operate on any "
            "recovery path until crew is assigned",
        )
        for flight in flights
        if flight.crew_coverage is CrewCoverage.GAP
    ]


def _double_booking_conflicts(
    option_id: str,
    aircraft_id: str,
    flights: tuple[FlightRecord, ...],
    timings: tuple[FlightTiming, ...],
    all_flights: tuple[FlightRecord, ...],
) -> list[RouteConflict]:
    affected = {flight.flight_number for flight in flights}
    windows = [
        (
            timing.feasible_departure,
            timing.feasible_departure + (flight.scheduled_arrival - flight.scheduled_departure),
        )
        for flight, timing in zip(flights, timings, strict=True)
    ]
    clashing = sorted(
        other.flight_number
        for other in all_flights
        if other.assigned_aircraft_id == aircraft_id
        and other.flight_number not in affected
        and any(
            other.scheduled_departure < end and other.scheduled_arrival > start
            for start, end in windows
        )
    )
    if not clashing:
        return []
    return [
        _conflict(
            option_id,
            ConflictCode.AIRCRAFT_DOUBLE_BOOKED,
            (aircraft_id, *clashing),
            f"Aircraft {aircraft_id} is already assigned to {', '.join(clashing)} during the "
            "recovery window",
        )
    ]


def _time_estimate_conflicts(
    option_id: str,
    eta: datetime,
    flights: tuple[FlightRecord, ...],
    settings: OperationsSettings,
) -> list[RouteConflict]:
    ready = eta + timedelta(minutes=settings.turnaround_buffer_minutes)
    conflicts: list[RouteConflict] = []
    for flight in flights:
        if flight.crew_coverage is not CrewCoverage.DELAYED or flight.crew_available_from is None:
            continue
        gap = _minutes(flight.crew_available_from - ready)
        if gap > settings.time_conflict_threshold_minutes:
            conflicts.append(
                _conflict(
                    option_id,
                    ConflictCode.TIME_ESTIMATE_CONFLICT,
                    (flight.flight_number, f"crew:{flight.flight_number}"),
                    f"Maintenance/Materials ETA {_hhmm(eta)} implies departure readiness "
                    f"{_hhmm(ready)}, but crew for {flight.flight_number} is available only at "
                    f"{_hhmm(flight.crew_available_from)} ({gap} minutes later)",
                )
            )
    return conflicts


def detect_route_conflicts(
    option_id: str,
    flights: tuple[FlightRecord, ...],
    timings: tuple[FlightTiming, ...],
    all_flights: tuple[FlightRecord, ...],
    substitute: AircraftRecord | None,
    eta: datetime | None,
    settings: OperationsSettings,
) -> tuple[RouteConflict, ...]:
    conflicts = _crew_gap_conflicts(option_id, flights)
    if substitute is not None:
        conflicts += _double_booking_conflicts(
            option_id, substitute.aircraft_id, flights, timings, all_flights
        )
    if eta is not None:
        conflicts += _time_estimate_conflicts(option_id, eta, flights, settings)
    return tuple(conflicts)


# --- check_fleet_availability ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SubstituteCandidate:
    aircraft: AircraftRecord
    ready_at: datetime


def check_fleet_availability(
    fleet: FleetAvailabilityData,
    flights: tuple[FlightRecord, ...],
    excluded_aircraft_id: str,
    settings: OperationsSettings,
) -> tuple[SubstituteCandidate, ...]:
    required_types = {flight.required_aircraft_type for flight in flights}
    if len(required_types) != 1:
        return ()
    required_type = next(iter(required_types))
    earliest_departure = min(flight.scheduled_departure for flight in flights)
    latest_ready = earliest_departure + timedelta(minutes=settings.swap_window_minutes)

    candidates = [
        SubstituteCandidate(
            aircraft=aircraft,
            ready_at=aircraft.available_from
            + timedelta(minutes=aircraft.positioning_minutes + settings.turnaround_buffer_minutes),
        )
        for aircraft in fleet.aircraft
        if aircraft.status is AircraftStatus.SERVICEABLE
        and aircraft.aircraft_type == required_type
        and aircraft.aircraft_id != excluded_aircraft_id
        and aircraft.positioning_minutes <= settings.swap_positioning_limit_minutes
    ]
    eligible = [candidate for candidate in candidates if candidate.ready_at <= latest_ready]
    return tuple(
        sorted(
            eligible,
            key=lambda c: (c.ready_at, -c.aircraft.package_capacity, c.aircraft.aircraft_id),
        )
    )


# --- apply_disruption_thresholds ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ThresholdResult:
    level: ImpactLevel
    rule: str


def apply_disruption_thresholds(
    delay_minutes: int,
    service_critical: bool,
    unprotected_time_critical: bool,
    settings: OperationsSettings,
) -> ThresholdResult:
    if delay_minutes >= settings.delay_critical_minutes:
        level = ImpactLevel.CRITICAL
    elif delay_minutes >= settings.delay_high_minutes:
        level = ImpactLevel.HIGH
    elif delay_minutes >= settings.delay_medium_minutes:
        level = ImpactLevel.MEDIUM
    else:
        level = ImpactLevel.LOW
    rule = f"delay_threshold_{level.value}"

    uplift_reasons = [
        reason
        for applies, reason in (
            (service_critical, "service_critical_flight"),
            (unprotected_time_critical, "unprotected_time_critical_packages"),
        )
        if applies
    ]
    if uplift_reasons:
        index = min(IMPACT_ORDER.index(level) + 1, len(IMPACT_ORDER) - 1)
        level = IMPACT_ORDER[index]
        rule += "+uplift:" + "+".join(uplift_reasons)
    return ThresholdResult(level=level, rule=rule)


# --- find_replacement_flights ------------------------------------------------------------------


def _flight_order(flight: ReplacementFlight, prefer_own: bool) -> tuple[int, datetime, int, str]:
    own_first = prefer_own and flight.carrier_type is not CarrierType.OWN
    return (int(own_first), flight.departure_at, flight.cost_per_package_usd, flight.flight_number)


def _restriction(
    flight_carrier: CarrierType,
    cost: int,
    capacity: int,
    departure_at: datetime,
    booking_deadline: datetime | None,
    policy: ReroutePolicy,
    evaluated_at: datetime,
    latest_cutoff: datetime | None,
) -> str | None:
    partner = flight_carrier is CarrierType.PARTNER
    max_cost = policy.max_partner_cost_per_package_usd
    if partner and not policy.allow_partner_flights:
        return "partner flights are not permitted by the reroute policy"
    if partner and max_cost is not None and cost > max_cost:
        return "partner cost per package exceeds the policy limit"
    if departure_at < evaluated_at:
        return "already departed at evaluation time"
    if booking_deadline is not None and booking_deadline < evaluated_at:
        return "booking deadline has passed"
    if capacity == 0:
        return "no spare package capacity"
    if latest_cutoff is not None and departure_at > latest_cutoff:
        return "departs after the latest package cut-off"
    return None


def find_replacement_flights(
    flights: tuple[FlightRecord, ...],
    data: AlternateFlightData,
    policy: ReroutePolicy,
    evaluated_at: datetime,
    latest_cutoff: datetime | None,
) -> tuple[ReplacementFlight, ...]:
    """Own-network and partner flights on the affected routes; bookability is never assumed."""
    routes = {(flight.origin, flight.destination) for flight in flights}
    affected = {flight.flight_number for flight in flights}
    found: list[ReplacementFlight] = []
    for alt in data.flights:
        if (alt.origin, alt.destination) not in routes or alt.flight_number in affected:
            continue
        restriction = _restriction(
            alt.carrier_type,
            alt.cost_per_package_usd,
            alt.available_capacity,
            alt.departure_at,
            alt.booking_deadline,
            policy,
            evaluated_at,
            latest_cutoff,
        )
        found.append(
            ReplacementFlight(
                flight_number=alt.flight_number,
                carrier_type=alt.carrier_type,
                carrier_name=alt.carrier_name,
                origin=alt.origin,
                destination=alt.destination,
                departure_at=alt.departure_at,
                arrival_at=alt.arrival_at,
                available_capacity=alt.available_capacity,
                cost_per_package_usd=alt.cost_per_package_usd,
                accepted_service_levels=alt.accepted_service_levels,
                booking_deadline=alt.booking_deadline,
                bookable=restriction is None,
                restriction=restriction,
            )
        )
    return tuple(sorted(found, key=lambda f: _flight_order(f, policy.prefer_own_network)))


# --- check_load_redistribution -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PrimaryPath:
    """Where packages go first: held on the original aircraft, or moved to a substitute."""

    substitute_id: str | None
    substitute_capacity: int


@dataclass(frozen=True, slots=True)
class RedistributionPlan:
    allocations: tuple[PackageAllocation, ...]
    held_in_place: int
    redistributed: int
    own_flight: int
    partner_flight: int
    reroute_cost_usd: int
    unprotected: int
    unprotected_time_critical: int
    unprotected_priority_rate: int
    unprotected_standard_rate: int
    capacity_constraints: tuple[str, ...]
    commitments_at_risk: tuple[str, ...]


_SERVICE_RANK = {PackageServiceLevel.PRIORITY: 0, PackageServiceLevel.STANDARD: 1}


def _group_order(group: PackageGroup) -> tuple[int, int, datetime, str]:
    return (
        0 if group.time_critical else 1,
        _SERVICE_RANK[group.service_level],
        group.cutoff_at,
        group.group_id,
    )


def check_load_redistribution(
    groups: tuple[PackageGroup, ...],
    replacement_flights: tuple[ReplacementFlight, ...],
    primary: PrimaryPath,
    feasible_departures: Mapping[str, datetime],
    routes: Mapping[str, tuple[str, str]],
    prefer_own: bool = True,
) -> RedistributionPlan:
    usable = sorted(
        (f for f in replacement_flights if f.bookable),
        key=lambda f: _flight_order(f, prefer_own),
    )
    remaining_capacity = {f.flight_number: f.available_capacity for f in usable}
    substitute_remaining = primary.substitute_capacity

    allocations: list[PackageAllocation] = []
    commitments: list[str] = []
    held = redistributed = own = partner = reroute_cost = 0
    unprotected = unprotected_tc = priority_rate = standard_rate = 0

    for group in sorted(groups, key=_group_order):
        remaining = group.count
        departure = feasible_departures.get(group.flight_number)
        meets_cutoff = departure is not None and departure <= group.cutoff_at

        if primary.substitute_id is None:
            if meets_cutoff:
                allocations.append(
                    PackageAllocation(
                        group_id=group.group_id,
                        path=AllocationPath.HELD,
                        target_id=f"hold:{group.flight_number}",
                        carrier_name=None,
                        departure_at=departure,
                        count=remaining,
                        cost_usd=0,
                    )
                )
                held += remaining
                remaining = 0
        elif meets_cutoff and substitute_remaining > 0:
            take = min(remaining, substitute_remaining)
            allocations.append(
                PackageAllocation(
                    group_id=group.group_id,
                    path=AllocationPath.SUBSTITUTE_AIRCRAFT,
                    target_id=primary.substitute_id,
                    carrier_name=None,
                    departure_at=departure,
                    count=take,
                    cost_usd=0,
                )
            )
            substitute_remaining -= take
            redistributed += take
            remaining -= take

        route = routes.get(group.flight_number)
        for flight in usable:
            if remaining == 0:
                break
            available = remaining_capacity[flight.flight_number]
            if (
                available > 0
                and route == (flight.origin, flight.destination)
                and flight.departure_at <= group.cutoff_at
                and group.service_level in flight.accepted_service_levels
            ):
                take = min(remaining, available)
                cost = take * flight.cost_per_package_usd
                is_partner = flight.carrier_type is CarrierType.PARTNER
                allocations.append(
                    PackageAllocation(
                        group_id=group.group_id,
                        path=AllocationPath.PARTNER_FLIGHT
                        if is_partner
                        else AllocationPath.OWN_FLIGHT,
                        target_id=flight.flight_number,
                        carrier_name=flight.carrier_name,
                        departure_at=flight.departure_at,
                        count=take,
                        cost_usd=cost,
                    )
                )
                remaining_capacity[flight.flight_number] = available - take
                redistributed += take
                reroute_cost += cost
                if is_partner:
                    partner += take
                else:
                    own += take
                remaining -= take

        if remaining:
            unprotected += remaining
            if group.time_critical:
                unprotected_tc += remaining
            if group.time_critical or group.service_level is PackageServiceLevel.PRIORITY:
                priority_rate += remaining
            else:
                standard_rate += remaining
            commitments.append(
                f"{group.flight_number} {group.service_level.value} packages: {remaining} "
                f"unprotected against the {_hhmm(group.cutoff_at)} cut-off"
            )

    constraints: list[str] = []
    if primary.substitute_id is not None and substitute_remaining == 0:
        constraints.append(
            f"substitute {primary.substitute_id} capacity {primary.substitute_capacity} fully used"
        )
    constraints.extend(
        f"{f.flight_number} ({f.carrier_name}) capacity fully used"
        for f in usable
        if remaining_capacity[f.flight_number] == 0 and f.available_capacity > 0
    )

    return RedistributionPlan(
        allocations=tuple(allocations),
        held_in_place=held,
        redistributed=redistributed,
        own_flight=own,
        partner_flight=partner,
        reroute_cost_usd=reroute_cost,
        unprotected=unprotected,
        unprotected_time_critical=unprotected_tc,
        unprotected_priority_rate=priority_rate,
        unprotected_standard_rate=standard_rate,
        capacity_constraints=tuple(constraints),
        commitments_at_risk=tuple(commitments),
    )


def compute_cost(
    total_delay_minutes: int,
    swap: bool,
    plan: RedistributionPlan | None,
    settings: OperationsSettings,
    reroute_assessed: bool = True,
) -> CostBreakdown:
    delay = total_delay_minutes * settings.delay_cost_per_minute_usd
    swap_cost = settings.swap_cost_usd if swap else 0
    rerouting = 0 if plan is None else plan.reroute_cost_usd
    packages = (
        0
        if plan is None
        else plan.unprotected_priority_rate * settings.unprotected_priority_package_cost_usd
        + plan.unprotected_standard_rate * settings.unprotected_standard_package_cost_usd
    )
    return CostBreakdown(
        delay_usd=delay,
        swap_usd=swap_cost,
        rerouting_usd=rerouting,
        unprotected_packages_usd=packages,
        total_usd=delay + swap_cost + rerouting + packages,
        complete=plan is not None and reroute_assessed,
    )


# --- candidate evaluation ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    request: OperationsRequest
    flights: tuple[FlightRecord, ...]
    all_flights: tuple[FlightRecord, ...]
    fleet: FleetAvailabilityData | None
    packages: PackageLoadData | None
    # None means alternate-flight data was unavailable (not that no flights exist).
    replacement_flights: tuple[ReplacementFlight, ...] | None = None


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    assessment: RecoveryOptionAssessment
    conflicts: tuple[RouteConflict, ...]
    used_estimated_eta: bool


def _unassessed_packages(reason: str) -> PackageOutcome:
    return PackageOutcome(
        assessed=False,
        reroute_assessed=False,
        affected_package_count=None,
        time_critical_package_count=None,
        held_in_place_count=None,
        redistributed_count=None,
        own_flight_count=None,
        partner_flight_count=None,
        unprotected_count=None,
        unprotected_time_critical_count=None,
        allocations=(),
        capacity_constraints=(reason,),
        service_commitments_at_risk=(),
    )


def _package_outcome(
    plan: RedistributionPlan, groups: tuple[PackageGroup, ...], reroute_assessed: bool
) -> PackageOutcome:
    constraints = plan.capacity_constraints
    if not reroute_assessed:
        constraints = (
            *constraints,
            "alternate flight data unavailable: unprotected counts are upper bounds",
        )
    return PackageOutcome(
        assessed=True,
        reroute_assessed=reroute_assessed,
        affected_package_count=sum(group.count for group in groups),
        time_critical_package_count=sum(group.count for group in groups if group.time_critical),
        held_in_place_count=plan.held_in_place,
        redistributed_count=plan.redistributed,
        own_flight_count=plan.own_flight,
        partner_flight_count=plan.partner_flight,
        unprotected_count=plan.unprotected,
        unprotected_time_critical_count=plan.unprotected_time_critical,
        allocations=plan.allocations,
        capacity_constraints=constraints,
        service_commitments_at_risk=plan.commitments_at_risk,
    )


def _early_result(
    candidate: CandidateOption,
    viability: Viability,
    rationale: str,
    reason: str,
    conflicts: tuple[RouteConflict, ...],
    missing: tuple[str, ...],
) -> CandidateEvaluation:
    return CandidateEvaluation(
        assessment=RecoveryOptionAssessment(
            option_id=candidate.option_id,
            kind=candidate.kind,
            viability=viability,
            impact_level=None,
            threshold_rule=None,
            schedule_delay_minutes=None,
            earliest_feasible_departure=None,
            substitute_aircraft_id=None,
            package=_unassessed_packages(reason),
            cost=None,
            conflict_ids=tuple(conflict.conflict_id for conflict in conflicts),
            missing_inputs=missing,
            rationale=rationale,
        ),
        conflicts=conflicts,
        used_estimated_eta=False,
    )


def evaluate_candidate(
    candidate: CandidateOption, context: EvaluationContext, settings: OperationsSettings
) -> CandidateEvaluation:
    flights = context.flights
    crew_conflicts = tuple(_crew_gap_conflicts(candidate.option_id, flights))
    if crew_conflicts:
        names = ", ".join(sorted({c.resource_ids[0] for c in crew_conflicts}))
        return _early_result(
            candidate,
            Viability.NOT_VIABLE,
            f"Not viable: no crew coverage for {names}.",
            "package impact not evaluated: option not viable",
            crew_conflicts,
            (),
        )

    substitute: SubstituteCandidate | None = None
    rejected: list[RouteConflict] = []
    if candidate.kind is OptionKind.SWAP:
        if context.fleet is None:
            return _early_result(
                candidate,
                Viability.UNDETERMINED,
                "Swap not assessed: fleet availability data is unavailable.",
                "package impact not evaluated: fleet availability unavailable",
                (),
                ("fleet availability",),
            )
        for option in check_fleet_availability(
            context.fleet, flights, context.request.case.aircraft_id, settings
        ):
            clashes = _double_booking_conflicts(
                candidate.option_id,
                option.aircraft.aircraft_id,
                flights,
                compute_timings(flights, option.ready_at),
                context.all_flights,
            )
            if clashes:
                rejected.extend(clashes)
            else:
                substitute = option
                break
        if substitute is None:
            return _early_result(
                candidate,
                Viability.NOT_VIABLE,
                "Not viable: no serviceable, correctly typed, conflict-free substitute aircraft "
                "is available within the swap window.",
                "package impact not evaluated: option not viable",
                tuple(rejected),
                (),
            )
        ready_at = substitute.ready_at
    else:
        if candidate.readiness_eta is None:
            return _early_result(
                candidate,
                Viability.UNDETERMINED,
                "Not assessed: no readiness ETA was supplied and none is assumed.",
                "package impact not evaluated: readiness ETA missing",
                (),
                (f"readiness ETA for {candidate.option_id}",),
            )
        ready_at = candidate.readiness_eta + timedelta(minutes=settings.turnaround_buffer_minutes)

    timings = compute_timings(flights, ready_at)
    time_conflicts = (
        _time_estimate_conflicts(candidate.option_id, candidate.readiness_eta, flights, settings)
        if candidate.kind is not OptionKind.SWAP and candidate.readiness_eta is not None
        else []
    )
    conflicts = (*time_conflicts, *rejected)

    delay_minutes = max(timing.delay_minutes for timing in timings)
    total_delay = sum(timing.delay_minutes for timing in timings)
    latest_departure = max(timing.feasible_departure for timing in timings)

    plan: RedistributionPlan | None = None
    reroute_assessed = context.replacement_flights is not None
    package = _unassessed_packages("package load data not available")
    if context.packages is not None:
        groups = tuple(
            group
            for group in context.packages.groups
            if group.flight_number in {flight.flight_number for flight in flights}
        )
        plan = check_load_redistribution(
            groups,
            context.replacement_flights or (),
            PrimaryPath(
                substitute_id=substitute.aircraft.aircraft_id if substitute else None,
                substitute_capacity=substitute.aircraft.package_capacity if substitute else 0,
            ),
            {timing.flight_number: timing.feasible_departure for timing in timings},
            {flight.flight_number: (flight.origin, flight.destination) for flight in flights},
            context.request.reroute_policy.prefer_own_network,
        )
        package = _package_outcome(plan, groups, reroute_assessed)

    threshold = apply_disruption_thresholds(
        delay_minutes,
        any(flight.service_critical for flight in flights),
        plan is not None and plan.unprotected_time_critical > 0,
        settings,
    )
    cost = compute_cost(total_delay, substitute is not None, plan, settings, reroute_assessed)

    has_risk = (
        bool(time_conflicts)
        or plan is None
        or not reroute_assessed
        or plan.unprotected > 0
        or threshold.level in {ImpactLevel.HIGH, ImpactLevel.CRITICAL}
    )
    viability = Viability.VIABLE_WITH_RISK if has_risk else Viability.VIABLE

    rationale = _rationale(
        candidate, substitute, delay_minutes, threshold, plan, rejected, time_conflicts
    )
    return CandidateEvaluation(
        assessment=RecoveryOptionAssessment(
            option_id=candidate.option_id,
            kind=candidate.kind,
            viability=viability,
            impact_level=threshold.level,
            threshold_rule=threshold.rule,
            schedule_delay_minutes=delay_minutes,
            earliest_feasible_departure=latest_departure,
            substitute_aircraft_id=substitute.aircraft.aircraft_id if substitute else None,
            package=package,
            cost=cost,
            conflict_ids=tuple(conflict.conflict_id for conflict in conflicts),
            missing_inputs=(),
            rationale=rationale,
        ),
        conflicts=tuple(conflicts),
        used_estimated_eta=candidate.eta_basis is EtaBasis.ESTIMATED,
    )


def _rationale(
    candidate: CandidateOption,
    substitute: SubstituteCandidate | None,
    delay_minutes: int,
    threshold: ThresholdResult,
    plan: RedistributionPlan | None,
    rejected: list[RouteConflict],
    time_conflicts: list[RouteConflict],
) -> str:
    parts = [
        f"{candidate.kind.value}: {delay_minutes} minute schedule delay, "
        f"{threshold.level.value} impact."
    ]
    if substitute is not None:
        parts.append(
            f"Substitute {substitute.aircraft.aircraft_id} (capacity "
            f"{substitute.aircraft.package_capacity}) ready {_hhmm(substitute.ready_at)}."
        )
    for conflict in rejected:
        parts.append(f"Alternative rejected: {conflict.description}.")
    if plan is None:
        parts.append("Package impact not assessed because package load data is unavailable.")
    else:
        parts.append(
            f"Packages: {plan.held_in_place} held, {plan.redistributed} redistributed "
            f"({plan.own_flight} on own-network flights, {plan.partner_flight} on partner "
            f"flights), {plan.unprotected} unprotected."
        )
    for conflict in time_conflicts:
        parts.append(f"Conflict: {conflict.description}.")
    return " ".join(parts)
