import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.context import (
    ControllerAuditRecorder,
    ControllerCaseContextRecorder,
    InMemoryControllerContextStore,
)
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    RoutingOmission,
    WorkflowStatus,
)
from aog_recovery.controller.orchestration import CandidateSpecialistRequest
from aog_recovery.controller.workflow import ControllerWorkflow, ControllerWorkflowResult
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
    OperationsOutcome,
    OperationsRequest,
    OptionKind,
    PackageLoadData,
)
from aog_recovery.operations.synthetic import default_adapters, default_case

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class FakeSpecialist:
    def __init__(
        self,
        role: AgentRole,
        fail_kinds: frozenset[OptionKind] = frozenset(),
    ) -> None:
        self.role = role
        self.fail_kinds = fail_kinds
        self.calls: list[CandidateSpecialistRequest] = []

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        self.calls.append(request)
        if request.candidate.candidate.kind in self.fail_kinds:
            error = {
                "schema_version": "1.0",
                "category": "synthetic_specialist_failure",
                "component": f"{self.role.value}-agent",
                "message": "Synthetic specialist failure",
                "retryable": False,
                "case_impact": "Candidate analysis is unavailable",
            }
            return AgentResult(
                schema_version="1.0",
                agent_role=self.role,
                status=AgentResultStatus.FAILED,
                summary="Synthetic specialist failure",
                confidence=0.0,
                assumptions=(),
                evidence_references=(),
                role_payload={"error": error},
            )

        if self.role is AgentRole.MAINTENANCE:
            role_payload = maintenance_payload().model_dump(mode="json")
        else:
            role_payload = materials_payload().model_dump(mode="json")
        return AgentResult(
            schema_version="1.0",
            agent_role=self.role,
            status=AgentResultStatus.COMPLETE,
            summary=f"Synthetic {self.role.value} assessment",
            confidence=0.82,
            assumptions=(),
            evidence_references=("evidence-controller-001",),
            role_payload=role_payload,
        )


class FakeOperations:
    def __init__(self, timeout_kinds: frozenset[OptionKind] = frozenset()) -> None:
        self.agent = OperationsAgent(default_adapters())
        self.timeout_kinds = timeout_kinds
        self.calls: list[OperationsRequest] = []

    def assess(self, request: OperationsRequest) -> OperationsOutcome:
        self.calls.append(request)
        if request.candidates[0].kind in self.timeout_kinds:
            raise TimeoutError("synthetic Operations timeout")
        return self.agent.assess(request)


def evidence_bundle(
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
    conflicting: bool = False,
) -> tuple[Evidence, ...]:
    primary = Evidence(
        evidence_id="evidence-controller-001",
        source="synthetic-controller-source",
        retrieved_at=NOW,
        validity_state=validity,
        claim_reference="claim-controller-readiness",
        content={"readiness": "synthetic"},
    )
    if not conflicting:
        return (primary,)
    contradictory = Evidence(
        evidence_id="evidence-controller-conflict-001",
        source="synthetic-conflict-source",
        retrieved_at=NOW,
        validity_state=EvidenceValidity.CONFLICTING,
        claim_reference=primary.claim_reference,
        content={"readiness": "different-synthetic-value"},
    )
    return primary, contradictory


