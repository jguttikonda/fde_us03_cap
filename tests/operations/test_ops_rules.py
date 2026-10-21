from datetime import timedelta

import pytest

from aog_recovery.operations.models import (
    AllocationPath,
    ConflictCode,
    CrewCoverage,
    EtaBasis,
    ImpactLevel,
    PackageGroup,
    PackageServiceLevel,
    ReplacementFlight,
    ReroutePolicy,
    Viability,
)
from aog_recovery.operations.rules import (
    EvaluationContext,
    PrimaryPath,
    RedistributionPlan,
    apply_disruption_thresholds,
    check_fleet_availability,
    check_load_redistribution,
    compute_cost,
    compute_timings,
    detect_route_conflicts,
    evaluate_candidate,
    find_replacement_flights,
    validate_flight_schedule,
)
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import (
    T0,
    at,
    default_alternate_flights,
    default_fleet,
    default_packages,
    default_schedule,
    delay_option,
    repair_alternate,
    repair_original,
    request_for,
    swap_option,
)

SETTINGS = OperationsSettings()


# --- apply_disruption_thresholds (ARD-OPS-003) ---------------------------------------------


@pytest.mark.parametrize(
    ("minutes", "level"),
    [
        (0, ImpactLevel.LOW),
        (59, ImpactLevel.LOW),
        (60, ImpactLevel.MEDIUM),
        (179, ImpactLevel.MEDIUM),
        (180, ImpactLevel.HIGH),
        (359, ImpactLevel.HIGH),
        (360, ImpactLevel.CRITICAL),
        (1000, ImpactLevel.CRITICAL),
    ],
)
def test_threshold_boundaries(minutes: int, level: ImpactLevel) -> None:
    result = apply_disruption_thresholds(minutes, False, False, SETTINGS)
    assert result.level is level
    assert result.rule == f"delay_threshold_{level.value}"


def test_uplift_is_one_step_and_capped_at_critical() -> None:
    assert apply_disruption_thresholds(10, True, False, SETTINGS).level is ImpactLevel.MEDIUM
    both = apply_disruption_thresholds(10, True, True, SETTINGS)
    assert both.level is ImpactLevel.MEDIUM
    assert "service_critical_flight" in both.rule
    assert "unprotected_time_critical_packages" in both.rule
    assert apply_disruption_thresholds(420, True, True, SETTINGS).level is ImpactLevel.CRITICAL


def test_thresholds_follow_configuration() -> None:
    custom = OperationsSettings(
        delay_medium_minutes=10, delay_high_minutes=20, delay_critical_minutes=30
    )
    assert apply_disruption_thresholds(20, False, False, custom).level is ImpactLevel.HIGH


# --- validate_flight_schedule ---------------------------------------------------------------


def test_schedule_validation_lists_missing_flights_and_mismatches() -> None:
    request = request_for(repair_original())
    request = request.model_copy(update={"affected_flight_numbers": ("FX103", "FX999", "FX440")})
    validation = validate_flight_schedule(request, default_schedule())
    assert [f.flight_number for f in validation.flights] == ["FX103", "FX440"]
    assert validation.missing_flight_numbers == ("FX999",)
    assert validation.assignment_mismatches == ("FX440",)


# --- compute_timings and conflicts (ARD-OPS-002/008) -----------------------------------------


def test_timings_use_latest_of_schedule_readiness_and_crew() -> None:
    flights = default_schedule(crew=CrewCoverage.DELAYED, crew_available_from=at(19)).flights[:1]
    early = compute_timings(flights, at(10))[0]
    assert (early.feasible_departure, early.delay_minutes) == (at(19), 300)
    ready = compute_timings(flights, at(20))[0]
    assert ready.delay_minutes == 360


def test_no_negative_delay_when_ready_before_schedule() -> None:
    flights = default_schedule().flights[:1]
    assert compute_timings(flights, at(9))[0].delay_minutes == 0


