import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

import aog_recovery.controller.recommendation as recommendation_module
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceConflict, EvidenceValidity
from aog_recovery.contracts.governance import (
    HumanDecisionRecord,
    HumanDecisionType,
    ReviewerRole,
)
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.compliance import build_unranked_handoff
from aog_recovery.controller.context import ControllerAuditRecorder, InMemoryControllerContextStore
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    PerCandidateResult,
    RecommendationStatus,
    WorkflowStatus,
)
from aog_recovery.controller.recommendation import apply_human_decisions, build_recommendation
from aog_recovery.controller.scoring import (
    CandidateScoringResult,
    score_candidates,
    score_maintenance_risk,
    score_operational_package_impact,
)
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentPayload,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RepairabilityStatus,
)
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
    PartEligibilityEvidence,
    SourcingMethod,
    SourcingOption,
    TraceabilityStatus,
)
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import (
    ImpactLevel,
    OperationsRequest,
    OptionKind,
    PackageLoadData,
)
from aog_recovery.operations.synthetic import default_adapters
from aog_recovery.validation.confidence import ConfidenceDisposition
from aog_recovery.validation.human_gate import HumanGateStatus

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def make_case() -> AogCase:
    return AogCase(
        case_id="case-controller-compliance-001",
        aircraft_id="N123AB",
        event_type="synthetic_aog",
        defect_summary="Synthetic pump defect",
        location="TEST-STATION-A",
        event_at=NOW,
        created_at=NOW,
        schema_version="1.0",
        trace_context=TraceContext(
            trace_id="trace-controller-001",
            correlation_id="corr-controller-001",
        ),
    )


