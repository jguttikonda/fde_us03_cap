import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.evidence import (
    Assumption,
    EvidenceValidity,
    EvidenceWarning,
)
from aog_recovery.contracts.tool import ToolName, ToolResultStatus
from aog_recovery.controller.brief import build_decision_brief, render_decision_brief
from aog_recovery.controller.candidates import build_recovery_candidates
from aog_recovery.controller.compliance import apply_compliance_gate
from aog_recovery.controller.intake import InMemoryCaseContextStore, validate_controller_intake
from aog_recovery.controller.models import (
    CandidateBuildContext,
    CandidateScoringInput,
    ComplianceGateResult,
    ControllerIntake,
    ControllerWorkflowStatus,
)
from aog_recovery.controller.scoring import score_candidates
from aog_recovery.controller.workflow import ControllerWorkflow, _maintenance_evidence_ids
from aog_recovery.coordination.models import ExchangeStatus
from aog_recovery.coordination.recording import InMemoryCaseContextRecorder
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentInput,
    MaintenanceAssessmentPayload,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RecurringFailureSummary,
    RepairabilityStatus,
    RootCauseEvidence,
)
from aog_recovery.materials_logistics.agent import (
    MaterialsLogisticsAgentPayload,
    MaterialsLogisticsAssessmentInput,
)
from aog_recovery.operations.models import (
    AlternateFlightData,
    CandidateOption,
    FleetAvailabilityData,
    FlightScheduleData,
    NetworkStatusData,
    OperationsRequest,
    OptionKind,
    PackageLoadData,
)
from aog_recovery.operations.synthetic import make_adapters

FIXTURE_ROOT = Path("incidents/mock_data")
EVALUATED_AT = datetime(2026, 10, 22, 10, 10, tzinfo=UTC)


class FakeAssessor:
    def __init__(self, result: AgentResult) -> None:
        self.result = result
        self.calls = 0

    async def assess(self, payload: object) -> AgentResult:
        self.calls += 1
        return self.result


def load_json(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def controller_intake() -> ControllerIntake:
    payload = {
        "schema_version": "1.0",
        "request_id": "REQ-CONTROLLER-REMOTE-1042",
        "case": {
            "case_id": "AOG-MOCK-1042",
            "aircraft_id": "N123AB",
            "event_type": "hydraulic_pump_failure",
            "defect_summary": "Hydraulic pump P-110 failure; P-120 transfer from DFW.",
            "location": "MIA",
            "event_at": "2026-10-22T10:00:00Z",
            "created_at": "2026-10-22T10:05:00Z",
            "need_by": "2026-10-22T18:00:00Z",
            "schema_version": "1.0",
            "trace_context": {
                "trace_id": "trace-aog-mock-1042",
                "correlation_id": "corr-aog-mock-1042",
            },
        },
        "failed_part_number": "P-110",
        "affected_flight_numbers": ["FX103"],
        "evaluated_at": "2026-10-22T10:10:00Z",
    }
    validated = validate_controller_intake(payload)
    assert validated.intake is not None
    return validated.intake


def maintenance_result(payload: MaintenanceAssessmentInput) -> AgentResult:
    evidence_ids = tuple(
        evidence.evidence_id
        for evidence in (
            *payload.maintenance_history,
            *payload.engineering_constraints,
            *payload.safety_conditions,
            payload.aircraft_metadata,
            payload.work_order.evidence if payload.work_order is not None else None,
        )
        if evidence is not None
    )
    assessment = MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.FEASIBLE,
        root_cause=RootCauseEvidence(
            category="hydraulic_pump_failure",
            confidence=0.82,
            evidence_references=("WORK-ORDER-1042",),
        ),
        recurring_failure=RecurringFailureSummary(
            part_number="P-110",
            occurrences=3,
            window_days=90,
            evidence_references=("HIST-P110-001", "HIST-P110-002", "HIST-P110-003"),
        ),
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("ENG-P120-1042",),
        required_actions=("Complete required functional checks",),
        estimated_ground_time_hours=3.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("1000.00"),
        need_by_time=payload.need_by_time,
        parts_ready_at=payload.parts_ready_at,
        return_to_service_time=datetime(2026, 10, 22, 16, 0, tzinfo=UTC),
        meets_need_by_time=True,
        eta_confidence=0.68,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.MEDIUM,
            parts_dependency_risk=MaintenanceRiskLevel.MEDIUM,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=("Transfer delay may affect the return-to-service estimate.",),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.APPROVAL_RECORDED,
            approver_role="maintenance_airworthiness",
            source_reference="APPROVAL-P120-1042",
            recorded_at=datetime(2026, 10, 22, 10, 6, tzinfo=UTC),
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.REPAIR,
            confidence=0.82,
            rationale=(
                "Repair path has a recorded engineering approval and an estimated readiness time."
            ),
            next_steps=("Operations lead must review the operational plan.",),
        ),
    )
    return AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MAINTENANCE,
        status=AgentResultStatus.COMPLETE,
        summary="P-120 is the preferred replacement with recorded engineering approval.",
        confidence=0.82,
        assumptions=(
            Assumption(
                assumption_id="AOG-MOCK-1042-MNT-ASSUMPTION-1",
                claim_reference="maintenance-assessment:AOG-MOCK-1042",
                statement="The mock transfer estimate remains current.",
                evidence_references=(),
            ),
        ),
        evidence_references=evidence_ids,
        role_payload=assessment.model_dump(mode="json"),
    )


