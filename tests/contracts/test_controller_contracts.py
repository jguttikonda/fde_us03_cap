from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.contracts.governance import ReviewerRole
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.context import ControllerAuditRecorder, InMemoryControllerContextStore
from aog_recovery.controller.intake import prepare_intake
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    ExcludedRecoveryOption,
    RankedRecoveryOption,
    RecommendationCostBreakdown,
    RecommendationFactorScores,
    RecommendationStatus,
    RecommendationWeights,
    RecoveryDecisionBrief,
    RoutingOmission,
    ScoredRecoveryOption,
    SourceHealthRecord,
    SourceHealthStatus,
)
from aog_recovery.controller.ranking import rank_options
from aog_recovery.controller.scoring import normalize_relative
from aog_recovery.maintenance.models import MaintenanceRiskLevel, MaintenanceRiskMetrics
from aog_recovery.materials_logistics.models import SourcingMethod, SourcingOption
from aog_recovery.operations.models import (
    ImpactLevel,
    OptionKind,
    PackageLoadData,
    PackageOutcome,
)
from aog_recovery.operations.models import (
    SourcingMethod as CandidateSourcingMethod,
)
from aog_recovery.validation.confidence import assess_confidence
from aog_recovery.validation.human_gate import HumanGateAssessment, HumanGateStatus


def _scored_recovery_option(
    option_id: str,
    score: Decimal,
    *,
    kind: OptionKind = OptionKind.DELAY,
    sourcing_method: CandidateSourcingMethod | None = None,
    cost: RecommendationCostBreakdown | None = None,
) -> ScoredRecoveryOption:
    return ScoredRecoveryOption(
        option_id=option_id,
        kind=kind,
        description=f"Recovery option {option_id}",
        sourcing_method=sourcing_method,
        readiness_eta=datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
        affected_routes=("MIA-ORD",),
        impact_level=ImpactLevel.LOW,
        schedule_delay_minutes=0,
        package=PackageOutcome(
            assessed=True,
            reroute_assessed=True,
            affected_package_count=0,
            time_critical_package_count=0,
            held_in_place_count=0,
            redistributed_count=0,
            own_flight_count=0,
            partner_flight_count=0,
            unprotected_count=0,
            unprotected_time_critical_count=0,
            allocations=(),
            capacity_constraints=(),
            service_commitments_at_risk=(),
        ),
        maintenance_risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.LOW,
            parts_dependency_risk=MaintenanceRiskLevel.LOW,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=(),
        operational_risks=(),
        assumptions=(),
        factor_scores=RecommendationFactorScores(
            speed=score,
            operational_package_impact=score,
            risk=score,
            cost=score,
        ),
        aggregate_score=score,
        cost=cost
        or RecommendationCostBreakdown(
            repair_labor_usd=Decimal("0"),
            sourcing_usd=Decimal("0"),
            operations_usd=Decimal("0"),
            total_usd=Decimal("0"),
        ),
        evidence_references=(f"evidence-{option_id}",),
        trade_off=f"Trade-off for {option_id}",
    )


def test_controller_intake_reuses_validated_case_and_evidence(
    valid_case_payload: dict[str, object],
) -> None:
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(
            {
                "evidence_id": "evidence-001",
                "source": "synthetic-maintenance",
                "retrieved_at": datetime(2026, 10, 21, tzinfo=UTC),
                "validity_state": EvidenceValidity.CURRENT,
                "claim_reference": "repairability",
                "content": {},
            },
        ),
    )

    assert intake.case.case_id == valid_case_payload["case_id"]
    assert intake.evidence[0].evidence_id == "evidence-001"


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": "1.0", "case": {}, "evidence": ()},
        {"schema_version": "2.0", "case": {}, "evidence": ()},
        {
            "schema_version": "1.0",
            "case": {},
            "evidence": (),
            "untrusted_extra": "must be rejected",
        },
    ],
)
def test_controller_intake_rejects_invalid_versions_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ControllerIntake.model_validate(payload)


def test_source_health_requires_reason_when_degraded() -> None:
    with pytest.raises(ValidationError, match="requires a reason"):
        SourceHealthRecord(
            source_id="maintenance-records",
            status=SourceHealthStatus.UNAVAILABLE,
            checked_at=datetime(2026, 10, 21, tzinfo=UTC),
            evidence_references=(),
        )


