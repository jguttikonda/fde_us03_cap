from datetime import timedelta

from aog_recovery.adapters.local import MockResponseMode
from aog_recovery.contracts.agent import AgentResultStatus
from aog_recovery.contracts.tool import ToolName
from aog_recovery.observability.structured import serialize_event
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import (
    CandidateOption,
    CrewCoverage,
    OperationsOutcome,
    OperationsRequest,
    OptionKind,
    RecommendationDecision,
    ReroutePolicy,
    Viability,
)
from aog_recovery.operations.reasoning import OperationsFacts, OperationsJudgment
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import (
    T0,
    at,
    default_adapters,
    default_case,
    default_fleet,
    default_network,
    default_packages,
    default_schedule,
    delay_option,
    make_adapters,
    repair_original,
    request_for,
    scenario_conflicting_estimates,
    scenario_full_options,
    scenario_normal_repair,
    scenario_own_network_only,
    scenario_package_timeout,
    scenario_partner_reroute,
    scenario_swap_capacity,
    swap_option,
)
from aog_recovery.validation.boundaries import validate_agent_result
from aog_recovery.validation.confidence import ConfidenceDisposition
from aog_recovery.validation.models import ValidationReport


def run(scenario) -> OperationsOutcome:  # noqa: ANN001
    return OperationsAgent(scenario.adapters).assess(scenario.request)


def options(outcome: OperationsOutcome) -> dict[str, object]:
    assert outcome.assessment is not None
    return {o.option_id: o for o in outcome.assessment.recovery_options}


# --- normal evidence ---------------------------------------------------------------------------


def test_normal_evidence_is_complete_and_preferred_but_still_needs_human_approval() -> None:
    outcome = run(scenario_normal_repair())
    assessment = outcome.assessment
    assert assessment is not None
    assert outcome.result.status is AgentResultStatus.COMPLETE
    assert outcome.result.confidence == 0.9
    assert outcome.confidence.disposition is ConfidenceDisposition.PREFERRED
    assert assessment.recommendation.decision is RecommendationDecision.REPAIR_ORIGINAL
    assert assessment.human_approval_required is True
    assert assessment.missing_data == () and assessment.missing_analysis == ()
    assert assessment.affected_routes == ("MIA-ORD",)
    assert assessment.operational_impact_level is not None
    assert assessment.operational_impact_level.value == "medium"


def test_result_envelope_passes_shared_validation_with_upstream_eta_references() -> None:
    outcome = run(scenario_normal_repair())
    available = {e.evidence_id for e in outcome.evidence} | {"evidence-maintenance-eta-001"}
    report = validate_agent_result(outcome.result.model_dump(), available)
    assert report.is_valid, report.findings
    missing = validate_agent_result(outcome.result.model_dump(), set())
    assert not missing.is_valid


def test_every_candidate_is_assessed_once() -> None:
    outcome = run(scenario_full_options())
    assert outcome.assessment is not None
    assert [o.option_id for o in outcome.assessment.recovery_options] == [
        "OPT-REPAIR-P110",
        "OPT-REPAIR-P120",
        "OPT-SWAP",
    ]


# --- trade-offs and human selection (ARD-OPS-007) ----------------------------------------------


def test_materially_different_options_require_human_selection_and_are_not_ranked() -> None:
    outcome = run(scenario_full_options())
    assessment = outcome.assessment
    assert assessment is not None
    assert assessment.requires_human_selection is True
    assert len(assessment.trade_offs) == 3
    assert assessment.recommendation.decision is RecommendationDecision.DEFER_TO_CONTROLLER
    assert assessment.recommendation.viable_option_ids == (
        "OPT-REPAIR-P110",
        "OPT-REPAIR-P120",
        "OPT-SWAP",
    )
    assert outcome.result.status is AgentResultStatus.PARTIAL
    assert outcome.result.confidence == 0.69
    assert "readiness ETA is an estimate, not confirmed" in assessment.confidence_reasons