def build_result(
    authorization: AuthorizationStatus,
    traceability: TraceabilityStatus = TraceabilityStatus.VERIFIED,
    approval: ApprovalEvidenceStatus = ApprovalEvidenceStatus.APPROVAL_RECORDED,
) -> tuple[AogCase, PerCandidateResult]:
    case = make_case()
    evidence = tuple(
        Evidence(
            evidence_id=evidence_id,
            source=f"synthetic-{evidence_id}",
            retrieved_at=NOW,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference=evidence_id,
            content={"verified": True},
        )
        for evidence_id in (
            "approval-evidence-001",
            "part-eligibility-001",
            "eta-evidence-001",
            "load-evidence-001",
        )
    )
    sourcing = SourcingOption(
        part_number="P-120",
        source="synthetic-station",
        source_location="TEST-STATION-B",
        method=SourcingMethod.INTERNAL_TRANSFER,
        shipping_provider=None,
        shipping_service=None,
        transfer_required=True,
        lead_time_hours=2.0,
        eta_at=NOW,
        estimated_cost_usd=Decimal("100.00"),
        quote_unavailable_reason=None,
        evidence_references=("part-eligibility-001",),
    )
    source = CandidateSource(
        source_key="repair-preferred-p120",
        kind=OptionKind.REPAIR_ALTERNATE,
        failed_part_number="P-110",
        source_evidence_references=tuple(item.evidence_id for item in evidence),
        readiness=ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=NOW,
            basis=EtaBasis.CONFIRMED,
            evidence_references=("eta-evidence-001",),
        ),
        sourcing_options=(sourcing,),
        package_load=PackageLoadData(groups=()),
        package_load_evidence_references=("load-evidence-001",),
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=case,
        evidence=evidence,
        affected_flight_numbers=("FX103",),
        candidate_sources=(source,),
    )
    candidate = build_candidates(intake)[0]

    approval_recorded = approval is ApprovalEvidenceStatus.APPROVAL_RECORDED
    maintenance_payload = MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=(
            RepairabilityStatus.FEASIBLE if approval_recorded else RepairabilityStatus.UNCERTAIN
        ),
        root_cause=None,
        recurring_failure=None,
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("part-eligibility-001",),
        required_actions=("replace_pump",),
        estimated_ground_time_hours=2.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("125.00"),
        need_by_time=None,
        parts_ready_at=NOW,
        return_to_service_time=NOW,
        meets_need_by_time=None,
        eta_confidence=0.95,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.LOW,
            parts_dependency_risk=MaintenanceRiskLevel.LOW,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=approval,
            approver_role="maintenance_airworthiness_authority" if approval_recorded else None,
            source_reference="approval-evidence-001" if approval_recorded else None,
            recorded_at=NOW if approval_recorded else None,
        ),
        recommendation=MaintenanceRecommendation(
            decision=(
                MaintenanceRecommendationDecision.REPAIR
                if approval_recorded
                else MaintenanceRecommendationDecision.UNCERTAIN
            ),
            confidence=0.95,
            rationale="Synthetic repair assessment",
            next_steps=(),
        ),
    )
    materials_payload = MaterialsLogisticsAgentPayload(
        schema_version="1.0",
        assessment=MaterialsLogisticsAssessmentPayload(
            schema_version="1.0",
            availability_status=AvailabilityStatus.AVAILABLE,
            part_availability=(),
            part_eligibility=(
                PartEligibilityEvidence(
                    part_number="P-120",
                    compatibility=CompatibilityStatus.COMPATIBLE,
                    authorization=authorization,
                    traceability=traceability,
                    checked_by_role="materials_inventory_specialist",
                    evidence_references=("part-eligibility-001",),
                ),
            ),
            sourcing_options=(sourcing,),
            confidence=0.95,
            risk_factors=(),
            assumptions=(),
            missing_data=(),
        ),
        evidence_summary=MaterialsEvidenceSummary(
            status=ToolResultStatus.SUCCESS,
            confidence=0.95,
            evidence_references=("part-eligibility-001",),
            warnings=(),
            errors=(),
        ),
    )
    maintenance_result = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MAINTENANCE,
        status=AgentResultStatus.COMPLETE,
        summary="Synthetic repair assessment",
        confidence=0.95,
        assumptions=(),
        evidence_references=("approval-evidence-001", "eta-evidence-001"),
        role_payload=maintenance_payload.model_dump(mode="json"),
    )
    materials_result = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MATERIALS_LOGISTICS,
        status=AgentResultStatus.COMPLETE,
        summary="Synthetic sourcing assessment",
        confidence=0.95,
        assumptions=(),
        evidence_references=("part-eligibility-001",),
        role_payload=materials_payload.model_dump(mode="json"),
    )
    operations_request = OperationsRequest(
        schema_version="1.0",
        request_id=f"{candidate.candidate.option_id}:operations",
        case=case,
        affected_flight_numbers=("FX103",),
        candidates=(candidate.candidate,),
        evaluated_at=NOW,
    )
    operations_result = OperationsAgent(default_adapters()).assess(operations_request)
    return case, PerCandidateResult(
        candidate=candidate.candidate,
        candidate_source=candidate.source,
        maintenance_result=maintenance_result,
        materials_logistics_result=materials_result,
        operations_result=operations_result,
        peer_exchange_recording=None,
        confidence=None,
        status=WorkflowStatus.IN_PROGRESS,
        evidence=evidence,
        warnings=(),
        conflicts=(),
        unknowns=(),
        missing_data=(),
        errors=(),
    )


def test_compliant_repair_is_unranked_and_still_requires_human_approval() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    store = InMemoryControllerContextStore()

    handoff = build_unranked_handoff(
        case,
        (result,),
        audit_recorder=ControllerAuditRecorder(store),
        occurred_at=NOW,
    )

    assert handoff.candidates[0].eligible
    assert handoff.candidates[0].exclusion_reasons == ()
    assert handoff.human_gate.status is HumanGateStatus.PENDING
    assert handoff.human_gate.required_roles == (
        ReviewerRole.OPS_LEAD,
        ReviewerRole.MAINTENANCE_AIRWORTHINESS,
    )
    assert 0.50 <= handoff.confidence.confidence < 0.70
    assert handoff.confidence.disposition is ConfidenceDisposition.PROVISIONAL
    assert not hasattr(handoff.candidates[0], "score")
    assert not hasattr(handoff.candidates[0], "rank")
    assert not hasattr(handoff, "recommended_winner")
    assert not any(
        hasattr(handoff, action) for action in ("book", "purchase", "transfer", "dispatch")
    )
    assert [event.event_type for event in store.events_for(case.case_id)] == [
        "controller_aggregation",
        "controller_handoff",
    ]
    assert all(
        event.trace_context == case.trace_context for event in store.events_for(case.case_id)
    )


