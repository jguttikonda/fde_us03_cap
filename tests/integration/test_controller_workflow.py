import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event
from types import SimpleNamespace

import pytest
from test_specialist_workflow import (
    FakeMaintenanceRunner,
    FakeMaterialsRunner,
    maintenance_runner_outputs,
    materials_runner_outputs,
)
from test_specialist_workflow import maintenance_input as specialist_maintenance_input
from test_specialist_workflow import materials_input as specialist_materials_input

from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole, StructuredError
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.adk_agent import ControllerAdkResponse, build_controller_adk_agent
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
from aog_recovery.controller.operations_adapter import (
    BoundedAsyncOperationsAdapter,
    OperationsCapacityError,
)
from aog_recovery.controller.orchestration import CandidateSpecialistRequest
from aog_recovery.controller.specialist_adapters import (
    MaintenanceSpecialistAdapter,
    MaterialsLogisticsSpecialistAdapter,
)
from aog_recovery.controller.workflow import ControllerWorkflow, ControllerWorkflowResult
from aog_recovery.maintenance.agent import MaintenanceAgent
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentInput,
    MaintenanceAssessmentPayload,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RepairabilityStatus,
)
from aog_recovery.materials_logistics.agent import (
    MaterialsLogisticsAgent,
    MaterialsLogisticsAgentPayload,
    MaterialsLogisticsAssessmentInput,
)
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
from aog_recovery.validation.confidence import ConfidenceDisposition

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class FakeSpecialist:
    def __init__(
        self,
        role: AgentRole,
        fail_kinds: frozenset[OptionKind] = frozenset(),
    ) -> None:
        self.role = role
        self.fail_kinds = fail_kinds
        self.fail_case_id: str | None = None
        self.result_override: AgentResult | None = None
        self.calls: list[CandidateSpecialistRequest] = []

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        self.calls.append(request)
        if self.result_override is not None:
            return self.result_override
        if request.candidate.candidate.kind in self.fail_kinds and (
            self.fail_case_id is None or request.case.case_id == self.fail_case_id
        ):
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

    async def assess(self, request: OperationsRequest) -> OperationsOutcome:
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
        source=("synthetic-maintenance-estimate" if conflicting else "synthetic-controller-source"),
        retrieved_at=NOW,
        validity_state=validity,
        claim_reference="recovery-time-estimate" if conflicting else "claim-controller-readiness",
        content=(
            {"estimate_hours": 3, "estimate_type": "maintenance_repair"}
            if conflicting
            else {"readiness": "synthetic"}
        ),
    )
    if not conflicting:
        return (primary,)
    contradictory = Evidence(
        evidence_id="evidence-controller-conflict-001",
        source="synthetic-operations-disruption",
        retrieved_at=NOW,
        validity_state=EvidenceValidity.CONFLICTING,
        claim_reference=primary.claim_reference,
        content={"estimate_hours": 7, "estimate_type": "operations_disruption"},
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
async def test_async_operations_adapter_preserves_deterministic_outcome() -> None:
    intake = ControllerIntake.model_validate_json(json.dumps(make_intake_payload()))
    candidate = build_candidates(intake)[0].candidate
    request = OperationsRequest(
        schema_version="1.0",
        request_id=f"{candidate.option_id}:operations",
        case=intake.case,
        affected_flight_numbers=intake.affected_flight_numbers,
        candidates=(candidate,),
        evaluated_at=NOW,
        reroute_policy=intake.reroute_policy,
        reserved_capacity=intake.reserved_capacity,
    )
    agent = OperationsAgent(default_adapters())
    expected = agent.assess(request)

    result = await BoundedAsyncOperationsAdapter(
        agent,
        AogSettings(operations_timeout_seconds=5),
    ).assess(request)

    assert result == expected


@pytest.mark.asyncio
async def test_adk_agent_binds_versioned_workflow_response_without_model_call() -> None:
    workflow, _, _, _, _ = create_workflow()
    agent = build_controller_adk_agent(workflow, model_name="test-model")

    assert agent.output_schema is ControllerAdkResponse
    assert agent.name == "controller_agent"
    assert len(agent.tools) == 1
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))
    tool_result = await agent.tools[0](make_intake_payload(), tool_context)
    response = ControllerAdkResponse.model_validate_json(json.dumps(tool_result))

    assert response.schema_version == "1.0"
    assert response.status == "complete"
    assert response.workflow is not None
    assert response.workflow.handoff is not None
    assert response.workflow.handoff.human_gate.status.value == "pending"
    assert response.workflow.recommendation is not None
    assert response.workflow.recommendation.case_id == response.workflow.handoff.case.case_id
    assert response.workflow.recommendation.human_gate.status.value == "pending"
    assert response.workflow.recommendation.weights.speed == Decimal("0.30")
    assert tool_context.actions.skip_summarization