def test_selection_is_forced_only_beyond_the_configured_materiality_limit() -> None:
    # Own flights only: repair leaves 0 packages unprotected and swap leaves 150.
    request = request_for(
        repair_original(),
        swap_option(),
        reroute_policy=ReroutePolicy(allow_partner_flights=False),
    )
    adapters = make_adapters(
        default_schedule(), default_fleet(), default_packages(), default_network()
    )
    default = OperationsAgent(adapters).assess(request).assessment
    relaxed = (
        OperationsAgent(
            adapters, settings=OperationsSettings(material_unprotected_packages_gap=200)
        )
        .assess(request)
        .assessment
    )
    assert default is not None and relaxed is not None
    assert default.requires_human_selection is True
    assert relaxed.requires_human_selection is False
    assert len(relaxed.trade_offs) == 2
    assert relaxed.recommendation.decision is RecommendationDecision.DEFER_TO_CONTROLLER


# --- swap and package redistribution ------------------------------------------------------------


def test_swap_capacity_case_matches_proposal_test_case_6() -> None:
    outcome = run(scenario_swap_capacity())
    assert outcome.assessment is not None
    [option] = outcome.assessment.recovery_options
    assert option.substitute_aircraft_id == "N980FX"
    assert option.package.redistributed_count == 900
    assert option.package.unprotected_count == 300
    assert {(a.group_id, a.count) for a in option.package.allocations} == {
        ("FX103-PRIORITY", 700),
        ("FX103-STANDARD", 200),
    }
    assert option.cost is not None
    assert option.cost.total_usd == 27600
    assert option.viability is Viability.VIABLE_WITH_RISK
    assert outcome.assessment.package_impact.affected_package_count == 1200
    assert outcome.assessment.package_impact.time_critical_package_count == 700


# --- conflicting estimates (ARD-GOV-004) -------------------------------------------------------


def test_conflicting_estimates_escalate_regardless_of_confidence() -> None:
    outcome = run(scenario_conflicting_estimates())
    assessment = outcome.assessment
    assert assessment is not None
    assert outcome.result.status is AgentResultStatus.ESCALATION_REQUIRED
    assert outcome.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED
    assert assessment.recommendation.decision is RecommendationDecision.ESCALATE
    [conflict] = outcome.conflicts
    assert conflict.evidence_references == (
        "evidence-maintenance-eta-001",
        "evidence-req-ops-0001-flight_schedule",
    )
    assert "210 minutes" in conflict.description
    assert [c.code.value for c in assessment.conflicts] == ["time_estimate_conflict"]
    event_types = [e.event_type for e in outcome.audit_events]
    assert "operations_conflict_detected" in event_types
    assert "operations_escalation" in event_types


def test_no_viable_candidate_escalates() -> None:
    scenario = scenario_normal_repair()
    adapters = make_adapters(
        default_schedule(crew=CrewCoverage.GAP),
        default_fleet(),
        default_packages(),
        default_network(),
    )
    outcome = OperationsAgent(adapters).assess(scenario.request)
    assert outcome.result.status is AgentResultStatus.ESCALATION_REQUIRED
    assert outcome.assessment is not None
    assert outcome.assessment.recommendation.decision is RecommendationDecision.ESCALATE
    assert outcome.assessment.recommendation.viable_option_ids == ()
    assert outcome.assessment.operational_impact_level is None


# --- degraded sources (ARD-RES-002..006) -------------------------------------------------------


def test_package_timeout_continues_with_warning_and_named_missing_analysis() -> None:
    outcome = run(scenario_package_timeout())
    assessment = outcome.assessment
    assert assessment is not None
    assert outcome.result.status is AgentResultStatus.PARTIAL
    assert outcome.result.confidence == 0.6
    assert outcome.confidence.disposition is ConfidenceDisposition.PROVISIONAL
    assert assessment.missing_analysis == ("package load redistribution not performed",)
    assert any(w.startswith("SOURCE_UNAVAILABLE") for w in assessment.warnings)
    assert assessment.package_impact.assessed is False
    assert [e.category for e in outcome.errors] == ["timeout"]
    assert outcome.errors[0].retryable is True
    assert [u.claim_reference for u in outcome.unknowns] == ["operations:package_load"]
    [option] = assessment.recovery_options
    assert option.package.assessed is False
    assert option.cost is not None and option.cost.complete is False
    assert "operations_source_failed" in [e.event_type for e in outcome.audit_events]