@pytest.mark.parametrize(("crew_from", "conflict"), [(at(16, 30), False), (at(16, 31), True)])
def test_time_estimate_conflict_boundary(crew_from, conflict) -> None:  # noqa: ANN001
    schedule = default_schedule(crew=CrewCoverage.DELAYED, crew_available_from=crew_from)
    flights = schedule.flights[:1]
    timings = compute_timings(flights, at(15, 30))
    conflicts = detect_route_conflicts(
        "opt", flights, timings, schedule.flights, None, at(15), SETTINGS
    )
    assert bool(conflicts) is conflict
    if conflict:
        assert conflicts[0].code is ConflictCode.TIME_ESTIMATE_CONFLICT
        assert "FX103" in conflicts[0].resource_ids


def test_crew_gap_names_flight_and_crew_resources() -> None:
    schedule = default_schedule(crew=CrewCoverage.GAP)
    flights = schedule.flights[:1]
    conflicts = detect_route_conflicts(
        "opt", flights, compute_timings(flights, at(15)), schedule.flights, None, None, SETTINGS
    )
    assert [c.code for c in conflicts] == [ConflictCode.CREW_COVERAGE_GAP]
    assert conflicts[0].resource_ids == ("FX103", "crew:FX103")


def test_conflict_detection_is_deterministic() -> None:
    schedule = default_schedule(crew=CrewCoverage.GAP)
    flights = schedule.flights[:1]
    args = (
        "opt",
        flights,
        compute_timings(flights, at(15)),
        schedule.flights,
        None,
        None,
        SETTINGS,
    )
    assert detect_route_conflicts(*args) == detect_route_conflicts(*args)


# --- check_fleet_availability (ARD-OPS-002) ---------------------------------------------------


def _flights():  # noqa: ANN202
    return default_schedule().flights[:1]


def test_fleet_selection_orders_by_ready_time() -> None:
    chosen = check_fleet_availability(default_fleet(), _flights(), "N123AB", SETTINGS)
    assert [c.aircraft.aircraft_id for c in chosen] == ["N980FX", "N981FX"]
    assert chosen[0].ready_at == at(15)
    assert chosen[1].ready_at == at(16, 30)


def test_fleet_excludes_wrong_type_status_and_original_aircraft() -> None:
    ids = {
        c.aircraft.aircraft_id
        for c in check_fleet_availability(default_fleet(), _flights(), "N980FX", SETTINGS)
    }
    assert ids == {"N981FX"}


def test_fleet_tie_break_is_capacity_then_identifier() -> None:
    first, second, *_ = default_fleet().aircraft
    twin = second.model_copy(
        update={"available_from": first.available_from, "positioning_minutes": 0}
    )
    bigger = twin.model_copy(update={"aircraft_id": "N001XX", "package_capacity": 950})
    same_cap = twin.model_copy(update={"aircraft_id": "N000XX", "package_capacity": 900})
    fleet = default_fleet().model_copy(update={"aircraft": (first, same_cap, bigger)})
    order = [
        c.aircraft.aircraft_id
        for c in check_fleet_availability(fleet, _flights(), "N123AB", SETTINGS)
    ]
    assert order == ["N001XX", "N000XX", "N980FX"]


def test_fleet_positioning_limit_and_swap_window() -> None:
    first, second, *_ = default_fleet().aircraft
    too_far = first.model_copy(update={"positioning_minutes": 241})
    too_late = second.model_copy(update={"available_from": at(23)})
    fleet = default_fleet().model_copy(update={"aircraft": (too_far, too_late)})
    assert check_fleet_availability(fleet, _flights(), "N123AB", SETTINGS) == ()


def test_fleet_requires_single_compatible_type() -> None:
    flights = default_schedule().flights
    other_type = flights[1].model_copy(update={"required_aircraft_type": "B767"})
    mixed = (flights[0], other_type)
    assert check_fleet_availability(default_fleet(), mixed, "N123AB", SETTINGS) == ()


# --- find_replacement_flights: own network vs partner (ARD-OPS-009) -----------------------------

CUTOFF = at(17, 30)
EVALUATED = T0 + timedelta(minutes=10)
ROUTES = {"FX103": ("MIA", "ORD")}


def replacement(
    policy: ReroutePolicy | None = None,
    evaluated_at=EVALUATED,  # noqa: ANN001
) -> tuple[ReplacementFlight, ...]:
    return find_replacement_flights(
        _flights(), default_alternate_flights(), policy or ReroutePolicy(), evaluated_at, CUTOFF
    )