@pytest.mark.asyncio
async def test_adk_response_preserves_partial_decision_brief_and_errors() -> None:
    workflow, _, _, _, _ = create_workflow(maintenance_fail_kinds=frozenset({OptionKind.SWAP}))
    agent = build_controller_adk_agent(workflow, model_name="test-model")
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))

    result = await agent.tools[0](make_intake_payload(), tool_context)
    response = ControllerAdkResponse.model_validate_json(json.dumps(result))

    assert response.status == "complete"
    assert response.workflow is not None
    assert response.workflow.handoff is not None
    assert response.workflow.recommendation is not None
    assert response.workflow.errors
    assert response.workflow.recommendation.errors
    assert response.workflow.recommendation.human_gate.status.value == "pending"
    assert response.workflow.recommendation.status.value in {
        "provisional",
        "requires_escalation",
        "awaiting_additional_data",
    }
    assert tool_context.actions.skip_summarization


@pytest.mark.asyncio
async def test_adk_boundary_returns_explicit_failure_for_invalid_workflow_output() -> None:
    class InvalidWorkflow:
        async def run(self, payload: object) -> object:
            return {"status": "success", "recommended_winner": "untrusted"}

    agent = build_controller_adk_agent(InvalidWorkflow(), model_name="test-model")  # type: ignore[arg-type]
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))

    result = await agent.tools[0](make_intake_payload(), tool_context)
    response = ControllerAdkResponse.model_validate_json(json.dumps(result))

    assert response.status == "failed"
    assert response.workflow is None
    assert response.failure is not None
    assert response.failure.category == "controller_workflow_output_invalid"
    assert "recommended_winner" not in json.dumps(result)
    assert tool_context.actions.skip_summarization


@pytest.mark.asyncio
async def test_adk_boundary_returns_explicit_failure_for_workflow_exception() -> None:
    class RaisingWorkflow:
        async def run(self, payload: object) -> object:
            raise RuntimeError("synthetic workflow failure")

    agent = build_controller_adk_agent(RaisingWorkflow(), model_name="test-model")  # type: ignore[arg-type]
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))

    result = await agent.tools[0](make_intake_payload(), tool_context)
    response = ControllerAdkResponse.model_validate_json(json.dumps(result))

    assert response.status == "failed"
    assert response.workflow is None
    assert response.failure is not None
    assert response.failure.category == "controller_workflow_failed"
    assert "synthetic workflow failure" not in json.dumps(result)
    assert tool_context.actions.skip_summarization


@pytest.mark.asyncio
async def test_adk_boundary_keeps_untrusted_intake_invalid_without_fallback() -> None:
    workflow, maintenance, materials, operations, _ = create_workflow()
    agent = build_controller_adk_agent(workflow, model_name="test-model")
    payload = make_intake_payload()
    payload["execute_transfer"] = True
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))

    result = await agent.tools[0](payload, tool_context)
    response = ControllerAdkResponse.model_validate_json(json.dumps(result))

    assert response.status == "complete"
    assert response.workflow is not None
    assert not response.workflow.intake.validation.is_valid
    assert response.workflow.handoff is None
    assert response.workflow.recommendation is None
    assert maintenance.calls == []
    assert materials.calls == []
    assert operations.calls == []
    assert tool_context.actions.skip_summarization
    schema = ControllerAdkResponse.model_json_schema()
    schema_properties: set[str] = set()

    def collect_properties(value: object) -> None:
        if not isinstance(value, dict):
            return
        properties = value.get("properties")
        if isinstance(properties, dict):
            schema_properties.update(properties)
            for child in properties.values():
                collect_properties(child)
        definitions = value.get("$defs")
        if isinstance(definitions, dict):
            for definition in definitions.values():
                collect_properties(definition)

    collect_properties(schema)
    assert schema_properties.isdisjoint({"execute", "execute_transfer"})