def test_essential_schedule_failure_is_a_structured_failed_result() -> None:
    adapters = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.UNAVAILABLE})
    outcome = OperationsAgent(adapters).assess(request_for(repair_original()))
    assert outcome.result.status is AgentResultStatus.FAILED
    assert outcome.result.confidence == 0.0
    assert outcome.assessment is None
    assert outcome.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED
    assert outcome.errors[0].category == "source_unavailable"
    payload = outcome.result.role_payload
    assert payload["advisory_only"] is True
    assert payload["human_approval_required"] is True
    assert payload["missing_analysis"] == ["flight schedule validation not performed"]
    assert any(str(w).startswith("SOURCE_UNAVAILABLE") for w in payload["warnings"])  # type: ignore[attr-defined]


def test_unknown_affected_flights_fail_without_inventing_an_assessment() -> None:
    request = request_for(repair_original()).model_copy(
        update={"affected_flight_numbers": ("FX999",)}
    )
    outcome = OperationsAgent(default_adapters()).assess(request)
    assert outcome.result.status is AgentResultStatus.FAILED
    assert outcome.result.role_payload["missing_data"] == ["flight FX999 not found in schedule"]


def test_stale_schedule_is_partial_and_provisional() -> None:
    adapters = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.STALE})
    outcome = OperationsAgent(adapters).assess(request_for(repair_original()))
    assert outcome.result.status is AgentResultStatus.PARTIAL
    assert outcome.result.confidence == 0.65
    assert outcome.confidence.disposition is ConfidenceDisposition.PROVISIONAL
    assert "flight schedule validation evidence is stale" in outcome.assessment.confidence_reasons  # type: ignore[union-attr]
    assert [e.validity_state.value for e in outcome.evidence if "schedule" in e.evidence_id] == [
        "stale"
    ]
    assert "operations_source_degraded" in [e.event_type for e in outcome.audit_events]


def test_all_sources_stale_by_age_escalates_for_low_confidence() -> None:
    adapters = make_adapters(
        default_schedule(),
        default_fleet(),
        default_packages(),
        default_network(),
        retrieved_at=T0 - timedelta(hours=5),
    )
    outcome = OperationsAgent(adapters).assess(request_for(repair_original()))
    assert outcome.result.confidence < 0.5
    assert outcome.result.status is AgentResultStatus.ESCALATION_REQUIRED
    assert outcome.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED


def test_partial_package_data_is_not_a_complete_result() -> None:
    adapters = default_adapters({ToolName.PACKAGE_LOAD: MockResponseMode.PARTIAL})
    outcome = OperationsAgent(adapters).assess(request_for(repair_original()))
    assert outcome.result.status is AgentResultStatus.PARTIAL
    assert outcome.result.confidence == 0.69


def test_missing_flight_manifest_is_reported_as_missing_data() -> None:
    packages = default_packages().model_copy(update={"groups": ()})
    adapters = make_adapters(default_schedule(), default_fleet(), packages, default_network())
    outcome = OperationsAgent(adapters).assess(request_for(repair_original()))
    assessment = outcome.assessment
    assert assessment is not None
    assert assessment.missing_data == ("package manifest for flight FX103",)
    assert assessment.package_impact.assessed is False
    assert outcome.result.status is AgentResultStatus.PARTIAL