@pytest.mark.parametrize(
    ("authorization", "traceability", "approval", "reason_fragment"),
    [
        (
            AuthorizationStatus.UNKNOWN,
            TraceabilityStatus.VERIFIED,
            ApprovalEvidenceStatus.APPROVAL_RECORDED,
            "authorization is unknown",
        ),
        (
            AuthorizationStatus.UNAUTHORIZED,
            TraceabilityStatus.VERIFIED,
            ApprovalEvidenceStatus.APPROVAL_RECORDED,
            "authorization is unauthorized",
        ),
        (
            AuthorizationStatus.AUTHORIZED,
            TraceabilityStatus.NOT_VERIFIED,
            ApprovalEvidenceStatus.APPROVAL_RECORDED,
            "traceability is not_verified",
        ),
        (
            AuthorizationStatus.AUTHORIZED,
            TraceabilityStatus.VERIFIED,
            ApprovalEvidenceStatus.PENDING,
            "Engineering approval is pending",
        ),
    ],
)
def test_compliance_gate_excludes_unknown_or_failed_authorization(
    authorization: AuthorizationStatus,
    traceability: TraceabilityStatus,
    approval: ApprovalEvidenceStatus,
    reason_fragment: str,
) -> None:
    case, result = build_result(authorization, traceability, approval)

    handoff = build_unranked_handoff(case, (result,))

    candidate = handoff.candidates[0]
    assert not candidate.eligible
    assert any(reason_fragment in reason for reason in candidate.exclusion_reasons)
    assert handoff.human_gate.status is HumanGateStatus.PENDING


def test_failed_materials_result_cannot_clear_compliance_gate() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    failed_materials_result = result.materials_logistics_result.model_copy(
        update={
            "status": AgentResultStatus.FAILED,
            "confidence": 0.0,
            "role_payload": {
                "error": {
                    "schema_version": "1.0",
                    "category": "materials_source_unavailable",
                    "component": "materials-logistics-agent",
                    "message": "Synthetic authorization source unavailable",
                    "retryable": False,
                    "case_impact": "Part authorization could not be verified",
                }
            },
        }
    )
    result = result.model_copy(update={"materials_logistics_result": failed_materials_result})

    handoff = build_unranked_handoff(case, (result,))

    candidate = handoff.candidates[0]
    assert not candidate.eligible
    assert any("results are unavailable" in reason for reason in candidate.exclusion_reasons)
    assert handoff.human_gate.status is HumanGateStatus.PENDING


def test_conflict_and_handoff_audit_events_are_correlated() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    conflict = EvidenceConflict(
        conflict_id="conflict-controller-001",
        claim_reference="readiness-estimate",
        evidence_references=("eta-evidence-001", "approval-evidence-001"),
        description="Synthetic specialist findings conflict",
    )
    result = result.model_copy(update={"conflicts": (conflict,)})
    store = InMemoryControllerContextStore()

    handoff = build_unranked_handoff(
        case,
        (result,),
        audit_recorder=ControllerAuditRecorder(store),
        occurred_at=NOW,
    )
    events = store.events_for(case.case_id)

    assert [event.event_type for event in events] == [
        "controller_aggregation",
        "controller_conflict",
        "controller_handoff",
    ]
    assert events[1].evidence_references == conflict.evidence_references
    assert events[1].trace_context.correlation_id == case.trace_context.correlation_id
    assert handoff.confidence.disposition.value == "escalation_required"


def test_handoff_audit_append_failure_is_visible_and_not_complete() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    failed_id = f"{case.case_id}:unranked-handoff"
    store = InMemoryControllerContextStore(fail_on_event_ids=frozenset({failed_id}))

    handoff = build_unranked_handoff(
        case,
        (result,),
        audit_recorder=ControllerAuditRecorder(store),
        occurred_at=NOW,
    )

    assert handoff.status is WorkflowStatus.PARTIAL
    assert handoff.human_gate.status is HumanGateStatus.PENDING
    assert any(error.category == "controller_audit_append_failed" for error in handoff.errors)