def make_intake_payload(
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
    conflicting: bool = False,
) -> dict[str, object]:
    evidence = evidence_bundle(validity, conflicting)
    references = tuple(item.evidence_id for item in evidence)
    readiness = ReadinessEstimate(
        source_agent=AgentRole.MAINTENANCE,
        eta=NOW,
        basis=EtaBasis.ESTIMATED,
        evidence_references=(references[0],),
    )
    sourcing = tuple(
        SourcingOption(
            part_number=part_number,
            source="synthetic-parts-source",
            source_location="TEST-STATION-B",
            method=SourcingMethod.INTERNAL_TRANSFER,
            shipping_provider=None,
            shipping_service=None,
            transfer_required=True,
            lead_time_hours=2.0,
            eta_at=NOW,
            estimated_cost_usd=Decimal("100.00"),
            quote_unavailable_reason=None,
            evidence_references=(references[0],),
        )
        for part_number in ("P-110", "P-120")
    )
    sources = (
        CandidateSource(
            source_key="repair-original-P110",
            kind=OptionKind.REPAIR_ORIGINAL,
            failed_part_number="P-110",
            source_evidence_references=references,
            readiness=readiness,
            sourcing_options=(sourcing[0],),
            package_load=PackageLoadData(groups=()),
            package_load_evidence_references=(references[0],),
        ),
        CandidateSource(
            source_key="repair-alternate-P120",
            kind=OptionKind.REPAIR_ALTERNATE,
            failed_part_number="P-110",
            source_evidence_references=references,
            readiness=readiness,
            sourcing_options=(sourcing[1],),
            package_load=PackageLoadData(groups=()),
            package_load_evidence_references=(references[0],),
        ),
        CandidateSource(
            source_key="aircraft-swap",
            kind=OptionKind.SWAP,
            source_evidence_references=references,
            readiness=readiness,
            package_load=PackageLoadData(groups=()),
            package_load_evidence_references=(references[0],),
        ),
        CandidateSource(
            source_key="flight-delay",
            kind=OptionKind.DELAY,
            source_evidence_references=references,
            package_load=PackageLoadData(groups=()),
            package_load_evidence_references=(references[0],),
        ),
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=default_case(),
        evidence=evidence,
        candidate_sources=sources,
        affected_flight_numbers=("FX103",),
    )
    return intake.model_dump(mode="json")


def maintenance_payload() -> MaintenanceAssessmentPayload:
    return MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.UNCERTAIN,
        root_cause=None,
        recurring_failure=None,
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("evidence-controller-001",),
        required_actions=("inspect_pump",),
        estimated_ground_time_hours=None,
        ground_time_unavailable_reason="synthetic estimate unavailable",
        estimated_repair_labor_cost_usd=None,
        need_by_time=None,
        parts_ready_at=NOW,
        return_to_service_time=None,
        meets_need_by_time=None,
        eta_confidence=0.72,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.UNKNOWN,
            parts_dependency_risk=MaintenanceRiskLevel.UNKNOWN,
            repair_complexity_risk=MaintenanceRiskLevel.UNKNOWN,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=("ground-time estimate",),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.UNKNOWN,
            approver_role=None,
            source_reference=None,
            recorded_at=None,
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.UNCERTAIN,
            confidence=0.72,
            rationale="Synthetic assessment requires additional evidence",
            next_steps=(),
        ),
    )


def materials_payload() -> MaterialsLogisticsAgentPayload:
    sourcing_options = tuple(
        SourcingOption(
            part_number=part_number,
            source="synthetic-parts-source",
            source_location="TEST-STATION-B",
            method=SourcingMethod.INTERNAL_TRANSFER,
            shipping_provider=None,
            shipping_service=None,
            transfer_required=True,
            lead_time_hours=2.0,
            eta_at=NOW,
            estimated_cost_usd=Decimal("100.00"),
            quote_unavailable_reason=None,
            evidence_references=("evidence-controller-001",),
        )
        for part_number in ("P-110", "P-120")
    )
    return MaterialsLogisticsAgentPayload(
        schema_version="1.0",
        assessment=MaterialsLogisticsAssessmentPayload(
            schema_version="1.0",
            availability_status=AvailabilityStatus.UNCERTAIN,
            part_availability=(),
            part_eligibility=tuple(
                PartEligibilityEvidence(
                    part_number=part_number,
                    compatibility=CompatibilityStatus.UNKNOWN,
                    authorization=AuthorizationStatus.UNKNOWN,
                    traceability=TraceabilityStatus.UNKNOWN,
                    checked_by_role=None,
                    evidence_references=("evidence-controller-001",),
                )
                for part_number in ("P-110", "P-120")
            ),
            sourcing_options=sourcing_options,
            confidence=0.72,
            risk_factors=(),
            assumptions=(),
            missing_data=("authorization", "traceability"),
        ),
        evidence_summary=MaterialsEvidenceSummary(
            status=ToolResultStatus.PARTIAL,
            confidence=0.72,
            evidence_references=("evidence-controller-001",),
            warnings=(),
            errors=(),
        ),
    )