def test_missing_eta_is_missing_data_not_an_assumption() -> None:
    no_eta = CandidateOption(option_id="OPT-NOETA", kind=OptionKind.DELAY, description="hold")
    outcome = OperationsAgent(default_adapters()).assess(request_for(no_eta, swap_option()))
    assessment = outcome.assessment
    assert assessment is not None
    assert assessment.missing_data == ("readiness ETA for OPT-NOETA",)
    undetermined = [o for o in assessment.recovery_options if o.viability is Viability.UNDETERMINED]
    assert [o.option_id for o in undetermined] == ["OPT-NOETA"]
    assert outcome.result.status is AgentResultStatus.PARTIAL
    assert assessment.recommendation.decision is RecommendationDecision.SWAP
    assert [u.claim_reference for u in outcome.unknowns] == ["operations:option:OPT-NOETA"]


def test_only_undetermined_candidates_escalate() -> None:
    no_eta = CandidateOption(option_id="OPT-NOETA", kind=OptionKind.DELAY, description="hold")
    outcome = OperationsAgent(default_adapters()).assess(request_for(no_eta))
    assert outcome.result.status is AgentResultStatus.ESCALATION_REQUIRED


def test_swap_without_fleet_data_is_undetermined_and_lowers_confidence() -> None:
    adapters = default_adapters({ToolName.FLEET_AVAILABILITY: MockResponseMode.UNAVAILABLE})
    outcome = OperationsAgent(adapters).assess(request_for(swap_option()))
    assessment = outcome.assessment
    assert assessment is not None
    assert assessment.recovery_options[0].viability is Viability.UNDETERMINED
    assert assessment.missing_analysis == ("substitute aircraft availability not performed",)
    assert outcome.result.confidence < 0.5


def test_fleet_is_not_requested_when_no_swap_candidate_exists() -> None:
    outcome = run(scenario_normal_repair())
    assert ToolName.FLEET_AVAILABILITY.value not in " ".join(
        e.evidence_id for e in outcome.evidence
    )


# --- guardrail integration --------------------------------------------------------------------


class OverreachingReasoner:
    mode = "overreaching_test_reasoner"

    def reason(self, facts: OperationsFacts) -> OperationsJudgment:
        return OperationsJudgment(
            summary="The aircraft is airworthy and the swap plan was approved.",
            reasoning="Safe to fly.",
            next_steps=("Dispatch now.",),
        )


def test_rejected_reasoning_is_replaced_visibly() -> None:
    scenario = scenario_normal_repair()
    outcome = OperationsAgent(scenario.adapters, reasoner=OverreachingReasoner()).assess(
        scenario.request
    )
    assessment = outcome.assessment
    assert assessment is not None
    assert assessment.reasoner_mode.startswith("overreaching_test_reasoner:rejected(")
    assert assessment.reasoner_mode.endswith("->deterministic_offline")
    assert "airworthy" not in assessment.recommendation.reasoning
    assert "airworthy" not in outcome.result.summary
    assert any(w.code == "REASONING_REJECTED" for w in outcome.warnings)
    assert any(w.startswith("REASONING_REJECTED") for w in assessment.warnings)
    assert "operations_fallback" in [e.event_type for e in outcome.audit_events]
    assert outcome.result.status is AgentResultStatus.COMPLETE


class RecordingReasoner:
    mode = "recording_test_reasoner"

    def __init__(self) -> None:
        self.seen: list[OperationsFacts] = []

    def reason(self, facts: OperationsFacts) -> OperationsJudgment:
        self.seen.append(facts)
        return OperationsJudgment(
            summary="Operations assessed the options.",
            reasoning="Impact evidence only.",
            next_steps=("Hand to the Controller.",),
        )


def test_a_clean_custom_reasoner_is_used_and_labelled() -> None:
    reasoner = RecordingReasoner()
    scenario = scenario_normal_repair()
    outcome = OperationsAgent(scenario.adapters, reasoner=reasoner).assess(scenario.request)
    assert outcome.assessment is not None
    assert outcome.assessment.reasoner_mode == "recording_test_reasoner"
    assert outcome.assessment.recommendation.reasoning == "Impact evidence only."
    assert len(reasoner.seen) == 1
    assert reasoner.seen[0].viable_option_ids == ("OPT-REPAIR-P110",)


# --- boundary, determinism, isolation, audit --------------------------------------------------