def test_invalid_intake_has_findings_and_no_route(valid_case_payload: dict[str, object]) -> None:
    del valid_case_payload["case_id"]
    valid_case_payload["untrusted"] = "ignored nowhere"
    payload = {"schema_version": "1.0", "case": valid_case_payload, "evidence": []}

    result = prepare_intake(payload, validated_at=datetime(2026, 10, 21, tzinfo=UTC))

    assert not result.validation.is_valid
    assert result.intake is None
    assert result.routing is None
    assert {finding.field_path for finding in result.validation.findings} == {
        "case.case_id",
        "case.untrusted",
    }


def test_valid_intake_routes_all_specialists_and_exposes_unknown_health(
    valid_case_payload: dict[str, object],
) -> None:
    result = prepare_intake(
        {"schema_version": "1.0", "case": valid_case_payload, "evidence": []},
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
    )

    assert result.validation.is_valid
    assert result.routing is not None
    assert result.routing.selected_roles == (
        AgentRole.MAINTENANCE,
        AgentRole.MATERIALS_LOGISTICS,
        AgentRole.OPERATIONS,
    )
    assert result.routing.omitted_roles == ()
    assert {item.status for item in result.routing.source_health} == {SourceHealthStatus.UNKNOWN}


def test_routing_retains_unavailable_source_and_explicit_omission(
    valid_case_payload: dict[str, object],
) -> None:
    unavailable = {
        "source_id": "materials-catalog",
        "agent_role": AgentRole.MATERIALS_LOGISTICS,
        "status": SourceHealthStatus.UNAVAILABLE,
        "checked_at": datetime(2026, 10, 21, tzinfo=UTC),
        "evidence_references": (),
        "reason": "synthetic catalog outage",
    }
    omission = RoutingOmission(
        agent_role=AgentRole.OPERATIONS,
        reason="case contains no affected flight data",
    )
    result = prepare_intake(
        {
            "schema_version": "1.0",
            "case": valid_case_payload,
            "evidence": [],
            "source_health": [unavailable],
        },
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
        omitted_specialists=(omission,),
    )

    assert result.routing is not None
    assert result.routing.selected_roles == (AgentRole.MAINTENANCE, AgentRole.MATERIALS_LOGISTICS)
    assert result.routing.omitted_roles == (omission,)
    assert any(
        item.source_id == "materials-catalog" and item.status is SourceHealthStatus.UNAVAILABLE
        for item in result.routing.source_health
    )
    assert any("case contains no affected flight data" in item for item in result.routing.rationale)


def test_intake_and_routing_events_are_correlated_and_invalid_intake_stays_unrouted(
    valid_case_payload: dict[str, object],
) -> None:
    store = InMemoryControllerContextStore()
    audit = ControllerAuditRecorder(store)
    payload = {"schema_version": "1.0", "case": valid_case_payload, "evidence": []}

    accepted = prepare_intake(
        payload,
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
        audit_recorder=audit,
    )
    rejected_case = dict(valid_case_payload)
    rejected_case.pop("aircraft_id")
    rejected = prepare_intake(
        {"schema_version": "1.0", "case": rejected_case, "evidence": []},
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
        audit_recorder=audit,
    )

    events = store.events_for(valid_case_payload["case_id"])
    assert [event.event_type for event in events] == [
        "controller_intake_validation",
        "controller_routing",
        "controller_intake_validation",
    ]
    assert {event.trace_context.correlation_id for event in events} == {"corr-synthetic-001"}
    assert events[-1].status == "rejected"
    assert accepted.audit_errors == ()
    assert rejected.routing is None
    assert not rejected.validation.is_valid
    assert rejected.audit_errors == ()