def by_number(flights: tuple[ReplacementFlight, ...]) -> dict[str, ReplacementFlight]:
    return {f.flight_number: f for f in flights}


def test_flights_are_limited_to_the_affected_route_and_ordered_own_first() -> None:
    assert [f.flight_number for f in replacement()] == ["FX505", "PX150", "PX220", "PX310"]


def test_without_own_network_preference_flights_are_ordered_by_departure() -> None:
    flights = replacement(ReroutePolicy(prefer_own_network=False))
    assert [f.flight_number for f in flights] == ["PX150", "FX505", "PX220", "PX310"]


def test_flight_after_the_latest_cutoff_is_not_usable() -> None:
    found = by_number(replacement())
    assert found["PX310"].bookable is False
    assert found["PX310"].restriction == "departs after the latest package cut-off"
    assert all(found[n].bookable for n in ("FX505", "PX150", "PX220"))


def test_policy_can_forbid_partner_flights() -> None:
    found = by_number(replacement(ReroutePolicy(allow_partner_flights=False)))
    assert found["FX505"].bookable is True
    for number in ("PX150", "PX220", "PX310"):
        assert (
            found[number].restriction == "partner flights are not permitted by the reroute policy"
        )


def test_policy_can_cap_partner_cost_per_package() -> None:
    found = by_number(replacement(ReroutePolicy(max_partner_cost_per_package_usd=20)))
    assert found["PX150"].bookable is True
    assert found["PX220"].restriction == "partner cost per package exceeds the policy limit"
    assert found["FX505"].bookable is True


def test_expired_booking_deadline_and_departed_flights_are_not_usable() -> None:
    found = by_number(replacement(evaluated_at=at(15, 10)))
    assert found["PX150"].restriction == "booking deadline has passed"
    assert found["PX220"].bookable is True
    late = by_number(replacement(evaluated_at=at(16, 5)))
    assert late["FX505"].restriction == "already departed at evaluation time"


def test_flight_without_spare_capacity_is_not_usable() -> None:
    data = default_alternate_flights()
    full = data.flights[0].model_copy(update={"available_capacity": 0})
    flights = find_replacement_flights(
        _flights(), data.model_copy(update={"flights": (full,)}), ReroutePolicy(), EVALUATED, CUTOFF
    )
    assert flights[0].restriction == "no spare package capacity"


def test_the_affected_flight_is_never_offered_as_its_own_replacement() -> None:
    data = default_alternate_flights()
    same = data.flights[0].model_copy(update={"flight_number": "FX103"})
    flights = find_replacement_flights(
        _flights(), data.model_copy(update={"flights": (same,)}), ReroutePolicy(), EVALUATED, CUTOFF
    )
    assert flights == ()


# --- check_load_redistribution (ARD-OPS-009, test case 6) -------------------------------------


def redistribute(
    primary: PrimaryPath,
    departure,  # noqa: ANN001
    flights: tuple[ReplacementFlight, ...] = (),
    groups=None,  # noqa: ANN001
    routes=ROUTES,  # noqa: ANN001
    prefer_own: bool = True,
) -> RedistributionPlan:
    return check_load_redistribution(
        groups or default_packages().groups,
        flights,
        primary,
        {"FX103": departure},
        routes,
        prefer_own,
    )


def test_case_6_swap_capacity_900_with_300_unprotected() -> None:
    plan = redistribute(PrimaryPath("N980FX", 900), at(15))
    by_group = {a.group_id: a.count for a in plan.allocations}
    assert by_group == {"FX103-PRIORITY": 700, "FX103-STANDARD": 200}
    assert {a.path for a in plan.allocations} == {AllocationPath.SUBSTITUTE_AIRCRAFT}
    assert plan.redistributed == 900
    assert plan.unprotected == 300
    assert plan.unprotected_time_critical == 0
    assert plan.unprotected_standard_rate == 300
    assert plan.commitments_at_risk == (
        "FX103 standard packages: 300 unprotected against the 17:30Z cut-off",
    )
    assert any("fully used" in c for c in plan.capacity_constraints)