def test_high_confidence_handoff_still_requires_human_approval() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    operations_outcome = result.operations_result
    assessment = operations_outcome.assessment.model_copy(
        update={
            "confidence": 0.95,
            "confidence_disposition": ConfidenceDisposition.PREFERRED,
            "confidence_reasons": (),
        }
    )
    operations_result = operations_outcome.result.model_copy(
        update={"status": AgentResultStatus.COMPLETE, "confidence": 0.95}
    )
    operations_outcome = operations_outcome.model_copy(
        update={
            "result": operations_result,
            "assessment": assessment,
            "confidence": operations_outcome.confidence.model_copy(
                update={
                    "confidence": 0.95,
                    "disposition": ConfidenceDisposition.PREFERRED,
                }
            ),
        }
    )
    result = result.model_copy(update={"operations_result": operations_outcome})

    handoff = build_unranked_handoff(case, (result,))

    assert handoff.confidence.confidence >= 0.70
    assert handoff.human_gate.status is HumanGateStatus.PENDING


def test_recommendation_stage_scores_only_compliance_eligible_options() -> None:
    case, authorized_result = build_result(AuthorizationStatus.AUTHORIZED)
    _, unauthorized_result = build_result(AuthorizationStatus.UNAUTHORIZED)
    unauthorized_result = unauthorized_result.model_copy(
        update={
            "candidate": unauthorized_result.candidate.model_copy(
                update={"option_id": "case-controller-compliance-unauthorized"}
            )
        }
    )

    excluded_handoff = build_unranked_handoff(case, (unauthorized_result,))
    eligible_handoff = build_unranked_handoff(case, (authorized_result,))
    excluded_brief = build_recommendation(excluded_handoff)
    eligible_brief = build_recommendation(eligible_handoff)

    excluded_id = excluded_handoff.candidates[0].result.candidate.option_id
    assert excluded_brief.status is RecommendationStatus.REQUIRES_ESCALATION
    assert excluded_brief.ranked_options == ()
    assert excluded_brief.unscored_options == ()
    assert excluded_brief.excluded_options[0].option_id == excluded_id
    assert excluded_brief.excluded_options[0].exclusion_reasons
    assert all(item.option_id != excluded_id for item in excluded_brief.ranked_options)
    assert len(eligible_brief.ranked_options) == 1
    assert eligible_brief.excluded_options == ()
    ranked = eligible_brief.ranked_options[0]
    source_result = eligible_handoff.candidates[0].result
    assert ranked.readiness_eta == source_result.candidate.readiness_eta
    assert ranked.affected_routes == source_result.operations_result.assessment.affected_routes
    assert ranked.package.affected_package_count == 1200
    assert ranked.package.time_critical_package_count == 700
    assert ranked.package.allocations
    assert ranked.maintenance_risk_metrics.delay_risk is MaintenanceRiskLevel.LOW
    assert ranked.evidence_references
    assert ranked.cost.total_usd == Decimal("225.00")
    assert eligible_brief.assumptions
    assert eligible_brief.risks
    assert eligible_brief.confidence.disposition is ConfidenceDisposition.PROVISIONAL
    assert eligible_brief.human_gate.status is HumanGateStatus.PENDING
    assert "both required approvers" in eligible_brief.required_human_action
    assert ranked.option_id in eligible_brief.summary
    assert ranked.trade_off in eligible_brief.summary


def test_decision_brief_close_scores_require_human_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    handoff = build_unranked_handoff(case, (result,))
    base = score_candidates(case, handoff.candidates).scored_options[0]
    leading_factor_scores = base.factor_scores.model_copy(
        update={
            "speed": Decimal("90"),
            "operational_package_impact": Decimal("90"),
            "risk": Decimal("90"),
            "cost": Decimal("90"),
        }
    )
    leading = base.model_copy(
        update={
            "option_id": "close-option-a",
            "factor_scores": leading_factor_scores,
            "aggregate_score": Decimal("90"),
        }
    )
    close_factor_scores = leading.factor_scores.model_copy(
        update={
            "speed": Decimal("88"),
            "operational_package_impact": Decimal("88"),
            "risk": Decimal("88"),
            "cost": Decimal("88"),
        }
    )
    close = base.model_copy(
        update={
            "option_id": "close-option-b",
            "factor_scores": close_factor_scores,
            "aggregate_score": Decimal("88"),
        }
    )
    scores = CandidateScoringResult((leading, close), ())
    monkeypatch.setattr(
        recommendation_module,
        "score_candidates",
        lambda _case, _candidates: scores,
    )

    brief = recommendation_module.build_recommendation(handoff)

    assert brief.requires_human_selection
    assert tuple(option.selection_group for option in brief.ranked_options) == (1, 1)
    assert "human selection is required" in brief.summary
    assert "close-option-a" in brief.summary
    assert "close-option-b" in brief.summary
    assert "Select one close-scored option" in brief.required_human_action