def test_assess_payload_validates_untrusted_input() -> None:
    scenario = scenario_normal_repair()
    agent = OperationsAgent(scenario.adapters)
    ok = agent.assess_payload(scenario.request.model_dump())
    assert isinstance(ok, OperationsOutcome)
    bad = agent.assess_payload({**scenario.request.model_dump(), "schema_version": "9.9"})
    assert isinstance(bad, ValidationReport)
    assert not bad.is_valid
    assert agent.assess_payload("not a request").is_valid is False  # type: ignore[union-attr]


def test_identical_inputs_give_identical_results() -> None:
    scenario = scenario_full_options()
    agent = OperationsAgent(scenario.adapters)
    first = agent.assess(scenario.request)
    second = agent.assess(scenario.request)
    assert first.model_dump() == second.model_dump()
    assert run(scenario_full_options()).model_dump() == first.model_dump()


def test_a_failure_in_one_case_does_not_affect_another() -> None:
    healthy = scenario_normal_repair()
    broken = scenario_package_timeout()
    other_case = default_case().model_copy(
        update={"case_id": "AOG-SYN-0002", "aircraft_id": "N123AB"}
    )
    other_request = healthy.request.model_copy(
        update={"case": other_case, "request_id": "req-ops-0002"}
    )
    healthy_agent = OperationsAgent(healthy.adapters)
    broken_agent = OperationsAgent(broken.adapters)
    before = healthy_agent.assess(healthy.request).model_dump()
    broken_outcome = broken_agent.assess(broken.request)
    other = healthy_agent.assess(other_request)
    after = healthy_agent.assess(healthy.request).model_dump()
    assert broken_outcome.result.status is AgentResultStatus.PARTIAL
    assert before == after
    assert other.result.status is AgentResultStatus.COMPLETE
    assert {e.case_id for e in other.audit_events} == {"AOG-SYN-0002"}
    assert not any("AOG-SYN-0001" in e.model_dump_json() for e in other.audit_events)


def test_audit_events_carry_required_fields_and_correlation() -> None:
    outcome = run(scenario_conflicting_estimates())
    assert [e.event_type for e in outcome.audit_events][0] == "operations_request_validated"
    assert outcome.audit_events[-1].event_type == "operations_assessment_completed"
    for event in outcome.audit_events:
        assert event.schema_version == "1.0"
        assert event.case_id == "AOG-SYN-0001"
        assert event.trace_context.trace_id == "trace-syn-0001"
        assert event.trace_context.correlation_id == "corr-syn-0001"
        assert event.component == "operations-agent"
        assert event.request_id == "req-ops-0001"
        assert event.occurred_at.tzinfo is not None
        assert event.rationale is None or len(event.rationale) <= 500
        serialize_event(event)


def test_evaluation_time_not_wall_clock_drives_staleness() -> None:
    scenario = scenario_normal_repair()
    late = OperationsRequest.model_validate(
        {**scenario.request.model_dump(), "evaluated_at": at(12) + timedelta(hours=3)}
    )
    outcome = OperationsAgent(scenario.adapters).assess(late)
    assert outcome.result.status is not AgentResultStatus.COMPLETE
    assert outcome.result.confidence < 0.9


def test_swap_with_double_booked_first_choice_uses_next_aircraft_end_to_end() -> None:
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
    adapters = make_adapters(schedule, default_fleet(), default_packages(), default_network())
    outcome = OperationsAgent(adapters).assess(request_for(swap_option()))
    assessment = outcome.assessment
    assert assessment is not None
    [option] = assessment.recovery_options
    assert option.substitute_aircraft_id == "N981FX"
    assert option.cost is not None and option.cost.total_usd == 38800
    assert assessment.conflicts[0].code.value == "aircraft_double_booked"
    assert outcome.conflicts == ()
    assert outcome.result.status is AgentResultStatus.COMPLETE
    assert option.viability is Viability.VIABLE


# --- flight sourcing: own network vs partner (ARD-OPS-009) ---------------------------------------