def create_workflow(
    *,
    store: InMemoryControllerContextStore | None = None,
    maintenance_fail_kinds: frozenset[OptionKind] = frozenset(),
    operations_timeout_kinds: frozenset[OptionKind] = frozenset(),
    omitted_specialists: tuple[RoutingOmission, ...] = (),
) -> tuple[
    ControllerWorkflow,
    FakeSpecialist,
    FakeSpecialist,
    FakeOperations,
    InMemoryControllerContextStore,
]:
    chosen_store = store or InMemoryControllerContextStore()
    maintenance = FakeSpecialist(AgentRole.MAINTENANCE, maintenance_fail_kinds)
    materials = FakeSpecialist(AgentRole.MATERIALS_LOGISTICS)
    operations = FakeOperations(operations_timeout_kinds)
    audit = ControllerAuditRecorder(chosen_store)
    workflow = ControllerWorkflow(
        maintenance,
        materials,
        operations,
        ControllerCaseContextRecorder(chosen_store),
        settings=AogSettings(agent_timeout_seconds=1),
        audit_recorder=audit,
        omitted_specialists=omitted_specialists,
        clock=lambda: NOW,
    )
    return workflow, maintenance, materials, operations, chosen_store


@pytest.mark.asyncio
async def test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate() -> None:
    workflow, maintenance, materials, operations, store = create_workflow()

    result: ControllerWorkflowResult = await workflow.run(make_intake_payload())

    assert result.intake.validation.is_valid
    assert result.intake.routing is not None
    assert len(result.intake.routing.selected_roles) == 3
    assert result.handoff is not None
    assert len(result.handoff.candidates) == 4
    assert result.handoff.human_gate.status.value == "pending"
    assert len(maintenance.calls) == 4
    assert len(materials.calls) == 4
    assert len(operations.calls) == 4
    assert "readiness_eta" in next(
        candidate.result.missing_data
        for candidate in result.handoff.candidates
        if candidate.result.candidate.kind is OptionKind.DELAY
    )
    assert all(
        not hasattr(candidate.result.candidate, field_name)
        for candidate in result.handoff.candidates
        for field_name in ("score", "rank", "recommended_winner")
    )
    assert any(event.event_type == "controller_handoff" for event in store.events)
    assert sum(event.event_type == "peer_exchange" for event in store.events) == 4


@pytest.mark.asyncio
async def test_workflow_keeps_failures_candidate_local_and_records_timeout_and_h3_failure() -> None:
    payload = make_intake_payload()
    intake = ControllerIntake.model_validate_json(json.dumps(payload))
    repair = next(
        candidate
        for candidate in build_candidates(intake)
        if candidate.candidate.kind is OptionKind.REPAIR_ORIGINAL
    )
    store = InMemoryControllerContextStore(
        fail_on_event_ids=frozenset({f"peer-exchange:{repair.candidate.option_id}:h3h4:response"})
    )
    workflow, maintenance, _, operations, event_store = create_workflow(
        store=store,
        maintenance_fail_kinds=frozenset({OptionKind.SWAP}),
        operations_timeout_kinds=frozenset({OptionKind.DELAY}),
    )

    result = await workflow.run(payload)

    assert result.handoff is not None
    assert len(result.handoff.candidates) == 4
    by_kind = {item.result.candidate.kind: item for item in result.handoff.candidates}
    assert by_kind[OptionKind.SWAP].result.maintenance_result.status is AgentResultStatus.FAILED
    assert any(
        error.category == "operations_timeout" for error in by_kind[OptionKind.DELAY].result.errors
    )
    assert "h3_h4_exchange" in by_kind[OptionKind.REPAIR_ORIGINAL].result.missing_data
    assert by_kind[OptionKind.REPAIR_ALTERNATE].result.operations_result is not None
    assert any(event.event_type == "operations_timeout" for event in event_store.events)
    assert any(error.category == "case_context_recording_failed" for error in result.errors)
    assert len(maintenance.calls) == 4
    assert len(operations.calls) == 4
    assert result.handoff.human_gate.status.value == "pending"