def test_priority_packages_are_allocated_first_when_capacity_is_short() -> None:
    plan = redistribute(PrimaryPath("N980FX", 100), at(15))
    assert [(a.group_id, a.count) for a in plan.allocations] == [("FX103-PRIORITY", 100)]
    assert plan.unprotected_time_critical == 600


def test_missing_cutoff_leaves_everything_unprotected() -> None:
    plan = redistribute(PrimaryPath("N980FX", 900), at(18))
    assert plan.allocations == ()
    assert plan.unprotected == 1200
    assert plan.unprotected_time_critical == 700


def test_late_repair_reroutes_on_own_flights_first_then_partner_flights() -> None:
    plan = redistribute(PrimaryPath(None, 0), at(19), replacement())
    assert [(a.group_id, a.target_id, a.path, a.count, a.cost_usd) for a in plan.allocations] == [
        ("FX103-PRIORITY", "FX505", AllocationPath.OWN_FLIGHT, 150, 750),
        ("FX103-PRIORITY", "PX220", AllocationPath.PARTNER_FLIGHT, 400, 8800),
        ("FX103-STANDARD", "PX150", AllocationPath.PARTNER_FLIGHT, 100, 1800),
    ]
    assert (plan.own_flight, plan.partner_flight, plan.reroute_cost_usd) == (150, 500, 11350)
    assert plan.redistributed == 650
    assert plan.unprotected == 550
    assert plan.unprotected_time_critical == 150
    assert (plan.unprotected_priority_rate, plan.unprotected_standard_rate) == (150, 400)


def test_service_level_restricted_flight_never_takes_priority_packages() -> None:
    plan = redistribute(PrimaryPath(None, 0), at(19), replacement())
    assert not [a for a in plan.allocations if a.target_id == "PX150" and "PRIORITY" in a.group_id]


def test_unusable_flights_are_never_allocated() -> None:
    plan = redistribute(PrimaryPath(None, 0), at(19), replacement())
    assert "PX310" not in {a.target_id for a in plan.allocations}
    own_only = redistribute(
        PrimaryPath(None, 0), at(19), replacement(ReroutePolicy(allow_partner_flights=False))
    )
    assert {a.target_id for a in own_only.allocations} == {"FX505"}
    assert own_only.partner_flight == 0
    assert own_only.unprotected == 1050


def test_flights_on_a_different_route_are_not_used() -> None:
    plan = redistribute(
        PrimaryPath(None, 0), at(19), replacement(), routes={"FX103": ("MIA", "ATL")}
    )
    assert plan.allocations == ()
    assert plan.unprotected == 1200


def test_substitute_capacity_is_used_before_rerouting() -> None:
    plan = redistribute(PrimaryPath("N980FX", 900), at(15), replacement())
    assert plan.redistributed == 1200
    assert plan.unprotected == 0
    assert (plan.own_flight, plan.partner_flight) == (150, 150)
    assert plan.reroute_cost_usd == 150 * 5 + 100 * 18 + 50 * 22


def test_hold_in_place_when_departure_meets_cutoff() -> None:
    plan = redistribute(PrimaryPath(None, 0), at(15, 30), replacement())
    assert (plan.held_in_place, plan.redistributed, plan.unprotected) == (1200, 0, 0)
    assert {a.path for a in plan.allocations} == {AllocationPath.HELD}
    assert plan.reroute_cost_usd == 0


def test_cutoff_equal_to_departure_is_protected() -> None:
    assert redistribute(PrimaryPath(None, 0), at(17, 30)).unprotected == 0


def test_group_ordering_is_deterministic_by_cutoff_then_id() -> None:
    early = PackageGroup(
        group_id="A-EARLY",
        flight_number="FX103",
        service_level=PackageServiceLevel.STANDARD,
        time_critical=False,
        count=50,
        cutoff_at=at(16),
    )
    groups = (*default_packages().groups, early)
    first = redistribute(PrimaryPath("S", 600), at(15), groups=groups)
    second = redistribute(PrimaryPath("S", 600), at(15), groups=tuple(reversed(groups)))
    assert first == second