def test_late_repair_lists_flights_and_reroutes_own_first_then_partner() -> None:
    outcome = run(scenario_partner_reroute())
    assessment = outcome.assessment
    assert assessment is not None
    assert [(f.flight_number, f.bookable) for f in assessment.available_flights] == [
        ("FX505", True),
        ("PX150", True),
        ("PX220", True),
        ("PX310", False),
    ]
    [option] = assessment.recovery_options
    assert (option.package.own_flight_count, option.package.partner_flight_count) == (150, 500)
    assert option.package.unprotected_count == 550
    assert option.cost is not None and option.cost.total_usd == 52150
    assert any("depend on partner flights" in r for r in assessment.risk_factors)
    assert any("book them" in step for step in assessment.recommendation.next_steps)
    assert outcome.result.status is AgentResultStatus.COMPLETE


def test_policy_forbidding_partner_flights_is_respected_and_visible() -> None:
    outcome = run(scenario_own_network_only())
    assessment = outcome.assessment
    assert assessment is not None
    [option] = assessment.recovery_options
    assert option.package.partner_flight_count == 0
    assert option.package.unprotected_count == 1050
    assert {f.restriction for f in assessment.available_flights if not f.bookable} == {
        "partner flights are not permitted by the reroute policy"
    }
    assert not any("book them" in step for step in assessment.recommendation.next_steps)


def test_partner_cost_cap_leaves_cheaper_partner_flights_usable() -> None:
    request = request_for(
        delay_option(at(19)), reroute_policy=ReroutePolicy(max_partner_cost_per_package_usd=20)
    )
    outcome = OperationsAgent(default_adapters()).assess(request)
    assert outcome.assessment is not None
    [option] = outcome.assessment.recovery_options
    assert {a.target_id for a in option.package.allocations} == {"FX505", "PX150"}


def test_flight_search_outage_is_a_named_gap_with_lower_confidence() -> None:
    adapters = default_adapters({ToolName.ALTERNATE_FLIGHTS: MockResponseMode.TIMEOUT})
    outcome = OperationsAgent(adapters).assess(request_for(delay_option(at(19))))
    assessment = outcome.assessment
    assert assessment is not None
    assert outcome.result.status is AgentResultStatus.PARTIAL
    assert outcome.result.confidence == 0.6
    assert assessment.available_flights == ()
    assert assessment.missing_analysis == (
        "alternate flight search (own network and partners) not performed",
    )
    assert any(w.startswith("SOURCE_UNAVAILABLE") for w in assessment.warnings)
    assert any("could not be searched" in r for r in assessment.risk_factors)
    [option] = assessment.recovery_options
    assert option.package.reroute_assessed is False
    assert option.cost is not None and option.cost.complete is False
    assert [u.claim_reference for u in outcome.unknowns] == ["operations:alternate_flights"]


def test_request_policy_defaults_to_own_first_with_partners_allowed() -> None:
    policy = request_for(repair_original()).reroute_policy
    assert (policy.allow_partner_flights, policy.prefer_own_network) == (True, True)
    assert policy.max_partner_cost_per_package_usd is None


def test_network_disruption_is_reported_as_a_risk_factor() -> None:
    outcome = run(scenario_normal_repair())
    assert outcome.assessment is not None
    assert outcome.assessment.risk_factors == (
        "Active weather disruption at ORD (severity medium)",
    )


def test_assess_payload_accepts_json_strings_as_an_llm_or_human_would_send() -> None:
    import json

    scenario = scenario_normal_repair()
    payload = json.loads(scenario.request.model_dump_json())
    assert isinstance(payload["evaluated_at"], str)
    outcome = OperationsAgent(scenario.adapters).assess_payload(payload)
    assert isinstance(outcome, OperationsOutcome)
    assert outcome.result.status is AgentResultStatus.COMPLETE
    unserializable = OperationsAgent(scenario.adapters).assess_payload({"x": object()})
    assert isinstance(unserializable, ValidationReport) and not unserializable.is_valid