def materials_result(
    payload: MaterialsLogisticsAssessmentInput,
    *,
    status: AgentResultStatus = AgentResultStatus.COMPLETE,
    confidence: float = 0.86,
) -> AgentResult:
    role_payload = MaterialsLogisticsAgentPayload(
        schema_version="1.0",
        assessment=payload.assessment,
        evidence_summary=payload.evidence_summary,
    )
    evidence_references = set(payload.evidence_summary.evidence_references)
    evidence_references.update(
        record.claim_reference for record in payload.assessment.part_availability
    )
    evidence_references.update(
        reference
        for eligibility in payload.assessment.part_eligibility
        for reference in eligibility.evidence_references
    )
    evidence_references.update(
        reference
        for option in payload.assessment.sourcing_options
        for reference in option.evidence_references
    )
    return AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MATERIALS_LOGISTICS,
        status=status,
        summary="P-120 is eligible at DFW with an estimated transfer ETA.",
        confidence=confidence,
        assumptions=(),
        evidence_references=tuple(sorted(evidence_references)),
        role_payload=role_payload.model_dump(mode="json"),
    )


def operations_adapters() -> dict[ToolName, ReadOnlyAdapter]:
    source = load_json("operations_agent.json")["source_data"]
    assert isinstance(source, dict)
    models = (
        (FlightScheduleData, "flight_schedule"),
        (FleetAvailabilityData, "fleet_availability"),
        (PackageLoadData, "package_load"),
        (AlternateFlightData, "alternate_flights"),
        (NetworkStatusData, "operations_status"),
    )
    parsed = {key: model.model_validate_json(json.dumps(source[key])) for model, key in models}
    return make_adapters(
        parsed["flight_schedule"],
        parsed["fleet_availability"],
        parsed["package_load"],
        parsed["operations_status"],
        alternates=parsed["alternate_flights"],
        retrieved_at=EVALUATED_AT,
    )


def test_controller_accepts_every_evidence_reference_the_maintenance_input_defines() -> None:
    """Need-by, parts-readiness, and dependency references are valid citations (ARD-GOV-004)."""
    maintenance_data = MaintenanceAssessmentInput.model_validate_json(
        json.dumps(load_json("maintenance_agent.json")["input"])
    )

    evidence_ids = _maintenance_evidence_ids(maintenance_data)

    assert {"NEED-BY-1042", "QUOTE-P120-REMOTE-1042", "APPROVAL-P120-1042"} <= evidence_ids