@pytest.mark.asyncio
async def test_concurrent_workflows_isolate_case_results_and_context_events() -> None:
    case_a_id = "AOG-CONCURRENT-A"
    case_b_id = "AOG-CONCURRENT-B"
    trace_a = {"trace_id": "trace-concurrent-a", "correlation_id": "corr-concurrent-a"}
    trace_b = {"trace_id": "trace-concurrent-b", "correlation_id": "corr-concurrent-b"}
    payload_a = make_intake_payload()
    payload_b = make_intake_payload()
    payload_a["case"]["case_id"] = case_a_id
    payload_a["case"]["trace_context"] = trace_a
    payload_b["case"]["case_id"] = case_b_id
    payload_b["case"]["trace_context"] = trace_b
    store = InMemoryControllerContextStore()
    settings = AogSettings(agent_timeout_seconds=1)

    class GatedSpecialist(FakeSpecialist):
        def __init__(
            self,
            role: AgentRole,
            fail_kinds: frozenset[OptionKind] = frozenset(),
        ) -> None:
            super().__init__(role, fail_kinds)
            self.started_cases: set[str] = set()
            self.both_cases_started = asyncio.Event()

        async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
            self.started_cases.add(request.case.case_id)
            if len(self.started_cases) == 2:
                self.both_cases_started.set()
            await self.both_cases_started.wait()
            return await super().assess(request)

    maintenance = GatedSpecialist(
        AgentRole.MAINTENANCE,
        frozenset({OptionKind.SWAP}),
    )
    maintenance.fail_case_id = case_a_id
    materials = GatedSpecialist(AgentRole.MATERIALS_LOGISTICS)
    operations = FakeOperations()
    recorder = ControllerCaseContextRecorder(store)
    audit = ControllerAuditRecorder(store)

    def make_case_workflow() -> ControllerWorkflow:
        return ControllerWorkflow(
            maintenance,
            materials,
            operations,
            recorder,
            settings=settings,
            audit_recorder=audit,
            clock=lambda: NOW,
        )

    workflow_a = make_case_workflow()
    workflow_b = make_case_workflow()
    result_a, result_b = await asyncio.gather(
        workflow_a.run(payload_a),
        workflow_b.run(payload_b),
    )

    assert result_a.handoff is not None
    assert result_b.handoff is not None
    assert result_a.handoff.case.case_id == case_a_id
    assert result_b.handoff.case.case_id == case_b_id
    assert result_a.handoff.case.trace_context.trace_id == trace_a["trace_id"]
    assert result_b.handoff.case.trace_context.trace_id == trace_b["trace_id"]

    candidates_a = {item.result.candidate.kind: item.result for item in result_a.handoff.candidates}
    candidates_b = {item.result.candidate.kind: item.result for item in result_b.handoff.candidates}
    assert candidates_a[OptionKind.SWAP].maintenance_result.status is AgentResultStatus.FAILED
    assert all(
        item.maintenance_result.status is AgentResultStatus.COMPLETE
        for item in candidates_b.values()
    )
    assert all(item.candidate.option_id.startswith(case_a_id) for item in candidates_a.values())
    assert all(item.candidate.option_id.startswith(case_b_id) for item in candidates_b.values())

    events_a = tuple(event for event in store.events if event.case_id == case_a_id)
    events_b = tuple(event for event in store.events if event.case_id == case_b_id)
    assert events_a and events_b
    assert all(event.trace_context.trace_id == trace_a["trace_id"] for event in events_a)
    assert all(event.trace_context.trace_id == trace_b["trace_id"] for event in events_b)
    recommendation_a = next(
        event for event in events_a if event.event_type == "controller_recommendation"
    )
    recommendation_b = next(
        event for event in events_b if event.event_type == "controller_recommendation"
    )
    assert result_a.recommendation is not None
    assert result_b.recommendation is not None
    assert recommendation_a.details["recommendation_version"] == (
        result_a.recommendation.recommendation_version
    )
    assert recommendation_b.details["recommendation_version"] == (
        result_b.recommendation.recommendation_version
    )
    assert all(case_a_id in str(event.details.get("candidate_id", case_a_id)) for event in events_a)
    assert all(case_b_id in str(event.details.get("candidate_id", case_b_id)) for event in events_b)
    assert all(
        item.result.status is not WorkflowStatus.FAILED for item in result_b.handoff.candidates
    )