def test_recommendation_preserves_degradation_conflicts_and_zero_scoreable_status() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    stale_result = result.model_copy(
        update={
            "evidence": tuple(
                item.model_copy(update={"validity_state": EvidenceValidity.STALE})
                for item in result.evidence
            )
        }
    )
    stale_brief = build_recommendation(build_unranked_handoff(case, (stale_result,)))
    assert stale_brief.status in {
        RecommendationStatus.PROVISIONAL,
        RecommendationStatus.REQUIRES_ESCALATION,
    }
    assert any(warning.code == "STALE_EVIDENCE" for warning in stale_brief.warnings)

    conflict = EvidenceConflict(
        conflict_id="conflict-recommendation-001",
        claim_reference="readiness-estimate",
        evidence_references=("eta-evidence-001", "part-eligibility-001"),
        description="Synthetic readiness evidence conflicts",
    )
    conflicting_result = result.model_copy(update={"conflicts": (conflict,)})
    conflict_brief = build_recommendation(build_unranked_handoff(case, (conflicting_result,)))
    assert conflict_brief.status is RecommendationStatus.REQUIRES_ESCALATION
    assert conflict_brief.conflicts == (conflict,)

    maintenance_payload = MaintenanceAssessmentPayload.model_validate_json(
        json.dumps(result.maintenance_result.role_payload)
    )
    maintenance_payload = maintenance_payload.model_copy(
        update={"estimated_repair_labor_cost_usd": None}
    )
    missing_cost_result = result.model_copy(
        update={
            "maintenance_result": result.maintenance_result.model_copy(
                update={"role_payload": maintenance_payload.model_dump(mode="json")}
            )
        }
    )
    missing_cost_brief = build_recommendation(build_unranked_handoff(case, (missing_cost_result,)))
    assert missing_cost_brief.status is RecommendationStatus.AWAITING_ADDITIONAL_DATA
    assert missing_cost_brief.ranked_options == ()
    assert missing_cost_brief.unscored_options[0].reasons == ("repair_labor_cost",)


