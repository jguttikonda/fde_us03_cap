import asyncio
from datetime import UTC, datetime

import pytest

from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.aggregation import aggregate_candidate_result
from aog_recovery.controller.candidates import CandidateDefinition, build_candidates
from aog_recovery.controller.context import (
    ContextDirection,
    ControllerAuditRecorder,
    ControllerCaseContextRecorder,
    InMemoryControllerContextStore,
)
from aog_recovery.controller.intake import prepare_intake
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    PerCandidateResult,
    WorkflowStatus,
)
from aog_recovery.controller.orchestration import (
    CandidateSpecialistRequest,
    assess_candidate_specialists,
    assess_operations_candidates,
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
    AvailabilityStatus,
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
)
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import (
    OperationsOutcome,
    OperationsRequest,
    OptionKind,
    PackageLoadData,
)
from aog_recovery.operations.synthetic import default_adapters, default_case

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def routing_for(intake: ControllerIntake):
    result = prepare_intake(intake.model_dump(mode="json"), validated_at=NOW)
    assert result.routing is not None
    return result.routing


class InvocationBarrier:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.ready = asyncio.Event()

    async def wait_for_peer(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.active == 2:
            self.ready.set()
        try:
            await asyncio.wait_for(self.ready.wait(), timeout=0.2)
        finally:
            self.active -= 1


class FakeSpecialist:
    def __init__(
        self,
        role: AgentRole,
        result_status: AgentResultStatus,
        role_payload: dict[str, object],
        evidence_id: str,
        *,
        barrier: InvocationBarrier | None = None,
        timeout_kind: OptionKind | None = None,
    ) -> None:
        self.role = role
        self.result_status = result_status
        self.role_payload = role_payload
        self.evidence_id = evidence_id
        self.barrier = barrier
        self.timeout_kind = timeout_kind
        self.calls: list[CandidateSpecialistRequest] = []

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        self.calls.append(request)
        if self.barrier is not None:
            await self.barrier.wait_for_peer()
        if request.candidate.candidate.kind is self.timeout_kind:
            await asyncio.Event().wait()
        return AgentResult(
            schema_version="1.0",
            agent_role=self.role,
            status=self.result_status,
            summary="Synthetic specialist result",
            confidence=0.68,
            assumptions=(),
            evidence_references=(self.evidence_id,),
            role_payload=self.role_payload,
        )


def maintenance_payload() -> MaintenanceAssessmentPayload:
    return MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.UNCERTAIN,
        root_cause=None,
        recurring_failure=None,
        preferred_replacement_part=None,
        preferred_replacement_evidence_references=(),
        required_actions=(),
        estimated_ground_time_hours=None,
        ground_time_unavailable_reason="synthetic estimate unavailable",
        estimated_repair_labor_cost_usd=None,
        need_by_time=None,
        parts_ready_at=None,
        return_to_service_time=None,
        meets_need_by_time=None,
        eta_confidence=0.62,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.UNKNOWN,
            parts_dependency_risk=MaintenanceRiskLevel.UNKNOWN,
            repair_complexity_risk=MaintenanceRiskLevel.UNKNOWN,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=("ground time",),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.UNKNOWN,
            approver_role=None,
            source_reference=None,
            recorded_at=None,
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.UNCERTAIN,
            confidence=0.62,
            rationale="Synthetic assessment is incomplete",
            next_steps=(),
        ),
    )


def materials_payload(evidence_id: str) -> MaterialsLogisticsAgentPayload:
    assessment = MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.UNCERTAIN,
        part_availability=(),
        part_eligibility=(),
        sourcing_options=(),
        confidence=0.60,
        risk_factors=(),
        assumptions=(),
        missing_data=("inventory",),
    )
    summary = MaterialsEvidenceSummary(
        status=ToolResultStatus.PARTIAL,
        confidence=0.60,
        evidence_references=(evidence_id,),
        warnings=(),
        errors=(),
    )
    return MaterialsLogisticsAgentPayload(
        schema_version="1.0", assessment=assessment, evidence_summary=summary
    )


def make_intake(valid_case, current_evidence: Evidence) -> ControllerIntake:
    readiness = ReadinessEstimate(
        source_agent=AgentRole.MAINTENANCE,
        eta=NOW,
        basis=EtaBasis.ESTIMATED,
        evidence_references=(current_evidence.evidence_id,),
    )
    return ControllerIntake(
        schema_version="1.0",
        case=valid_case,
        evidence=(current_evidence,),
        candidate_sources=(
            CandidateSource(
                source_key="repair-original",
                kind=OptionKind.REPAIR_ORIGINAL,
                failed_part_number="P-110",
                source_evidence_references=(current_evidence.evidence_id,),
                readiness=readiness,
                package_load=PackageLoadData(groups=()),
                package_load_evidence_references=(current_evidence.evidence_id,),
            ),
            CandidateSource(
                source_key="aircraft-swap",
                kind=OptionKind.SWAP,
                source_evidence_references=(current_evidence.evidence_id,),
                readiness=readiness,
                package_load=PackageLoadData(groups=()),
                package_load_evidence_references=(current_evidence.evidence_id,),
            ),
        ),
    )