@pytest.mark.asyncio
async def test_operations_timeout_is_bounded_visible_and_candidate_local() -> None:
    payload = make_intake_payload()
    intake = ControllerIntake.model_validate_json(json.dumps(payload))
    store = InMemoryControllerContextStore()
    settings = AogSettings(
        agent_timeout_seconds=1,
        operations_timeout_seconds=1,
        operations_max_workers=1,
    )

    class WaitingOperationsAgent:
        def __init__(self) -> None:
            self.agent = OperationsAgent(default_adapters())
            self.started = Event()
            self.release = Event()
            self.finished = Event()

        def assess(self, request: OperationsRequest) -> OperationsOutcome:
            is_delayed = request.candidates[0].kind is OptionKind.DELAY
            if is_delayed:
                self.started.set()
                self.release.wait()
            try:
                return self.agent.assess(request)
            finally:
                if is_delayed:
                    self.finished.set()

    waiting_agent = WaitingOperationsAgent()
    operations = BoundedAsyncOperationsAdapter(waiting_agent, settings)
    workflow = ControllerWorkflow(
        FakeSpecialist(AgentRole.MAINTENANCE),
        FakeSpecialist(AgentRole.MATERIALS_LOGISTICS),
        operations,
        ControllerCaseContextRecorder(store),
        settings=settings,
        audit_recorder=ControllerAuditRecorder(store),
        clock=lambda: NOW,
    )

    try:
        result = await workflow.run(payload)
        assert waiting_agent.started.is_set()
        assert not waiting_agent.finished.is_set()
        assert result.handoff is not None
        by_kind = {item.result.candidate.kind: item for item in result.handoff.candidates}
        delay = by_kind[OptionKind.DELAY].result
        timeout_error = next(
            error for error in delay.errors if error.category == "operations_timeout"
        )
        timeout_event = next(
            event for event in store.events if event.event_type == "operations_timeout"
        )

        assert delay.operations_result is None
        assert "operations_analysis" in delay.missing_data
        assert delay.confidence is not None
        assert delay.confidence.confidence <= 0.49
        assert delay.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED
        assert result.recommendation is not None
        assert result.recommendation.human_gate.status.value == "pending"
        assert any(error.category == "operations_timeout" for error in result.recommendation.errors)
        assert "operations_analysis" in result.recommendation.missing_data
        assert delay.candidate.option_id in timeout_error.message
        assert f"{delay.candidate.option_id}:operations" in timeout_error.message
        assert timeout_event.event_id == f"{delay.candidate.option_id}:operations:failed"
        assert timeout_event.trace_context == intake.case.trace_context
        assert timeout_event.details["candidate_id"] == delay.candidate.option_id
        assert timeout_event.details["timeout_seconds"] == 1
        retry_request = OperationsRequest(
            schema_version="1.0",
            request_id=f"{delay.candidate.option_id}:retry",
            case=intake.case,
            affected_flight_numbers=intake.affected_flight_numbers,
            candidates=(delay.candidate,),
            evaluated_at=NOW,
            reroute_policy=intake.reroute_policy,
            reserved_capacity=intake.reserved_capacity,
        )
        with pytest.raises(OperationsCapacityError):
            await operations.assess(retry_request)
        assert all(
            item.result.operations_result is not None
            and not any(error.category == "operations_timeout" for error in item.result.errors)
            for kind, item in by_kind.items()
            if kind is not OptionKind.DELAY
        )
        assert result.handoff.human_gate.status.value == "pending"
    finally:
        waiting_agent.release.set()
        assert waiting_agent.finished.wait(timeout=2)