# --- compute_cost (ARD-CTL-019) ----------------------------------------------------------------


def test_cost_components_sum() -> None:
    plan = redistribute(PrimaryPath("N980FX", 900), at(15))
    cost = compute_cost(60, True, plan, SETTINGS)
    assert (cost.delay_usd, cost.swap_usd, cost.rerouting_usd) == (5100, 18000, 0)
    assert cost.unprotected_packages_usd == 4500
    assert cost.total_usd == 27600
    assert cost.complete is True


def test_cost_includes_rerouting_on_own_and_partner_flights() -> None:
    plan = redistribute(PrimaryPath(None, 0), at(19), replacement())
    cost = compute_cost(330, False, plan, SETTINGS)
    assert cost.rerouting_usd == 11350
    assert cost.unprotected_packages_usd == 150 * 45 + 400 * 15
    assert cost.total_usd == 28050 + 11350 + 12750


def test_cost_is_flagged_incomplete_without_package_plan_or_flight_search() -> None:
    assert compute_cost(60, False, None, SETTINGS).complete is False
    plan = redistribute(PrimaryPath(None, 0), at(15, 30))
    assert compute_cost(0, False, plan, SETTINGS, reroute_assessed=False).complete is False


def test_cost_prices_priority_and_time_critical_packages_at_priority_rate() -> None:
    plan = redistribute(PrimaryPath(None, 0), at(18))
    cost = compute_cost(0, False, plan, SETTINGS)
    assert cost.unprotected_packages_usd == 700 * 45 + 500 * 15


# --- evaluate_candidate ------------------------------------------------------------------------


def _context(  # noqa: ANN202
    schedule=None,  # noqa: ANN001
    fleet=None,  # noqa: ANN001
    packages="default",  # noqa: ANN001
    flights="default",  # noqa: ANN001
):
    schedule = schedule or default_schedule()
    request = request_for(repair_original())
    return EvaluationContext(
        request=request,
        flights=schedule.flights[:1],
        all_flights=schedule.flights,
        fleet=fleet or default_fleet(),
        packages=default_packages() if packages == "default" else packages,
        replacement_flights=replacement() if flights == "default" else flights,
    )


def test_repair_candidate_is_viable_when_held_in_place() -> None:
    result = evaluate_candidate(repair_original(), _context(), SETTINGS)
    a = result.assessment
    assert (a.viability, a.impact_level, a.schedule_delay_minutes) == (
        Viability.VIABLE,
        ImpactLevel.MEDIUM,
        90,
    )
    assert a.package.held_in_place_count == 1200
    assert a.cost is not None
    assert a.cost.total_usd == 7650
    assert result.used_estimated_eta is False


def test_estimated_eta_is_flagged() -> None:
    result = evaluate_candidate(repair_alternate(), _context(), SETTINGS)
    assert result.used_estimated_eta is True
    assert repair_alternate().eta_basis is EtaBasis.ESTIMATED


def test_late_repair_pushes_packages_to_own_and_partner_flights() -> None:
    result = evaluate_candidate(repair_alternate(), _context(), SETTINGS).assessment
    assert result.impact_level is ImpactLevel.CRITICAL
    assert result.package.redistributed_count == 650
    assert (result.package.own_flight_count, result.package.partner_flight_count) == (150, 500)
    assert result.package.unprotected_count == 550
    assert result.cost is not None
    assert (result.cost.rerouting_usd, result.cost.total_usd) == (11350, 52150)
    assert result.viability is Viability.VIABLE_WITH_RISK
    assert result.threshold_rule is not None
    assert "unprotected_time_critical_packages" in result.threshold_rule
    assert "partner flights" in result.rationale


def test_own_network_only_policy_costs_more_unprotected_packages() -> None:
    own_only = replacement(ReroutePolicy(allow_partner_flights=False))
    context = _context(flights=own_only)
    result = evaluate_candidate(repair_alternate(), context, SETTINGS).assessment
    assert result.package.partner_flight_count == 0
    assert result.package.unprotected_count == 1050
    assert result.cost is not None
    assert result.cost.total_usd == 61050