def test_human_actions_update_only_advisory_report_state() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    brief = build_recommendation(build_unranked_handoff(case, (result,)))
    option_id = brief.ranked_options[0].option_id
    store = InMemoryControllerContextStore()
    audit_recorder = ControllerAuditRecorder(store)

    def human_decision(role: ReviewerRole, action: HumanDecisionType) -> HumanDecisionRecord:
        return HumanDecisionRecord(
            schema_version="1.0",
            decision_id=f"{action.value}-{role.value}",
            case_id=brief.case_id,
            decision=action,
            selected_action="repair",
            selected_option_id=option_id,
            reviewer_id=f"reviewer-{role.value}",
            reviewer_role=role,
            decided_at=NOW,
            rationale=f"Synthetic {action.value} decision",
            recommendation_version=brief.recommendation_version,
        )

    pending = apply_human_decisions(
        brief,
        (human_decision(ReviewerRole.OPS_LEAD, HumanDecisionType.APPROVE),),
        audit_recorder=audit_recorder,
    )
    assert pending.human_gate.status is HumanGateStatus.PENDING
    approved = apply_human_decisions(
        pending,
        (human_decision(ReviewerRole.MAINTENANCE_AIRWORTHINESS, HumanDecisionType.APPROVE),),
        audit_recorder=audit_recorder,
    )
    assert approved.status is RecommendationStatus.RESOLVED
    assert approved.human_gate.status is HumanGateStatus.APPROVED
    assert approved.human_gate.required_roles == (
        ReviewerRole.OPS_LEAD,
        ReviewerRole.MAINTENANCE_AIRWORTHINESS,
    )
    assert "no operational action was executed" in approved.required_human_action
    assert len(approved.human_decisions) == 2
    decision_events = tuple(
        event for event in store.events_for(brief.case_id) if event.event_type == "human_decision"
    )
    assert len(decision_events) == 2
    assert all(
        event.details["recommendation_version"] == brief.recommendation_version
        for event in decision_events
    )
    assert all(event.trace_context == brief.trace_context for event in decision_events)
    assert {event.details["reviewer_role"] for event in decision_events} == {
        ReviewerRole.OPS_LEAD.value,
        ReviewerRole.MAINTENANCE_AIRWORTHINESS.value,
    }
    assert all(event.occurred_at == NOW for event in decision_events)
    assert all(event.details["rationale"] for event in decision_events)
    assert all(decision.rationale for decision in approved.human_decisions)

    expected_statuses = {
        HumanDecisionType.REJECT: RecommendationStatus.REJECTED,
        HumanDecisionType.ESCALATE: RecommendationStatus.REQUIRES_ESCALATION,
        HumanDecisionType.REQUEST_INFORMATION: RecommendationStatus.AWAITING_ADDITIONAL_DATA,
    }
    for action, expected_status in expected_statuses.items():
        updated = apply_human_decisions(
            brief,
            (human_decision(ReviewerRole.OPS_LEAD, action),),
            audit_recorder=audit_recorder,
        )
        assert updated.status is expected_status
        assert "no operational action was executed" in updated.required_human_action
        assert not any(hasattr(updated, field) for field in ("execute", "dispatch", "purchase"))

    failed_decision = human_decision(ReviewerRole.OPS_LEAD, HumanDecisionType.APPROVE)
    failing_store = InMemoryControllerContextStore(
        fail_on_event_ids=frozenset(
            {f"{brief.case_id}:human-decision:{failed_decision.decision_id}"}
        )
    )
    failed_record = apply_human_decisions(
        brief,
        (failed_decision,),
        audit_recorder=ControllerAuditRecorder(failing_store),
    )
    assert failed_record.human_gate.status is HumanGateStatus.PENDING
    assert failed_record.status is RecommendationStatus.REQUIRES_ESCALATION
    assert failed_record.human_decisions == ()
    assert any(error.category == "controller_audit_append_failed" for error in failed_record.errors)


def test_scoring_uses_baseline_weights_and_sums_cost_components_once() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    handoff = build_unranked_handoff(case, (result,))

    scoring = score_candidates(case, handoff.candidates)

    assert len(scoring.scored_options) == 1
    assert scoring.unscored_options == ()
    score = scoring.scored_options[0]
    assert score.cost.repair_labor_usd == Decimal("125.00")
    assert score.cost.sourcing_usd == Decimal("100.00")
    assert score.cost.operations_usd == Decimal(
        result.operations_result.assessment.recovery_options[0].cost.total_usd
    )
    assert score.cost.total_usd == (
        score.cost.repair_labor_usd + score.cost.sourcing_usd + score.cost.operations_usd
    )
    assert score.factor_scores.speed == Decimal("100")
    assert score.factor_scores.operational_package_impact == Decimal("100")
    assert score.factor_scores.cost == Decimal("100")
    assert score.aggregate_score == (
        score.factor_scores.speed * Decimal("0.30")
        + score.factor_scores.operational_package_impact * Decimal("0.30")
        + score.factor_scores.risk * Decimal("0.30")
        + score.factor_scores.cost * Decimal("0.10")
    )
    assert score.factor_scores.risk == Decimal("100")