@pytest.mark.asyncio
async def test_specialist_adapters_preserve_candidate_domain_inputs() -> None:
    payload = make_intake_payload()
    case = default_case()
    base_maintenance_input = specialist_maintenance_input()
    maintenance_input = base_maintenance_input.model_copy(
        update={
            "case": case,
            "aircraft_metadata": base_maintenance_input.aircraft_metadata.model_copy(
                update={"content": {"aircraft_id": case.aircraft_id}}
            ),
            "work_order": base_maintenance_input.work_order.model_copy(
                update={"aircraft_id": case.aircraft_id}
            ),
            "maintenance_history": tuple(
                item.model_copy(update={"content": {"state": "synthetic"}})
                for item in base_maintenance_input.maintenance_history
            ),
        }
    )
    materials_input = specialist_materials_input().model_copy(update={"case": case})
    selected_offer = materials_input.assessment.sourcing_options[0]
    other_offer = selected_offer.model_copy(
        update={
            "source": "synthetic-vendor-source",
            "method": SourcingMethod.VENDOR_PURCHASE,
            "estimated_cost_usd": Decimal("200.00"),
        }
    )
    materials_input = materials_input.model_copy(
        update={
            "assessment": materials_input.assessment.model_copy(
                update={"sourcing_options": (selected_offer, other_offer)}
            )
        }
    )
    source = payload["candidate_sources"][1]
    source["sourcing_options"] = [selected_offer.model_dump(mode="json")]
    source["maintenance_assessment_input"] = maintenance_input.model_dump(mode="json")
    source["materials_logistics_assessment_input"] = materials_input.model_dump(mode="json")

    evidence_references = {
        item.evidence_id
        for item in (
            maintenance_input.aircraft_metadata,
            maintenance_input.work_order.evidence,
            *maintenance_input.maintenance_history,
            *maintenance_input.engineering_constraints,
            *maintenance_input.safety_conditions,
        )
        if item is not None
    }
    evidence_references.update(
        reference
        for reference in (
            maintenance_input.need_by_evidence_reference,
            maintenance_input.parts_readiness_evidence_reference,
        )
        if reference is not None
    )
    evidence_references.update(materials_input.evidence_summary.evidence_references)
    evidence_references.update(
        item.claim_reference for item in materials_input.assessment.part_availability
    )
    evidence_references.update(
        reference
        for item in materials_input.assessment.part_eligibility
        for reference in item.evidence_references
    )
    evidence_references.update(
        reference
        for option in materials_input.assessment.sourcing_options
        for reference in option.evidence_references
    )
    payload["evidence"].extend(
        Evidence(
            evidence_id=reference,
            source="synthetic-specialist-source",
            retrieved_at=NOW,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference=f"claim-{reference}",
            content={"state": "synthetic"},
        ).model_dump(mode="json")
        for reference in evidence_references
        if reference != "evidence-controller-001"
    )

    intake = ControllerIntake.model_validate_json(json.dumps(payload))
    candidate = build_candidates(intake)[1]
    request = CandidateSpecialistRequest(
        schema_version="1.0",
        request_id=f"{candidate.candidate.option_id}:maintenance",
        case=intake.case,
        candidate=candidate,
        available_evidence_ids=tuple(item.evidence_id for item in intake.evidence),
    )
    maintenance_outputs = list(maintenance_runner_outputs(maintenance_input))
    maintenance_outputs[-1] = maintenance_outputs[-1].model_copy(update={"recurring_failure": None})
    maintenance_runner = FakeMaintenanceRunner(tuple(maintenance_outputs))
    materials_runner = FakeMaterialsRunner(materials_runner_outputs(materials_input))

    maintenance_result = await MaintenanceSpecialistAdapter(
        MaintenanceAgent(maintenance_runner)
    ).assess(request)
    materials_result = await MaterialsLogisticsSpecialistAdapter(
        MaterialsLogisticsAgent(materials_runner)
    ).assess(request)

    assert maintenance_result.status is AgentResultStatus.COMPLETE
    assert materials_result.status is AgentResultStatus.COMPLETE
    assert request.request_id.startswith(candidate.candidate.option_id)
    assert maintenance_runner.payloads[0]["case"]["case_id"] == case.case_id
    assert maintenance_runner.payloads[0]["need_by_evidence_reference"] == (
        maintenance_input.need_by_evidence_reference
    )
    assert maintenance_runner.payloads[0]["parts_readiness"]["evidence_reference"] == (
        maintenance_input.parts_readiness_evidence_reference
    )
    assert materials_runner.payloads[0]["case"]["case_id"] == case.case_id
    assert materials_runner.payloads[0]["assessment"]["sourcing_options"] == [
        selected_offer.model_dump(mode="json")
    ]
    assert materials_runner.payloads[0]["evidence_summary"]["evidence_references"] == list(
        materials_input.evidence_summary.evidence_references
    )