def test_flight_search_outage_is_flagged_not_assumed() -> None:
    result = evaluate_candidate(repair_alternate(), _context(flights=None), SETTINGS).assessment
    assert result.package.reroute_assessed is False
    assert result.package.unprotected_count == 1200
    assert any("upper bounds" in c for c in result.package.capacity_constraints)
    assert result.cost is not None
    assert result.cost.complete is False
    assert result.viability is Viability.VIABLE_WITH_RISK


def test_delay_candidate_uses_its_own_eta() -> None:
    result = evaluate_candidate(delay_option(at(17, 30)), _context(), SETTINGS).assessment
    assert result.schedule_delay_minutes == 240
    assert result.impact_level is ImpactLevel.CRITICAL


def test_missing_eta_is_undetermined_without_assumption() -> None:
    candidate = repair_original().model_copy(
        update={"readiness_eta": None, "eta_basis": None, "eta_evidence_references": ()}
    )
    result = evaluate_candidate(candidate, _context(), SETTINGS).assessment
    assert result.viability is Viability.UNDETERMINED
    assert result.missing_inputs == ("readiness ETA for OPT-REPAIR-P110",)
    assert result.impact_level is None
    assert result.cost is None


def test_swap_selects_first_aircraft_and_reroutes_the_overflow() -> None:
    result = evaluate_candidate(swap_option(), _context(), SETTINGS).assessment
    assert result.substitute_aircraft_id == "N980FX"
    assert result.schedule_delay_minutes == 60
    assert result.package.unprotected_count == 0
    assert result.cost is not None
    assert result.cost.total_usd == 5100 + 18000 + (750 + 1800 + 1100)
    assert result.viability is Viability.VIABLE


def test_double_booked_substitute_is_rejected_with_named_resources() -> None:
    schedule = default_schedule()
    clash = schedule.flights[1].model_copy(
        update={
            "flight_number": "FX900",
            "assigned_aircraft_id": "N980FX",
            "scheduled_departure": at(15, 30),
            "scheduled_arrival": at(18),
        }
    )
    schedule = schedule.model_copy(update={"flights": (*schedule.flights, clash)})
    result = evaluate_candidate(swap_option(), _context(schedule), SETTINGS)
    assert result.assessment.substitute_aircraft_id == "N981FX"
    [conflict] = result.conflicts
    assert conflict.code is ConflictCode.AIRCRAFT_DOUBLE_BOOKED
    assert conflict.resource_ids == ("N980FX", "FX900")
    assert "Alternative rejected" in result.assessment.rationale
    assert result.assessment.viability is Viability.VIABLE
    assert result.assessment.cost is not None
    assert result.assessment.cost.total_usd == 12750 + 18000 + (750 + 1800 + 5500)


def test_no_substitute_is_not_viable() -> None:
    fleet = default_fleet().model_copy(update={"aircraft": ()})
    result = evaluate_candidate(swap_option(), _context(fleet=fleet), SETTINGS).assessment
    assert result.viability is Viability.NOT_VIABLE
    assert result.substitute_aircraft_id is None


def test_crew_gap_makes_every_candidate_not_viable() -> None:
    context = _context(default_schedule(crew=CrewCoverage.GAP))
    for candidate in (repair_original(), swap_option()):
        result = evaluate_candidate(candidate, context, SETTINGS)
        assert result.assessment.viability is Viability.NOT_VIABLE
        assert result.conflicts[0].code is ConflictCode.CREW_COVERAGE_GAP


def test_unavailable_package_data_is_not_assumed() -> None:
    result = evaluate_candidate(repair_original(), _context(packages=None), SETTINGS).assessment
    assert result.package.assessed is False
    assert result.package.unprotected_count is None
    assert result.cost is not None
    assert result.cost.complete is False
    assert result.viability is Viability.VIABLE_WITH_RISK


def test_evaluation_is_deterministic() -> None:
    first = evaluate_candidate(swap_option(), _context(), SETTINGS)
    second = evaluate_candidate(swap_option(), _context(), SETTINGS)
    assert first == second
    assert timedelta(minutes=30) == timedelta(minutes=SETTINGS.turnaround_buffer_minutes)