@pytest.mark.parametrize(
    "kind",
    [
        OptionKind.REPAIR_ORIGINAL,
        OptionKind.REPAIR_ALTERNATE,
        OptionKind.SWAP,
        OptionKind.DELAY,
    ],
)
def test_candidate_construction_is_stable_unranked_and_preserves_missing_inputs(
    kind: OptionKind,
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    source = CandidateSource(
        source_key=f"source-{kind.value}",
        kind=kind,
        source_evidence_references=(current_evidence.evidence_id,),
        readiness=ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
            basis=EtaBasis.ESTIMATED,
            evidence_references=(current_evidence.evidence_id,),
        ),
        package_load=PackageLoadData(groups=()),
        package_load_evidence_references=(current_evidence.evidence_id,),
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(source,),
    )

    first = build_candidates(intake)[0]
    second = build_candidates(intake)[0]

    assert first.candidate.option_id == second.candidate.option_id
    assert first.candidate.kind is kind
    expected_readiness = (
        None
        if kind in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
        else datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
    )
    assert first.candidate.readiness_eta == expected_readiness
    expected_missing_data = (
        ("readiness_eta", "failed_part_number", "sourcing_options", "sourcing_eta")
        if kind in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
        else ()
    )
    assert first.missing_data == expected_missing_data
    assert not hasattr(first.candidate, "score")
    assert not hasattr(first.candidate, "rank")


def test_candidate_construction_does_not_invent_readiness_or_package_data(
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(
            CandidateSource(
                source_key="delay-evidence",
                kind=OptionKind.DELAY,
                source_evidence_references=(current_evidence.evidence_id,),
            ),
        ),
    )

    candidate = build_candidates(intake)[0]

    assert candidate.candidate.readiness_eta is None
    assert candidate.candidate.eta_evidence_references == ()
    assert candidate.package_load is None
    assert candidate.missing_data == ("readiness_eta", "package_load")


def test_candidate_retains_its_sourcing_and_package_load_inputs(
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    sourcing = SourcingOption(
        part_number="P-120",
        source="synthetic-station",
        source_location="TEST-STATION-002",
        method=SourcingMethod.INTERNAL_TRANSFER,
        shipping_provider=None,
        shipping_service=None,
        transfer_required=True,
        lead_time_hours=4,
        eta_at=datetime(2026, 10, 21, 16, 0, tzinfo=UTC),
        estimated_cost_usd=Decimal("125.00"),
        quote_unavailable_reason=None,
        evidence_references=(current_evidence.evidence_id,),
    )
    package_load = PackageLoadData(groups=())
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(
            CandidateSource(
                source_key="alternate-part-p120",
                kind=OptionKind.REPAIR_ALTERNATE,
                source_evidence_references=(current_evidence.evidence_id,),
                readiness=ReadinessEstimate(
                    source_agent=AgentRole.MAINTENANCE,
                    eta=datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
                    basis=EtaBasis.CONFIRMED,
                    evidence_references=(current_evidence.evidence_id,),
                ),
                sourcing_options=(sourcing,),
                package_load=package_load,
                package_load_evidence_references=(current_evidence.evidence_id,),
            ),
        ),
    )

    candidate = build_candidates(intake)[0]

    assert candidate.sourcing_options == (sourcing,)
    assert candidate.source.sourcing_options == (sourcing,)
    assert candidate.candidate.readiness_eta == datetime(2026, 10, 21, 16, 0, tzinfo=UTC)
    assert candidate.package_load == package_load
    assert candidate.package_load_evidence_references == (current_evidence.evidence_id,)