@pytest.mark.asyncio
async def test_controller_coordinates_specialists_and_passes_their_eta_to_operations() -> None:
    (
        workflow,
        intake,
        maintenance_data,
        materials_data,
        operations_request,
        recorder,
        maintenance_fake,
        materials_fake,
    ) = workflow_fixture()

    result = await workflow.assess_candidate(
        intake,
        maintenance_data,
        materials_data,
        operations_request,
        operations_adapters(),
        "OPT-REPAIR-P120-REMOTE",
    )

    assert maintenance_fake.calls == 1
    assert materials_fake.calls == 1
    assert result.status is ControllerWorkflowStatus.PARTIAL
    assert result.peer_exchange is not None
    assert result.peer_exchange.request.preferred_part_number == "P-120"
    assert result.peer_exchange.response.status is ExchangeStatus.COMPLETE
    assert result.peer_recording is not None
    assert result.peer_recording.error is None
    recorded = recorder.records_for(
        intake.case.case_id,
        result.peer_exchange.request.exchange_id,
    )
    assert len(recorded) == 2
    assert result.operations_outcome is not None
    assert result.operations_outcome.result.agent_role is AgentRole.OPERATIONS
    assert result.operations_outcome.assessment is not None
    [option] = result.operations_outcome.assessment.recovery_options
    assert option.earliest_feasible_departure == datetime(2026, 10, 22, 16, 30, tzinfo=UTC)
    assert result.operations_outcome.assessment.human_approval_required is True
    assert "readiness ETA is an estimate, not confirmed" in (
        result.operations_outcome.assessment.confidence_reasons
    )


def workflow_fixture(
    *,
    maintenance_result_override: AgentResult | None = None,
    materials_data: MaterialsLogisticsAssessmentInput | None = None,
    materials_result_override: AgentResult | None = None,
) -> tuple[
    ControllerWorkflow,
    ControllerIntake,
    MaintenanceAssessmentInput,
    MaterialsLogisticsAssessmentInput,
    OperationsRequest,
    InMemoryCaseContextRecorder,
    FakeAssessor,
    FakeAssessor,
]:
    intake = controller_intake()
    maintenance_data = MaintenanceAssessmentInput.model_validate_json(
        json.dumps(load_json("maintenance_agent.json")["input"])
    )
    if materials_data is None:
        materials_scenario = next(
            item
            for item in load_json("materials_logistics_agent.json")["scenarios"]
            if item["scenario_id"] == "part_available_remote"
        )
        materials_data = MaterialsLogisticsAssessmentInput.model_validate_json(
            json.dumps(materials_scenario["input"])
        )
    maintenance_fake = FakeAssessor(
        maintenance_result_override or maintenance_result(maintenance_data)
    )
    materials_fake = FakeAssessor(materials_result_override or materials_result(materials_data))
    recorder = InMemoryCaseContextRecorder()
    workflow = ControllerWorkflow(
        maintenance_fake,
        materials_fake,
        InMemoryCaseContextStore().start_case(intake),
        recorder,
    )
    operations_request = OperationsRequest(
        schema_version="1.0",
        request_id="REQ-OPS-REMOTE-1042",
        case=intake.case,
        affected_flight_numbers=("FX103",),
        candidates=(
            CandidateOption(
                option_id="OPT-REPAIR-P120-REMOTE",
                kind=OptionKind.REPAIR_ALTERNATE,
                description="Repair using approved P-120 transferred from DFW.",
                eta_basis=None,
                eta_evidence_references=(),
            ),
        ),
        evaluated_at=EVALUATED_AT,
    )
    return (
        workflow,
        intake,
        maintenance_data,
        materials_data,
        operations_request,
        recorder,
        maintenance_fake,
        materials_fake,
    )


async def run_workflow_fixture(
    *,
    maintenance_result_override: AgentResult | None = None,
    materials_data: MaterialsLogisticsAssessmentInput | None = None,
    materials_result_override: AgentResult | None = None,
):
    (
        workflow,
        intake,
        maintenance_data,
        materials_input,
        operations_request,
        recorder,
        _,
        _,
    ) = workflow_fixture(
        maintenance_result_override=maintenance_result_override,
        materials_data=materials_data,
        materials_result_override=materials_result_override,
    )
    result = await workflow.assess_candidate(
        intake,
        maintenance_data,
        materials_input,
        operations_request,
        operations_adapters(),
        "OPT-REPAIR-P120-REMOTE",
    )
    return result, recorder