@pytest.mark.asyncio
async def test_specialist_adapters_keep_invalid_inputs_candidate_local() -> None:
    payload = make_intake_payload()
    case = default_case()
    maintenance_input = MaintenanceAssessmentInput(
        schema_version="1.0",
        case=case,
        need_by_time=None,
        need_by_evidence_reference=None,
        parts_ready_at=None,
        parts_readiness_evidence_reference=None,
        aircraft_metadata=None,
        work_order=None,
        maintenance_history=(),
        engineering_constraints=(),
        safety_conditions=(),
        part_dependencies=(),
        missing_data=("maintenance_history",),
    )
    materials_input = MaterialsLogisticsAssessmentInput(
        schema_version="1.0",
        case=case,
        assessment=MaterialsLogisticsAssessmentPayload(
            schema_version="1.0",
            availability_status=AvailabilityStatus.UNCERTAIN,
            part_availability=(),
            part_eligibility=(),
            sourcing_options=(),
            confidence=0.5,
            risk_factors=(),
            assumptions=(),
            missing_data=("inventory",),
        ),
        evidence_summary=MaterialsEvidenceSummary(
            status=ToolResultStatus.PARTIAL,
            confidence=0.5,
            evidence_references=(),
            warnings=(),
            errors=(),
        ),
    )
    first_offer = SourcingOption.model_validate_json(
        json.dumps(payload["candidate_sources"][0]["sourcing_options"][0])
    )
    second_offer = SourcingOption.model_validate_json(
        json.dumps(payload["candidate_sources"][1]["sourcing_options"][0])
    )
    first_materials_input = materials_input.model_copy(
        update={
            "assessment": materials_input.assessment.model_copy(
                update={"sourcing_options": (first_offer,)}
            )
        }
    )
    second_materials_input = materials_input.model_copy(
        update={
            "assessment": materials_input.assessment.model_copy(
                update={"sourcing_options": (second_offer,)}
            ),
            "evidence_summary": materials_input.evidence_summary.model_copy(
                update={"evidence_references": ("missing-materials-evidence",)}
            ),
        }
    )
    payload["candidate_sources"][0]["maintenance_assessment_input"] = maintenance_input.model_dump(
        mode="json"
    )
    payload["candidate_sources"][0]["materials_logistics_assessment_input"] = (
        first_materials_input.model_dump(mode="json")
    )
    payload["candidate_sources"][1]["maintenance_assessment_input"] = {"schema_version": "9.0"}
    payload["candidate_sources"][1]["materials_logistics_assessment_input"] = (
        second_materials_input.model_dump(mode="json")
    )

    intake = ControllerIntake.model_validate_json(json.dumps(payload))
    candidates = build_candidates(intake)[:2]
    requests = tuple(
        CandidateSpecialistRequest(
            schema_version="1.0",
            request_id=f"{candidate.candidate.option_id}:maintenance",
            case=intake.case,
            candidate=candidate,
            available_evidence_ids=tuple(item.evidence_id for item in intake.evidence),
        )
        for candidate in candidates
    )
    materials_requests = tuple(
        request.model_copy(
            update={"request_id": f"{request.candidate.candidate.option_id}:materials"}
        )
        for request in requests
    )

    class RecordingAgent:
        def __init__(self, role: AgentRole) -> None:
            self.role = role
            self.calls: list[object] = []

        async def assess(self, specialist_input: object) -> AgentResult:
            self.calls.append(specialist_input)
            return AgentResult(
                schema_version="1.0",
                agent_role=self.role,
                status=AgentResultStatus.COMPLETE,
                summary=f"Synthetic {self.role.value} result",
                confidence=0.8,
                assumptions=(),
                evidence_references=(),
                role_payload={},
            )

    maintenance_agent = RecordingAgent(AgentRole.MAINTENANCE)
    materials_agent = RecordingAgent(AgentRole.MATERIALS_LOGISTICS)
    maintenance_adapter = MaintenanceSpecialistAdapter(maintenance_agent)
    materials_adapter = MaterialsLogisticsSpecialistAdapter(materials_agent)

    maintenance_results = tuple([await maintenance_adapter.assess(request) for request in requests])
    materials_results = tuple(
        [await materials_adapter.assess(request) for request in materials_requests]
    )

    assert maintenance_results[0].status is AgentResultStatus.COMPLETE
    assert maintenance_results[1].status is AgentResultStatus.FAILED
    assert maintenance_results[1].role_payload["error"]["category"] == "maintenance_input_invalid"
    assert materials_results[0].status is AgentResultStatus.COMPLETE
    assert materials_results[1].status is AgentResultStatus.FAILED
    assert materials_results[1].role_payload["error"]["category"] == (
        "materials_evidence_unresolved"
    )
    assert len(maintenance_agent.calls) == 1
    assert isinstance(maintenance_agent.calls[0], MaintenanceAssessmentInput)
    assert len(materials_agent.calls) == 1
    assert isinstance(materials_agent.calls[0], MaterialsLogisticsAssessmentInput)


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
    assert result.recommendation is not None
    reported_kinds = {
        option.kind
        for option in (
            *result.recommendation.ranked_options,
            *result.recommendation.excluded_options,
            *result.recommendation.unscored_options,
        )
    }
    assert reported_kinds == {
        OptionKind.REPAIR_ORIGINAL,
        OptionKind.REPAIR_ALTERNATE,
        OptionKind.SWAP,
        OptionKind.DELAY,
    }
    swap = next(
        candidate
        for candidate in result.handoff.candidates
        if candidate.result.candidate.kind is OptionKind.SWAP
    )
    assert swap.eligible
    assert swap.result.evidence
    assert swap.result.operations_result is not None
    assert swap.result.operations_result.assessment is not None
    assert swap.result.operations_result.assessment.recovery_options[0].viability.value in {
        "viable",
        "viable_with_risk",
    }
    report_options = (
        *result.recommendation.ranked_options,
        *result.recommendation.excluded_options,
        *result.recommendation.unscored_options,
    )
    report_swap = next(option for option in report_options if option.kind is OptionKind.SWAP)
    assert report_swap.evidence_references
    assert result.recommendation.human_gate.status.value == "pending"
    assert not any(
        hasattr(result.recommendation, action)
        for action in ("purchase", "transfer", "book", "dispatch", "approve")
    )
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
    h4_responses = [
        event.exchange_record.message
        for event in store.events
        if event.event_type == "peer_exchange"
        and event.exchange_record is not None
        and event.exchange_record.direction.value == "response"
    ]
    assert len(h4_responses) == 2
    assert all(response.failed_part_number == "P-110" for response in h4_responses)
    assert all(response.preferred_part_number == "P-120" for response in h4_responses)
    assert any(item.startswith("readiness_eta") for item in result.recommendation.missing_data)