def test_candidate_construction_expands_sourcing_offers_with_stable_candidate_specific_eta(
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    first_offer = SourcingOption(
        part_number="P-120",
        source="synthetic-station-a",
        source_location="TEST-STATION-A",
        method=SourcingMethod.INTERNAL_TRANSFER,
        shipping_provider=None,
        shipping_service=None,
        transfer_required=True,
        lead_time_hours=1,
        eta_at=datetime(2026, 10, 21, 14, 0, tzinfo=UTC),
        estimated_cost_usd=Decimal("50.00"),
        quote_unavailable_reason=None,
        evidence_references=(current_evidence.evidence_id,),
    )
    second_offer = first_offer.model_copy(
        update={
            "source": "synthetic-station-b",
            "source_location": "TEST-STATION-B",
            "method": SourcingMethod.VENDOR_PURCHASE,
            "eta_at": datetime(2026, 10, 21, 17, 0, tzinfo=UTC),
            "estimated_cost_usd": Decimal("150.00"),
        }
    )
    source = CandidateSource(
        source_key="alternate-part-p120",
        kind=OptionKind.REPAIR_ALTERNATE,
        failed_part_number="P-110",
        source_evidence_references=(current_evidence.evidence_id,),
        readiness=ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
            basis=EtaBasis.CONFIRMED,
            evidence_references=(current_evidence.evidence_id,),
        ),
        sourcing_options=(first_offer, second_offer),
        package_load=PackageLoadData(groups=()),
        package_load_evidence_references=(current_evidence.evidence_id,),
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(source,),
    )

    candidates = build_candidates(intake)
    repeated = build_candidates(intake)

    assert len(candidates) == 2
    assert tuple(item.candidate.option_id for item in candidates) == tuple(
        item.candidate.option_id for item in repeated
    )
    assert len({item.candidate.option_id for item in candidates}) == 2
    assert tuple(item.sourcing_options for item in candidates) == ((first_offer,), (second_offer,))
    assert tuple(item.source.sourcing_options for item in candidates) == (
        (first_offer,),
        (second_offer,),
    )
    assert tuple(item.candidate.readiness_eta for item in candidates) == (
        datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
        datetime(2026, 10, 21, 17, 0, tzinfo=UTC),
    )
    assert all(
        {current_evidence.evidence_id}.issubset(
            {evidence.evidence_id for evidence in item.source_evidence}
        )
        for item in candidates
    )


def test_recovery_decision_brief_contract_validates_scores_and_usd_cost(
    valid_case_payload: dict[str, object],
) -> None:
    cost = RecommendationCostBreakdown(
        repair_labor_usd=Decimal("120.00"),
        sourcing_usd=Decimal("80.00"),
        operations_usd=Decimal("25.00"),
        total_usd=Decimal("225.00"),
    )
    scored_option = _scored_recovery_option(
        "case-synthetic-001-repair-original",
        Decimal("79"),
        kind=OptionKind.REPAIR_ORIGINAL,
        sourcing_method=CandidateSourcingMethod.INTERNAL_TRANSFER,
        cost=cost,
    )
    option = RankedRecoveryOption.model_validate({**scored_option.model_dump(), "rank": 1})
    brief = RecoveryDecisionBrief(
        schema_version="1.0",
        recommendation_version="recovery-v1-test",
        scoring_algorithm_version="weights-v1",
        case_id=valid_case_payload["case_id"],
        trace_context=valid_case_payload["trace_context"],
        status=RecommendationStatus.RECOMMENDED,
        summary="Repair is the highest-scoring eligible option.",
        ranked_options=(option,),
        excluded_options=(),
        unscored_options=(),
        weights=RecommendationWeights(),
        confidence=assess_confidence(0.8, (), ()),
        human_gate=HumanGateAssessment(
            status=HumanGateStatus.PENDING,
            required_roles=(ReviewerRole.OPS_LEAD, ReviewerRole.MAINTENANCE_AIRWORTHINESS),
            approved_roles=(),
            findings=(),
        ),
        requires_human_selection=False,
        required_human_action="Both required reviewers must approve before action.",
        assumptions=(),
        risks=(),
        warnings=(),
        conflicts=(),
        unknowns=(),
        missing_data=(),
        errors=(),
    )

    assert brief.weights.speed == Decimal("0.30")
    assert brief.ranked_options[0].cost.total_usd == Decimal("225.00")
    assert brief.ranked_options[0].aggregate_score == Decimal("79")

    with pytest.raises(ValidationError, match="evidence_references"):
        RankedRecoveryOption.model_validate({**option.model_dump(), "evidence_references": ()})
    with pytest.raises(ValidationError, match="recommendation_version"):
        RecoveryDecisionBrief.model_validate({"schema_version": "1.0"})

    with pytest.raises(ValidationError, match="sum of cost components"):
        RecommendationCostBreakdown(
            repair_labor_usd=Decimal("120"),
            sourcing_usd=Decimal("80"),
            operations_usd=Decimal("25"),
            total_usd=Decimal("224"),
        )