@pytest.mark.asyncio
async def test_workflow_preserves_degraded_evidence_and_excludes_unverified_parts() -> None:
    stale_workflow, _, _, _, _ = create_workflow()
    conflict_workflow, _, _, _, _ = create_workflow()

    stale_result = await stale_workflow.run(make_intake_payload(validity=EvidenceValidity.STALE))
    conflict_result = await conflict_workflow.run(make_intake_payload(conflicting=True))

    assert stale_result.handoff is not None
    assert any(warning.code == "STALE_EVIDENCE" for warning in stale_result.handoff.warnings)
    assert stale_result.handoff.status in {
        WorkflowStatus.PROVISIONAL,
        WorkflowStatus.ESCALATION_REQUIRED,
    }
    assert conflict_result.handoff is not None
    assert conflict_result.handoff.conflicts
    assert conflict_result.handoff.status is WorkflowStatus.ESCALATION_REQUIRED
    assert all(
        not candidate.eligible
        for candidate in conflict_result.handoff.candidates
        if candidate.result.candidate.kind
        in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
    )


@pytest.mark.asyncio
async def test_invalid_workflow_intake_invokes_no_specialist() -> None:
    workflow, maintenance, materials, operations, _ = create_workflow()
    payload = make_intake_payload()
    del payload["case"]["aircraft_id"]

    result = await workflow.run(payload)

    assert not result.intake.validation.is_valid
    assert result.intake.routing is None
    assert result.handoff is None
    assert maintenance.calls == []
    assert materials.calls == []
    assert operations.calls == []


@pytest.mark.asyncio
async def test_workflow_honors_omitted_and_unavailable_specialist_routes() -> None:
    omission = RoutingOmission(
        agent_role=AgentRole.MATERIALS_LOGISTICS,
        reason="materials source excluded by deterministic policy",
    )
    omitted_workflow, _, omitted_materials, _, _ = create_workflow(omitted_specialists=(omission,))

    omitted_result = await omitted_workflow.run(make_intake_payload())

    assert omitted_result.handoff is not None
    assert omitted_materials.calls == []
    assert omitted_result.handoff.routing is not None
    assert omission in omitted_result.handoff.routing.omitted_roles
    assert all(
        any(error.category == "specialist_omitted" for error in item.result.errors)
        for item in omitted_result.handoff.candidates
    )

    unavailable_workflow, _, unavailable_materials, _, _ = create_workflow()
    unavailable_payload = make_intake_payload()
    unavailable_payload["source_health"] = [
        {
            "source_id": "materials-api",
            "agent_role": AgentRole.MATERIALS_LOGISTICS.value,
            "status": "unavailable",
            "checked_at": NOW.isoformat(),
            "evidence_references": [],
            "reason": "synthetic source outage",
        }
    ]

    unavailable_result = await unavailable_workflow.run(unavailable_payload)

    assert unavailable_result.handoff is not None
    assert unavailable_materials.calls == []
    assert unavailable_result.handoff.routing is not None
    assert any(
        record.source_id == "materials-api" and record.status.value == "unavailable"
        for record in unavailable_result.handoff.routing.source_health
    )
    assert all(
        any(error.category == "specialist_source_unavailable" for error in item.result.errors)
        for item in unavailable_result.handoff.candidates
    )