@pytest.mark.asyncio
async def test_failed_specialist_stays_failed_and_creates_structured_controller_error() -> None:
    failed_maintenance = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MAINTENANCE,
        status=AgentResultStatus.FAILED,
        summary="Maintenance history source is unavailable.",
        confidence=0.0,
        assumptions=(),
        evidence_references=(),
        role_payload={"error_category": "maintenance_history_unavailable"},
    )

    result, _ = await run_workflow_fixture(maintenance_result_override=failed_maintenance)

    assert result.status is ControllerWorkflowStatus.PARTIAL
    assert result.operations_outcome is None
    assert result.errors[0].category == "maintenance_failed"
    assert result.warnings[0].code == "SPECIALIST_FAILED"
    assert "failed_specialist_analysis" in result.missing_data


@pytest.mark.asyncio
async def test_stale_materials_evidence_remains_visible_and_partial() -> None:
    materials_scenario = next(
        item
        for item in load_json("materials_logistics_agent.json")["scenarios"]
        if item["scenario_id"] == "part_available_remote"
    )
    materials_input = MaterialsLogisticsAssessmentInput.model_validate_json(
        json.dumps(materials_scenario["input"])
    )
    warning = EvidenceWarning(
        warning_id="stale-P120-1042",
        claim_reference="INV-P120-DFW-1042",
        code="STALE_EVIDENCE",
        message="P-120 inventory data is stale.",
        source_reference="mock_inventory",
    )
    stale_records = tuple(
        record.model_copy(update={"validity_state": EvidenceValidity.STALE})
        if record.part_number == "P-120"
        else record
        for record in materials_input.assessment.part_availability
    )
    materials_input = materials_input.model_copy(
        update={
            "assessment": materials_input.assessment.model_copy(
                update={"part_availability": stale_records}
            ),
            "evidence_summary": materials_input.evidence_summary.model_copy(
                update={
                    "status": ToolResultStatus.PARTIAL,
                    "confidence": 0.62,
                    "warnings": (warning,),
                }
            ),
        }
    )
    stale_result = materials_result(
        materials_input,
        status=AgentResultStatus.PARTIAL,
        confidence=0.62,
    )

    result, _ = await run_workflow_fixture(
        materials_data=materials_input,
        materials_result_override=stale_result,
    )

    assert result.status is ControllerWorkflowStatus.PARTIAL
    assert any(item.code == "STALE_EVIDENCE" for item in result.warnings)
    assert result.peer_exchange is not None
    assert result.peer_exchange.response.status is ExchangeStatus.PARTIAL


@pytest.mark.asyncio
async def test_conflicting_materials_evidence_escalates_and_remains_visible() -> None:
    materials_scenario = next(
        item
        for item in load_json("materials_logistics_agent.json")["scenarios"]
        if item["scenario_id"] == "part_available_remote"
    )
    materials_input = MaterialsLogisticsAssessmentInput.model_validate_json(
        json.dumps(materials_scenario["input"])
    )
    warning = EvidenceWarning(
        warning_id="conflicting-P120-1042",
        claim_reference="INV-P120-DFW-1042",
        code="CONFLICTING_DATA",
        message="Two inventory sources disagree about P-120 stock.",
        source_reference="mock_inventory",
    )
    materials_input = materials_input.model_copy(
        update={
            "evidence_summary": materials_input.evidence_summary.model_copy(
                update={
                    "status": ToolResultStatus.PARTIAL,
                    "warnings": (warning,),
                }
            )
        }
    )
    conflict_result = materials_result(
        materials_input,
        status=AgentResultStatus.ESCALATION_REQUIRED,
    )

    result, _ = await run_workflow_fixture(
        materials_data=materials_input,
        materials_result_override=conflict_result,
    )

    assert result.status is ControllerWorkflowStatus.ESCALATED
    assert result.specialist_conflicts == (warning.message,)
    assert warning in result.warnings