@pytest.mark.asyncio
async def test_workflow_does_not_create_brief_when_handoff_audit_fails() -> None:
    case = default_case()
    store = InMemoryControllerContextStore(
        fail_on_event_ids=frozenset({f"{case.case_id}:unranked-handoff"})
    )
    workflow, _, _, _, _ = create_workflow(store=store)

    result = await workflow.run(make_intake_payload())

    assert result.handoff is not None
    assert any(error.category == "controller_audit_append_failed" for error in result.errors)
    assert result.recommendation is None


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
    assert stale_result.recommendation is not None
    assert stale_result.recommendation.human_gate.status.value == "pending"
    assert any(warning.code == "STALE_EVIDENCE" for warning in stale_result.recommendation.warnings)
    assert stale_result.handoff.status in {
        WorkflowStatus.PROVISIONAL,
        WorkflowStatus.ESCALATION_REQUIRED,
    }
    assert conflict_result.handoff is not None
    assert conflict_result.handoff.conflicts
    assert conflict_result.handoff.status is WorkflowStatus.ESCALATION_REQUIRED
    assert conflict_result.recommendation is not None
    assert conflict_result.recommendation.status.value == "requires_escalation"
    assert conflict_result.recommendation.human_gate.status.value == "pending"
    assert any(
        warning.code == "CONFLICTING_EVIDENCE"
        for warning in conflict_result.recommendation.warnings
    )
    conflict_estimates = {
        item.source: item.content.get("estimate_hours")
        for item in conflict_result.handoff.evidence
        if item.claim_reference == "recovery-time-estimate"
    }
    assert conflict_estimates == {
        "synthetic-maintenance-estimate": 3,
        "synthetic-operations-disruption": 7,
    }
    assert conflict_result.recommendation.conflicts
    assert set(conflict_result.recommendation.conflicts[0].evidence_references) == {
        "evidence-controller-001",
        "evidence-controller-conflict-001",
    }
    assert all(
        not candidate.eligible
        for candidate in conflict_result.handoff.candidates
        if candidate.result.candidate.kind
        in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
    )