def specialist_port(
    role: AgentRole,
    payload: dict[str, object],
    evidence_id: str,
    *,
    status: AgentResultStatus = AgentResultStatus.COMPLETE,
    barrier: InvocationBarrier | None = None,
    timeout_kind: OptionKind | None = None,
) -> FakeSpecialist:
    return FakeSpecialist(
        role,
        status,
        payload,
        evidence_id,
        barrier=barrier,
        timeout_kind=timeout_kind,
    )


def per_candidate_result(
    candidate: CandidateDefinition,
    evidence: Evidence,
) -> PerCandidateResult:
    return PerCandidateResult(
        candidate=candidate.candidate,
        candidate_source=candidate.source,
        maintenance_result=AgentResult(
            schema_version="1.0",
            agent_role=AgentRole.MAINTENANCE,
            status=AgentResultStatus.COMPLETE,
            summary="Synthetic maintenance result",
            confidence=0.8,
            assumptions=(),
            evidence_references=(evidence.evidence_id,),
            role_payload=maintenance_payload().model_dump(mode="json"),
        ),
        materials_logistics_result=AgentResult(
            schema_version="1.0",
            agent_role=AgentRole.MATERIALS_LOGISTICS,
            status=AgentResultStatus.COMPLETE,
            summary="Synthetic materials result",
            confidence=0.8,
            assumptions=(),
            evidence_references=(evidence.evidence_id,),
            role_payload=materials_payload(evidence.evidence_id).model_dump(mode="json"),
        ),
        operations_result=None,
        peer_exchange_recording=None,
        confidence=None,
        status=WorkflowStatus.IN_PROGRESS,
        evidence=(evidence,),
        warnings=(),
        conflicts=(),
        unknowns=(),
        missing_data=candidate.missing_data,
        errors=(),
    )


class RecordingOperationsPort:
    def __init__(self) -> None:
        self.agent = OperationsAgent(default_adapters())
        self.requests: list[OperationsRequest] = []

    def assess(self, request: OperationsRequest) -> OperationsOutcome:
        self.requests.append(request)
        return self.agent.assess(request)


@pytest.mark.asyncio
async def test_specialists_overlap_and_h3_h4_is_recorded_in_order(
    valid_case,
    current_evidence: Evidence,
) -> None:
    intake = make_intake(valid_case, current_evidence)
    candidates = build_candidates(intake)
    barrier = InvocationBarrier()
    maintenance = specialist_port(
        AgentRole.MAINTENANCE,
        maintenance_payload().model_dump(mode="json"),
        current_evidence.evidence_id,
        status=AgentResultStatus.PARTIAL,
        barrier=barrier,
    )
    materials = specialist_port(
        AgentRole.MATERIALS_LOGISTICS,
        materials_payload(current_evidence.evidence_id).model_dump(mode="json"),
        current_evidence.evidence_id,
        status=AgentResultStatus.PARTIAL,
        barrier=barrier,
    )
    store = InMemoryControllerContextStore()

    results = await assess_candidate_specialists(
        intake,
        (candidates[0],),
        maintenance,
        materials,
        ControllerCaseContextRecorder(store),
        routing=routing_for(intake),
        settings=AogSettings(agent_timeout_seconds=1),
        clock=lambda: NOW,
        audit_recorder=ControllerAuditRecorder(store),
    )

    assert barrier.max_active == 2
    assert maintenance.calls[0].request_id.endswith(":maintenance")
    assert materials.calls[0].request_id.endswith(":materials-logistics")
    assert results[0].peer_exchange_recording is not None
    events = store.events_for(intake.case.case_id)
    assert [
        event.direction for event in events if event.direction is not ContextDirection.EVENT
    ] == [
        ContextDirection.REQUEST,
        ContextDirection.RESPONSE,
    ]
    assert [event.event_type for event in events] == [
        "specialist_invocation",
        "specialist_invocation",
        "specialist_result",
        "specialist_result",
        "peer_exchange",
        "peer_exchange",
    ]
    assert all(event.trace_context == intake.case.trace_context for event in events)
    assert results[0].status is WorkflowStatus.PARTIAL