@pytest.mark.asyncio
async def test_remote_stock_synthetic_case_flows_through_controller_to_chat_brief() -> None:
    (
        workflow,
        intake,
        maintenance_data,
        materials_data,
        operations_request,
        _,
        _,
        _,
    ) = workflow_fixture()
    maintenance_payload = MaintenanceAssessmentPayload.model_validate_json(
        json.dumps(maintenance_result(maintenance_data).role_payload)
    )
    evidence_references = tuple(
        evidence.evidence_id
        for evidence in (
            *maintenance_data.maintenance_history,
            *maintenance_data.engineering_constraints,
            *maintenance_data.safety_conditions,
            maintenance_data.aircraft_metadata,
            (
                maintenance_data.work_order.evidence
                if maintenance_data.work_order is not None
                else None
            ),
        )
        if evidence is not None
    )
    plans = build_recovery_candidates(
        CandidateBuildContext(
            schema_version="1.0",
            case=intake.case,
            request_id=intake.request_id,
            evaluated_at=intake.evaluated_at,
            failed_part_number=intake.failed_part_number,
            preferred_replacement_part="P-120",
            estimated_repair_duration_hours=3.0,
            maintenance_evidence_references=evidence_references,
            materials_assessment=materials_data.assessment,
        )
    )
    request = operations_request.model_copy(
        update={"candidates": tuple(plan.option for plan in plans)}
    )
    executions = tuple(
        await asyncio.gather(
            *(
                workflow.assess_candidate(
                    intake,
                    maintenance_data,
                    materials_data,
                    request,
                    operations_adapters(),
                    plan.option.option_id,
                )
                for plan in plans
            )
        )
    )
    eligibility = apply_compliance_gate(plans, maintenance_payload.approval_evidence)
    scoring_inputs = []
    for plan in eligibility.eligible_candidates:
        execution = next(
            item for item in executions if item.candidate_option_id == plan.option.option_id
        )
        assert execution.operations_outcome is not None
        assert execution.operations_outcome.assessment is not None
        [operation] = execution.operations_outcome.assessment.recovery_options
        package = operation.package
        costs = operation.cost
        scoring_inputs.append(
            CandidateScoringInput(
                option_id=plan.option.option_id,
                return_to_service_hours=(
                    (operation.earliest_feasible_departure - intake.evaluated_at).total_seconds()
                    / 3600.0
                    if operation.earliest_feasible_departure is not None
                    else None
                ),
                impact_level=operation.impact_level,
                total_package_count=package.affected_package_count,
                priority_package_count=package.time_critical_package_count,
                unprotected_package_count=package.unprotected_count,
                unprotected_priority_package_count=package.unprotected_time_critical_count,
                maintenance_risk_levels=(
                    maintenance_payload.risk_metrics.delay_risk,
                    maintenance_payload.risk_metrics.parts_dependency_risk,
                    maintenance_payload.risk_metrics.repair_complexity_risk,
                ),
                risk_factors=maintenance_payload.technical_risks,
                repair_labor_cost_usd=(
                    maintenance_payload.estimated_repair_labor_cost_usd
                    if plan.option.kind is not OptionKind.SWAP
                    else Decimal("0")
                ),
                part_and_sourcing_cost_usd=(
                    plan.sourcing_option.estimated_cost_usd
                    if plan.sourcing_option is not None
                    else Decimal("0")
                ),
                operations_cost_usd=(
                    Decimal(costs.total_usd) if costs is not None and costs.complete else None
                ),
            )
        )
    scored = score_candidates(
        ComplianceGateResult(
            eligible_candidates=eligibility.eligible_candidates,
            excluded_options=eligibility.excluded_options,
        ),
        tuple(scoring_inputs),
    )
    brief = build_decision_brief(executions, scored, "AOG-MOCK-1042-demo-v1")
    chat_response = render_decision_brief(brief)

    assert len(executions) == len(plans)
    assert any(item.peer_recording is not None for item in executions)
    assert all(item.operations_outcome is not None for item in executions)
    assert brief.human_approval_required is True
    assert "Advisory only" in chat_response
    assert "human approval is required" in chat_response.casefold()
    assert "P-120" in chat_response
    assert "part_available_remote" not in chat_response