@pytest.mark.asyncio
async def test_cached_inventory_failure_reaches_controller_report_and_correlated_audit() -> None:
    workflow, _, materials, _, store = create_workflow()
    source_error = StructuredError(
        schema_version="1.0",
        category="source_unavailable",
        component="materials-adapter:part_inventory",
        message="inventory source is unavailable",
        retryable=False,
        case_impact="inventory is represented by stale cached evidence",
    )
    cached_warning = EvidenceWarning(
        warning_id="cached-inventory-warning",
        claim_reference="inventory-claim-controller",
        code="CACHED_EVIDENCE",
        message="cached inventory may be stale",
        source_reference="synthetic-inventory-cache",
    )
    evidence_summary = MaterialsEvidenceSummary(
        status=ToolResultStatus.PARTIAL,
        confidence=0.72,
        evidence_references=("evidence-controller-001",),
        warnings=(cached_warning,),
        errors=(source_error,),
    )
    payload = materials_payload().model_copy(update={"evidence_summary": evidence_summary})
    materials.result_override = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MATERIALS_LOGISTICS,
        status=AgentResultStatus.PARTIAL,
        summary="Materials assessment uses degraded cached inventory",
        confidence=0.72,
        assumptions=(),
        evidence_references=("evidence-controller-001",),
        role_payload=payload.model_dump(mode="json"),
    )

    result = await workflow.run(make_intake_payload(validity=EvidenceValidity.STALE))

    assert result.handoff is not None
    assert result.handoff.human_gate.status.value == "pending"
    assert any(warning.code == "CACHED_EVIDENCE" for warning in result.handoff.warnings)
    assert any(error.category == "source_unavailable" for error in result.handoff.errors)
    response_events = [
        event
        for event in store.events
        if event.event_type == "peer_exchange"
        and event.exchange_record is not None
        and event.exchange_record.direction.value == "response"
    ]
    assert response_events
    for event in response_events:
        assert event.case_id == result.handoff.case.case_id
        assert event.trace_context == result.handoff.case.trace_context
        assert event.exchange_record is not None
        h4_response = event.exchange_record.message
        assert any(warning.code == "CACHED_EVIDENCE" for warning in h4_response.warnings)
        assert any(error.category == "source_unavailable" for error in h4_response.errors)


@pytest.mark.asyncio
async def test_malformed_specialist_schema_remains_visible_in_controller_report() -> None:
    workflow, _, materials, _, _ = create_workflow()
    materials.result_override = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MATERIALS_LOGISTICS,
        status=AgentResultStatus.COMPLETE,
        summary="Synthetic malformed Materials result",
        confidence=0.82,
        assumptions=(),
        evidence_references=("evidence-controller-001",),
        role_payload={"schema_version": "9.0"},
    )

    result = await workflow.run(make_intake_payload())

    assert result.handoff is not None
    assert result.recommendation is not None
    assert result.recommendation.human_gate.status.value == "pending"
    assert result.recommendation.status.value == "requires_escalation"
    assert any(
        error.category == "specialist_result_validation_failed"
        for error in result.recommendation.errors
    )
    assert any(
        error.category == "peer_exchange_payload_invalid" for error in result.recommendation.errors
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
    assert unavailable_result.recommendation is not None
    assert unavailable_result.recommendation.human_gate.status.value == "pending"
    assert any(
        error.category == "specialist_source_unavailable"
        for error in unavailable_result.recommendation.errors
    )
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