def test_individual_impact_package_and_risk_mappings_are_deterministic() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    maintenance = MaintenanceAssessmentPayload.model_validate_json(
        json.dumps(result.maintenance_result.role_payload)
    )
    operations = result.operations_result.assessment.recovery_options[0]

    assert score_maintenance_risk(maintenance) == Decimal("100")
    medium_risk = maintenance.model_copy(
        update={
            "risk_metrics": MaintenanceRiskMetrics(
                delay_risk=MaintenanceRiskLevel.MEDIUM,
                parts_dependency_risk=MaintenanceRiskLevel.MEDIUM,
                repair_complexity_risk=MaintenanceRiskLevel.MEDIUM,
            )
        }
    )
    assert score_maintenance_risk(medium_risk) == Decimal("50")
    high_risk = maintenance.model_copy(
        update={
            "risk_metrics": MaintenanceRiskMetrics(
                delay_risk=MaintenanceRiskLevel.HIGH,
                parts_dependency_risk=MaintenanceRiskLevel.HIGH,
                repair_complexity_risk=MaintenanceRiskLevel.HIGH,
            )
        }
    )
    assert score_maintenance_risk(high_risk) == Decimal("0")

    partial_package = operations.package.model_copy(
        update={"unprotected_count": 300, "unprotected_time_critical_count": 200}
    )
    medium_impact = operations.model_copy(
        update={"impact_level": ImpactLevel.MEDIUM, "package": partial_package}
    )
    package_score = Decimal("100") * (Decimal("1") - Decimal("500") / Decimal("1900"))
    assert score_operational_package_impact(medium_impact) == (
        Decimal("66.67") + package_score
    ) / Decimal("2")
    missing_package = operations.model_copy(
        update={"package": operations.package.model_copy(update={"unprotected_count": None})}
    )
    assert score_operational_package_impact(missing_package) is None


@pytest.mark.parametrize(
    ("update", "reason"),
    [
        ({"estimated_repair_labor_cost_usd": None}, "repair_labor_cost"),
        (
            {
                "risk_metrics": MaintenanceRiskMetrics(
                    delay_risk=MaintenanceRiskLevel.UNKNOWN,
                    parts_dependency_risk=MaintenanceRiskLevel.LOW,
                    repair_complexity_risk=MaintenanceRiskLevel.LOW,
                )
            },
            "maintenance_risk_unknown",
        ),
    ],
)
def test_scoring_keeps_missing_cost_and_unknown_risk_unscored(
    update: dict[str, object],
    reason: str,
) -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    maintenance_payload = MaintenanceAssessmentPayload.model_validate_json(
        json.dumps(result.maintenance_result.role_payload)
    )
    maintenance_payload = maintenance_payload.model_copy(update=update)
    maintenance_result = result.maintenance_result.model_copy(
        update={"role_payload": maintenance_payload.model_dump(mode="json")}
    )
    result = result.model_copy(update={"maintenance_result": maintenance_result})
    handoff = build_unranked_handoff(case, (result,))

    scoring = score_candidates(case, handoff.candidates)

    assert scoring.scored_options == ()
    assert len(scoring.unscored_options) == 1
    assert reason in scoring.unscored_options[0].reasons


def test_cost_changes_score_only_through_its_weight_and_scoring_is_reproducible() -> None:
    case, base_result = build_result(AuthorizationStatus.AUTHORIZED)

    def with_sourcing_cost(option_id: str, sourcing_cost: Decimal) -> PerCandidateResult:
        source_option = base_result.candidate_source.sourcing_options[0].model_copy(
            update={"estimated_cost_usd": sourcing_cost}
        )
        candidate = base_result.candidate.model_copy(update={"option_id": option_id})
        candidate_source = base_result.candidate_source.model_copy(
            update={"source_key": option_id, "sourcing_options": (source_option,)}
        )
        materials_payload = MaterialsLogisticsAgentPayload.model_validate_json(
            json.dumps(base_result.materials_logistics_result.role_payload)
        )
        materials_payload = materials_payload.model_copy(
            update={
                "assessment": materials_payload.assessment.model_copy(
                    update={"sourcing_options": (source_option,)}
                )
            }
        )
        materials_result = base_result.materials_logistics_result.model_copy(
            update={"role_payload": materials_payload.model_dump(mode="json")}
        )
        operations_outcome = base_result.operations_result
        operations_assessment = operations_outcome.assessment.model_copy(
            update={
                "recovery_options": tuple(
                    option.model_copy(update={"option_id": option_id})
                    for option in operations_outcome.assessment.recovery_options
                )
            }
        )
        operations_result = operations_outcome.result.model_copy(
            update={"role_payload": operations_assessment.model_dump(mode="json")}
        )
        operations_outcome = operations_outcome.model_copy(
            update={"result": operations_result, "assessment": operations_assessment}
        )
        return base_result.model_copy(
            update={
                "candidate": candidate,
                "candidate_source": candidate_source,
                "materials_logistics_result": materials_result,
                "operations_result": operations_outcome,
            }
        )

    handoff = build_unranked_handoff(
        case,
        (
            with_sourcing_cost("candidate-cheap", Decimal("100.00")),
            with_sourcing_cost("candidate-expensive", Decimal("500.00")),
        ),
    )

    first = score_candidates(case, handoff.candidates)
    repeated = score_candidates(case, handoff.candidates)
    scores = {option.option_id: option for option in first.scored_options}
    brief = build_recommendation(handoff)
    report_options = {option.option_id: option for option in brief.ranked_options}

    assert len(scores) == 2
    assert first == repeated
    assert scores["candidate-cheap"].factor_scores.cost == Decimal("100")
    assert scores["candidate-expensive"].factor_scores.cost == Decimal("0")
    assert scores["candidate-cheap"].aggregate_score - scores[
        "candidate-expensive"
    ].aggregate_score == Decimal("10.00")
    assert report_options["candidate-cheap"].cost.total_usd == Decimal("225.00")
    assert report_options["candidate-expensive"].cost.total_usd == Decimal("625.00")
    assert "estimated USD 225.00" in report_options["candidate-cheap"].trade_off


