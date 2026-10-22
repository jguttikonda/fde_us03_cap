from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceConflict, EvidenceValidity
from aog_recovery.contracts.governance import ReviewerRole
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.compliance import build_unranked_handoff
from aog_recovery.controller.context import ControllerAuditRecorder, InMemoryControllerContextStore
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    PerCandidateResult,
    WorkflowStatus,
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
from aog_recovery.operations.models import OperationsRequest, OptionKind, PackageLoadData
from aog_recovery.operations.synthetic import default_adapters
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
    assert handoff.confidence.confidence >= 0.70
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