@pytest.mark.asyncio
async def test_timeout_is_visible_and_does_not_erase_another_candidate(
    valid_case,
    current_evidence: Evidence,
) -> None:
    intake = make_intake(valid_case, current_evidence)
    candidates = build_candidates(intake)
    maintenance = specialist_port(
        AgentRole.MAINTENANCE,
        maintenance_payload().model_dump(mode="json"),
        current_evidence.evidence_id,
        timeout_kind=OptionKind.REPAIR_ORIGINAL,
    )
    materials = specialist_port(
        AgentRole.MATERIALS_LOGISTICS,
        materials_payload(current_evidence.evidence_id).model_dump(mode="json"),
        current_evidence.evidence_id,
    )
    audit_store = InMemoryControllerContextStore()

    results = await assess_candidate_specialists(
        intake,
        candidates,
        maintenance,
        materials,
        ControllerCaseContextRecorder(audit_store),
        routing=routing_for(intake),
        settings=AogSettings(agent_timeout_seconds=1),
        clock=lambda: NOW,
        audit_recorder=ControllerAuditRecorder(audit_store),
    )
    by_kind = {result.candidate.kind: result for result in results}

    assert by_kind[OptionKind.REPAIR_ORIGINAL].status is WorkflowStatus.PARTIAL
    assert by_kind[OptionKind.REPAIR_ORIGINAL].maintenance_result.status is AgentResultStatus.FAILED
    assert any(
        error.category == "specialist_timeout"
        for error in by_kind[OptionKind.REPAIR_ORIGINAL].errors
    )
    assert any(
        event.event_type == "specialist_timeout"
        and event.trace_context == intake.case.trace_context
        for event in audit_store.events_for(intake.case.case_id)
    )
    assert by_kind[OptionKind.SWAP].status is WorkflowStatus.PARTIAL
    assert by_kind[OptionKind.SWAP].maintenance_result.status is AgentResultStatus.COMPLETE
    assert any(
        missing.startswith("source_health:specialist:")
        for missing in by_kind[OptionKind.SWAP].missing_data
    )


def test_operations_runs_once_per_candidate_and_retains_domain_outcomes(
    current_evidence: Evidence,
) -> None:
    case = default_case()
    intake = ControllerIntake(
        schema_version="1.0",
        case=case,
        evidence=(current_evidence,),
        affected_flight_numbers=("FX103",),
        candidate_sources=(
            CandidateSource(
                source_key="delay-no-eta",
                kind=OptionKind.DELAY,
                source_evidence_references=(current_evidence.evidence_id,),
            ),
            CandidateSource(
                source_key="swap-with-readiness",
                kind=OptionKind.SWAP,
                source_evidence_references=(current_evidence.evidence_id,),
                readiness=ReadinessEstimate(
                    source_agent=AgentRole.MAINTENANCE,
                    eta=NOW,
                    basis=EtaBasis.CONFIRMED,
                    evidence_references=(current_evidence.evidence_id,),
                ),
            ),
        ),
    )
    candidates = build_candidates(intake)
    initial_results = tuple(
        per_candidate_result(candidate, current_evidence) for candidate in candidates
    )
    operations = RecordingOperationsPort()
    audit_store = InMemoryControllerContextStore()

    results = assess_operations_candidates(
        intake,
        initial_results,
        operations,
        clock=lambda: NOW,
        audit_recorder=ControllerAuditRecorder(audit_store),
    )
    by_kind = {result.candidate.kind: result for result in results}

    assert len(operations.requests) == 2
    assert all(len(request.candidates) == 1 for request in operations.requests)
    missing_eta_request = next(
        request for request in operations.requests if request.candidates[0].kind is OptionKind.DELAY
    )
    assert missing_eta_request.candidates[0].readiness_eta is None
    assert "readiness_eta" in by_kind[OptionKind.DELAY].missing_data
    assert by_kind[OptionKind.DELAY].operations_result is not None
    assert by_kind[OptionKind.SWAP].operations_result is not None
    assert by_kind[OptionKind.SWAP].operations_result.assessment is not None
    swap_assessment = by_kind[OptionKind.SWAP].operations_result.assessment.recovery_options[0]
    assert swap_assessment.package.assessed
    assert swap_assessment.cost is not None
    assert not hasattr(by_kind[OptionKind.SWAP].candidate, "score")
    assert not hasattr(by_kind[OptionKind.SWAP].candidate, "rank")
    audit_events = audit_store.events_for(intake.case.case_id)
    assert [event.event_type for event in audit_events] == [
        "operations_invocation",
        "operations_result",
        "operations_invocation",
        "operations_result",
    ]