def test_recommendation_audit_events_are_versioned_redacted_and_case_correlated() -> None:
    case, authorized_result = build_result(AuthorizationStatus.AUTHORIZED)
    conflict = EvidenceConflict(
        conflict_id="conflict-audit-recommendation-001",
        claim_reference="readiness-estimate",
        evidence_references=("eta-evidence-001", "part-eligibility-001"),
        description="Synthetic readiness evidence requires adjudication",
    )
    authorized_result = authorized_result.model_copy(update={"conflicts": (conflict,)})
    _, unauthorized_result = build_result(AuthorizationStatus.UNAUTHORIZED)
    unauthorized_result = unauthorized_result.model_copy(
        update={
            "candidate": unauthorized_result.candidate.model_copy(
                update={"option_id": "case-controller-compliance-audit-excluded"}
            )
        }
    )
    handoff = build_unranked_handoff(case, (authorized_result, unauthorized_result))
    store = InMemoryControllerContextStore()

    brief = build_recommendation(
        handoff,
        audit_recorder=ControllerAuditRecorder(store),
        occurred_at=NOW,
    )
    events = store.events_for(case.case_id)
    event_types = {event.event_type for event in events}

    assert {
        "controller_option_scored",
        "controller_option_excluded",
        "controller_escalation",
        "controller_recommendation",
    }.issubset(event_types)
    assert all(event.trace_context == case.trace_context for event in events)
    assert all(
        event.details["recommendation_version"] == brief.recommendation_version for event in events
    )
    assert brief.status is RecommendationStatus.REQUIRES_ESCALATION
    assert brief.conflicts == (conflict,)
    serialized_details = json.dumps([event.details for event in events])
    assert "private_chain_of_thought" not in serialized_details
    assert "synthetic-maintenance-system" not in serialized_details


def test_recommendation_audit_failure_is_visible_and_escalated() -> None:
    case, result = build_result(AuthorizationStatus.AUTHORIZED)
    handoff = build_unranked_handoff(case, (result,))
    baseline_store = InMemoryControllerContextStore()
    build_recommendation(
        handoff,
        audit_recorder=ControllerAuditRecorder(baseline_store),
        occurred_at=NOW,
    )
    failed_event_id = next(
        event.event_id
        for event in baseline_store.events_for(case.case_id)
        if event.event_type == "controller_recommendation"
    )
    failing_store = InMemoryControllerContextStore(fail_on_event_ids=frozenset({failed_event_id}))

    failed = build_recommendation(
        handoff,
        audit_recorder=ControllerAuditRecorder(failing_store),
        occurred_at=NOW,
    )

    assert failed.status is RecommendationStatus.REQUIRES_ESCALATION
    assert any(error.category == "controller_audit_append_failed" for error in failed.errors)
    assert "audit persistence failed" in failed.required_human_action