def test_recommendation_contract_rejects_nonbaseline_weights_and_out_of_range_scores() -> None:
    with pytest.raises(ValidationError, match="30/30/30/10 baseline"):
        RecommendationWeights(
            speed=Decimal("0.40"),
            operational_package_impact=Decimal("0.30"),
            risk=Decimal("0.20"),
            cost=Decimal("0.10"),
        )

    with pytest.raises(ValidationError):
        RecommendationFactorScores(
            speed=Decimal("100.01"),
            operational_package_impact=Decimal("80"),
            risk=Decimal("70"),
            cost=Decimal("60"),
        )


def test_recovery_decision_brief_rejects_duplicate_and_unknown_option_fields(
    valid_case_payload: dict[str, object],
) -> None:
    payload = {
        "schema_version": "1.0",
        "recommendation_version": "recovery-v1-test",
        "scoring_algorithm_version": "weights-v1",
        "case_id": valid_case_payload["case_id"],
        "trace_context": valid_case_payload["trace_context"],
        "status": RecommendationStatus.AWAITING_ADDITIONAL_DATA,
        "summary": "No option can be scored yet.",
        "ranked_options": (),
        "excluded_options": (
            ExcludedRecoveryOption(
                option_id="same-option",
                kind=OptionKind.REPAIR_ALTERNATE,
                description="Repair using an alternate part",
                exclusion_reasons=("Part authorization is unavailable",),
            ),
        ),
        "unscored_options": (),
        "weights": RecommendationWeights(),
        "confidence": assess_confidence(0.4, (), ()),
        "human_gate": HumanGateAssessment(
            status=HumanGateStatus.PENDING,
            required_roles=(ReviewerRole.OPS_LEAD, ReviewerRole.MAINTENANCE_AIRWORTHINESS),
            approved_roles=(),
            findings=(),
        ),
        "requires_human_selection": False,
        "required_human_action": "Escalate for missing authorization evidence.",
        "assumptions": (),
        "risks": (),
        "warnings": (),
        "conflicts": (),
        "unknowns": (),
        "missing_data": (),
        "errors": (),
    }
    payload["unscored_options"] = (
        {
            "option_id": "same-option",
            "kind": OptionKind.REPAIR_ALTERNATE,
            "description": "Repair using an alternate part",
            "reasons": ("Risk evidence is missing",),
        },
    )

    with pytest.raises(ValidationError, match="option IDs must be unique"):
        RecoveryDecisionBrief.model_validate(payload)

    payload["unscored_options"] = ()
    payload["untrusted_extra"] = "must be rejected"
    with pytest.raises(ValidationError, match="untrusted_extra"):
        RecoveryDecisionBrief.model_validate(payload)


def test_case_relative_normalization_handles_single_equal_and_opposed_values() -> None:
    assert normalize_relative({"single": Decimal("5")}, lower_is_better=True) == {
        "single": Decimal("100")
    }
    assert normalize_relative(
        {"first": Decimal("5"), "second": Decimal("5")},
        lower_is_better=False,
    ) == {"first": Decimal("100"), "second": Decimal("100")}
    assert normalize_relative(
        {"fast": Decimal("5"), "slow": Decimal("15")},
        lower_is_better=True,
    ) == {"fast": Decimal("100"), "slow": Decimal("0")}


def test_ranking_is_stable_and_close_score_threshold_is_inclusive() -> None:
    def scored(option_id: str, value: str) -> ScoredRecoveryOption:
        return _scored_recovery_option(option_id, Decimal(value))

    options = (scored("option-c", "87.99"), scored("option-b", "88"), scored("option-a", "90"))
    ranking = rank_options(options)
    repeated = rank_options(tuple(reversed(options)))

    assert tuple(item.option_id for item in ranking.ranked_options) == (
        "option-a",
        "option-b",
        "option-c",
    )
    assert ranking == repeated
    assert ranking.requires_human_selection
    assert tuple(item.selection_group for item in ranking.ranked_options) == (1, 1, None)


def test_ranking_handles_ties_and_single_option_without_false_close_selection() -> None:
    option = _scored_recovery_option("option-z", Decimal("95"))

    single = rank_options((option,))
    tie = rank_options((option, option.model_copy(update={"option_id": "option-a"})))

    assert not single.requires_human_selection
    assert single.ranked_options[0].selection_group is None
    assert tie.requires_human_selection
    assert tuple(item.option_id for item in tie.ranked_options) == ("option-a", "option-z")
    assert all(item.selection_group == 1 for item in tie.ranked_options)