def _with_operations_result(
    intake: ControllerIntake,
    candidate_result: PerCandidateResult,
) -> PerCandidateResult:
    outcome = OperationsAgent(default_adapters()).assess(
        OperationsRequest(
            schema_version="1.0",
            request_id=f"{candidate_result.candidate.option_id}:operations",
            case=intake.case,
            affected_flight_numbers=("FX103",),
            candidates=(candidate_result.candidate,),
            evaluated_at=NOW,
        )
    )
    return candidate_result.model_copy(update={"operations_result": outcome})


def test_aggregation_rejects_unavailable_evidence_references_and_escalates(
    current_evidence: Evidence,
) -> None:
    intake = ControllerIntake(
        schema_version="1.0",
        case=default_case(),
        evidence=(current_evidence,),
        affected_flight_numbers=("FX103",),
        candidate_sources=(
            CandidateSource(
                source_key="swap",
                kind=OptionKind.SWAP,
                source_evidence_references=(current_evidence.evidence_id,),
            ),
        ),
    )
    candidate = build_candidates(intake)[0]
    result = per_candidate_result(candidate, current_evidence)
    result = _with_operations_result(
        intake,
        result.model_copy(
            update={
                "maintenance_result": result.maintenance_result.model_copy(
                    update={"evidence_references": ("not-in-case-context",)}
                )
            }
        ),
    )

    aggregate = aggregate_candidate_result(result)

    assert aggregate.confidence is not None
    assert aggregate.confidence.confidence <= 0.69
    assert aggregate.status is WorkflowStatus.ESCALATION_REQUIRED
    assert any(
        error.category == "specialist_result_validation_failed" for error in aggregate.errors
    )
    assert any("evidence_references" in unknown.claim_reference for unknown in aggregate.unknowns)


def test_aggregation_preserves_conflicts_and_is_deterministic(
    current_evidence: Evidence,
) -> None:
    second_evidence = current_evidence.model_copy(
        update={
            "evidence_id": "evidence-synthetic-conflict",
            "source": "synthetic-conflict-source",
            "validity_state": EvidenceValidity.CONFLICTING,
            "content": {"finding": "different"},
        }
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=default_case(),
        evidence=(current_evidence, second_evidence),
        affected_flight_numbers=("FX103",),
        candidate_sources=(
            CandidateSource(
                source_key="swap-conflict",
                kind=OptionKind.SWAP,
                source_evidence_references=(
                    current_evidence.evidence_id,
                    second_evidence.evidence_id,
                ),
            ),
        ),
    )
    candidate = build_candidates(intake)[0]
    result = _with_operations_result(
        intake,
        per_candidate_result(candidate, current_evidence).model_copy(
            update={"evidence": (current_evidence, second_evidence)}
        ),
    )

    first = aggregate_candidate_result(result)
    second = aggregate_candidate_result(result)

    assert first.conflicts == second.conflicts
    assert first.confidence is not None
    assert first.confidence.disposition.value == "escalation_required"
    assert first.confidence.confidence <= 0.49
    assert first.conflicts[0].evidence_references == tuple(
        sorted((current_evidence.evidence_id, second_evidence.evidence_id))
    )


def test_aggregation_marks_missing_operations_result_as_partial_and_low_confidence(
    valid_case,
    current_evidence: Evidence,
) -> None:
    intake = make_intake(valid_case, current_evidence)
    candidate = build_candidates(intake)[0]
    result = aggregate_candidate_result(per_candidate_result(candidate, current_evidence))

    assert result.status is WorkflowStatus.ESCALATION_REQUIRED
    assert result.confidence is not None
    assert result.confidence.confidence <= 0.49
    assert "operations_result" in result.missing_data


def test_aggregation_preserves_failed_specialist_source(
    valid_case,
    current_evidence: Evidence,
) -> None:
    intake = make_intake(valid_case, current_evidence)
    candidate = build_candidates(intake)[0]
    result = per_candidate_result(candidate, current_evidence)
    failed = result.maintenance_result.model_copy(
        update={
            "status": AgentResultStatus.FAILED,
            "confidence": 0.0,
            "role_payload": {
                "error": {
                    "schema_version": "1.0",
                    "category": "synthetic_source_failure",
                    "component": "maintenance-agent",
                    "message": "synthetic maintenance source failure",
                    "retryable": False,
                    "case_impact": "maintenance assessment is unavailable",
                }
            },
        }
    )
    result = _with_operations_result(
        intake,
        result.model_copy(update={"maintenance_result": failed}),
    )

    aggregate = aggregate_candidate_result(result)

    assert aggregate.maintenance_result.status is AgentResultStatus.FAILED
    assert aggregate.status is WorkflowStatus.ESCALATION_REQUIRED
    assert any(error.category == "synthetic_source_failure" for error in aggregate.errors)
    assert aggregate.confidence is not None
    assert aggregate.confidence.confidence == 0.0
