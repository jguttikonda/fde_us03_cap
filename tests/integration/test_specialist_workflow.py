import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.coordination.models import DegradationStatus, ExchangeStatus
from aog_recovery.coordination.recording import (
    ExchangeDirection,
    ExchangeRecordingStatus,
    InMemoryCaseContextRecorder,
)
from aog_recovery.coordination.workflow import (
    CoordinatedPeerExchange,
    build_h3_request,
    coordinate_h3_h4,
)
from aog_recovery.maintenance.agent import (
    MaintenanceAgent,
    MaintenanceGroundingOutput,
    MaintenancePromptStage,
    MaintenanceReasoningOutput,
)
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentInput,
    MaintenanceAssessmentPayload,
    MaintenancePartDependency,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    MaintenanceWorkOrder,
    RecurringFailureSummary,
    RepairabilityStatus,
    RootCauseEvidence,
    WorkOrderStatus,
)
from aog_recovery.materials_logistics.agent import (
    MaterialsFinalOutput,
    MaterialsGroundingOutput,
    MaterialsLogisticsAgent,
    MaterialsLogisticsAgentPayload,
    MaterialsLogisticsAssessmentInput,
    MaterialsPromptStage,
    MaterialsReasoningOutput,
)
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartRole,
    ShippingProvider,
    SourcingMethod,
    SourcingOption,
    TraceabilityStatus,
)
from aog_recovery.observability.structured import LOGGER

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class FakeMaintenanceRunner:
    def __init__(self, outputs: tuple[BaseModel, ...]) -> None:
        self.outputs = list(outputs)
        self.stages: list[MaintenancePromptStage] = []

    async def run_stage(
        self,
        stage: MaintenancePromptStage,
        payload: Mapping[str, object],
    ) -> BaseModel | Mapping[str, object]:
        self.stages.append(stage)
        return self.outputs.pop(0)


class FakeMaterialsRunner:
    def __init__(self, outputs: tuple[BaseModel, ...]) -> None:
        self.outputs = list(outputs)
        self.stages: list[MaterialsPromptStage] = []

    async def run_stage(
        self,
        stage: MaterialsPromptStage,
        payload: Mapping[str, object],
    ) -> BaseModel | Mapping[str, object]:
        self.stages.append(stage)
        return self.outputs.pop(0)


def make_case() -> AogCase:
    return AogCase(
        case_id="case-integrated-001",
        aircraft_id="TEST-AIRCRAFT-001",
        event_type="synthetic_aog",
        defect_summary="Synthetic hydraulic pump failure",
        location="TEST-STATION-A",
        event_at=TIMESTAMP,
        created_at=TIMESTAMP,
        schema_version="1.0",
        trace_context=TraceContext(
            trace_id="trace-integrated-001", correlation_id="corr-integrated-001"
        ),
    )


def source_evidence(
    evidence_id: str,
    *,
    content: dict[str, object] | None = None,
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source=f"synthetic-{evidence_id}",
        retrieved_at=TIMESTAMP,
        validity_state=validity,
        claim_reference=f"claim-{evidence_id}",
        content=content or {"state": "synthetic"},
    )


def maintenance_input() -> MaintenanceAssessmentInput:
    history = tuple(
        source_evidence(
            f"history-P110-{index}",
            content={
                "part_number": "P-110",
                "occurred_at": TIMESTAMP - timedelta(days=day_offset),
            },
        )
        for index, day_offset in enumerate((89, 45, 0), start=1)
    )
    work_order_evidence = source_evidence("work-order-evidence")
    engineering_evidence = source_evidence("engineering-preference-P120")
    safety_evidence = source_evidence("safety-approval-evidence")
    case = make_case()
    return MaintenanceAssessmentInput(
        schema_version="1.0",
        case=case,
        need_by_time=TIMESTAMP + timedelta(hours=5),
        need_by_evidence_reference="schedule-need-by-P120",
        parts_ready_at=TIMESTAMP,
        parts_readiness_evidence_reference="inventory-eta-P120",
        aircraft_metadata=source_evidence(
            "aircraft-metadata", content={"aircraft_id": case.aircraft_id}
        ),
        work_order=MaintenanceWorkOrder(
            work_order_id="work-order-P110",
            aircraft_id=case.aircraft_id,
            status=WorkOrderStatus.OPEN,
            required_actions=("replace_hydraulic_pump",),
            estimated_repair_duration_hours=4.0,
            evidence=work_order_evidence,
        ),
        maintenance_history=history,
        engineering_constraints=(engineering_evidence,),
        safety_conditions=(safety_evidence,),
        part_dependencies=(
            MaintenancePartDependency(
                part_number="P-110",
                required_quantity=1,
                required_before_repair=True,
                evidence_references=(work_order_evidence.evidence_id,),
            ),
        ),
        missing_data=(),
    )


def maintenance_runner_outputs(
    assessment_input: MaintenanceAssessmentInput,
) -> tuple[BaseModel, ...]:
    evidence_ids = tuple(
        item.evidence_id
        for item in (
            *assessment_input.maintenance_history,
            *assessment_input.engineering_constraints,
            *assessment_input.safety_conditions,
            *((assessment_input.work_order.evidence,) if assessment_input.work_order else ()),
        )
    )
    grounding = MaintenanceGroundingOutput(
        evidence_summary="Synthetic P-110 history and engineering-supported P-120 replacement",
        evidence_references=evidence_ids,
        missing_data=(),
        assumptions=(),
        confidence_level=0.82,
    )
    reasoning = MaintenanceReasoningOutput(
        repairability_status=RepairabilityStatus.FEASIBLE,
        findings=("P-110 replacement path supported",),
        rationale="Three matching failures support evaluating preferred P-120",
        technical_risks=(),
        confidence=0.82,
    )
    payload = MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.FEASIBLE,
        root_cause=RootCauseEvidence(
            category="synthetic_hydraulic_pump_failure",
            confidence=0.82,
            evidence_references=("work-order-evidence",),
        ),
        recurring_failure=RecurringFailureSummary(
            part_number="P-110",
            occurrences=3,
            window_days=90,
            evidence_references=tuple(
                item.evidence_id for item in assessment_input.maintenance_history
            ),
        ),
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("engineering-preference-P120",),
        required_actions=("replace_hydraulic_pump",),
        estimated_ground_time_hours=4.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("125.00"),
        need_by_time=assessment_input.need_by_time,
        parts_ready_at=assessment_input.parts_ready_at,
        return_to_service_time=TIMESTAMP + timedelta(hours=4),
        meets_need_by_time=True,
        eta_confidence=0.82,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.LOW,
            parts_dependency_risk=MaintenanceRiskLevel.MEDIUM,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.APPROVAL_RECORDED,
            approver_role="maintenance_airworthiness_authority",
            source_reference="safety-approval-evidence",
            recorded_at=TIMESTAMP,
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.REPAIR,
            confidence=0.82,
            rationale="Synthetic supported repair path",
            next_steps=("Human operational approval remains required",),
        ),
    )
    return grounding, reasoning, payload


def materials_input(
    *,
    stale: bool = False,
) -> MaterialsLogisticsAssessmentInput:
    validity = EvidenceValidity.STALE if stale else EvidenceValidity.CURRENT
    warning = (
        (
            EvidenceWarning(
                warning_id="stale-P120-inventory",
                claim_reference="inventory-claim-P120",
                code="STALE_EVIDENCE",
                message="cached P-120 inventory is stale",
                source_reference="synthetic-inventory",
            ),
        )
        if stale
        else ()
    )
    materials_payload = MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.AVAILABLE,
        part_availability=(
            PartAvailabilityRecord(
                part_number="P-110",
                role=PartRole.FAILED_PART,
                required_quantity=1,
                available_quantity=0,
                minimum_stock_threshold=0,
                location="TEST-STATION-A",
                source="synthetic-inventory",
                retrieved_at=TIMESTAMP,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="inventory-claim-P110",
            ),
            PartAvailabilityRecord(
                part_number="P-120",
                role=PartRole.PREFERRED_REPLACEMENT,
                required_quantity=1,
                available_quantity=4,
                minimum_stock_threshold=1,
                location="TEST-STATION-A",
                source="synthetic-inventory",
                retrieved_at=TIMESTAMP,
                validity_state=validity,
                claim_reference="inventory-claim-P120",
            ),
        ),
        part_eligibility=(
            PartEligibilityEvidence(
                part_number="P-120",
                compatibility=CompatibilityStatus.COMPATIBLE,
                authorization=AuthorizationStatus.AUTHORIZED,
                traceability=TraceabilityStatus.VERIFIED,
                checked_by_role="materials_inventory_specialist",
                evidence_references=("eligibility-P120",),
            ),
        ),
        sourcing_options=(
            SourcingOption(
                part_number="P-120",
                source="synthetic-stock-location",
                source_location="TEST-STATION-A",
                method=SourcingMethod.INTERNAL_TRANSFER,
                shipping_provider=ShippingProvider.FEDEX_NETWORK,
                shipping_service="priority_freight",
                transfer_required=False,
                lead_time_hours=1.0,
                eta_at=TIMESTAMP + timedelta(hours=1),
                estimated_cost_usd=Decimal("20.00"),
                quote_unavailable_reason=None,
                evidence_references=("quote-P120",),
            ),
        ),
        confidence=0.82,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
    )
    summary = MaterialsEvidenceSummary(
        status=ToolResultStatus.PARTIAL if stale else ToolResultStatus.SUCCESS,
        confidence=0.72 if stale else 0.82,
        evidence_references=(
            "inventory-claim-P110",
            "inventory-claim-P120",
            "eligibility-P120",
            "quote-P120",
        ),
        warnings=warning,
        errors=(),
    )
    return MaterialsLogisticsAssessmentInput(
        schema_version="1.0",
        case=make_case(),
        assessment=materials_payload,
        evidence_summary=summary,
    )


def materials_runner_outputs(
    assessment_input: MaterialsLogisticsAssessmentInput,
) -> tuple[BaseModel, ...]:
    references = assessment_input.evidence_summary.evidence_references
    grounding = MaterialsGroundingOutput(
        evidence_summary="Synthetic P-110/P-120 inventory and quote evidence",
        evidence_references=references,
        missing_data=(),
        assumptions=(),
        confidence_level=assessment_input.evidence_summary.confidence,
    )
    reasoning = MaterialsReasoningOutput(
        summary="P-120 has the supported local sourcing path",
        risk_factors=(),
        assumptions=(),
        missing_data=(),
        confidence=assessment_input.evidence_summary.confidence,
    )
    final = MaterialsFinalOutput(
        summary="P-110/P-120 comparison is ready for Controller review",
        evidence_references=references,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
        confidence=assessment_input.evidence_summary.confidence,
    )
    return grounding, reasoning, final


async def run_integrated_scenario(
    *,
    stale: bool = False,
    recorder: InMemoryCaseContextRecorder | None = None,
) -> tuple[AgentResult, AgentResult, CoordinatedPeerExchange]:
    maintenance_data = maintenance_input()
    maintenance_runner = FakeMaintenanceRunner(maintenance_runner_outputs(maintenance_data))
    maintenance_result = await MaintenanceAgent(maintenance_runner).assess(
        maintenance_data.model_dump(mode="python")
    )
    maintenance_payload = MaintenanceAssessmentPayload.model_validate_json(
        json.dumps(maintenance_result.role_payload)
    )

    materials_data = materials_input(stale=stale)
    materials_runner = FakeMaterialsRunner(materials_runner_outputs(materials_data))
    materials_result = await MaterialsLogisticsAgent(materials_runner).assess(
        materials_data.model_dump(mode="python")
    )
    materials_agent_payload = MaterialsLogisticsAgentPayload.model_validate_json(
        json.dumps(materials_result.role_payload)
    )

    peer_request = build_h3_request(
        make_case(),
        maintenance_payload,
        failed_part_number="P-110",
        exchange_id="exchange-integrated-001",
        request_id="request-integrated-001",
        sent_at=TIMESTAMP,
        source_evidence=(
            *maintenance_data.maintenance_history,
            *maintenance_data.engineering_constraints,
            *maintenance_data.safety_conditions,
        ),
    )
    coordinated = coordinate_h3_h4(
        peer_request,
        materials_agent_payload.assessment,
        materials_agent_payload.evidence_summary,
        response_id="response-integrated-001",
        responded_at=TIMESTAMP + timedelta(minutes=1),
        recorder=recorder or InMemoryCaseContextRecorder(),
    )
    assert maintenance_runner.stages == list(MaintenancePromptStage)
    assert materials_runner.stages == list(MaterialsPromptStage)
    return maintenance_result, materials_result, coordinated


@pytest.mark.asyncio
async def test_both_specialists_complete_synthetic_a2a_with_correlated_audit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = InMemoryCaseContextRecorder()

    with caplog.at_level("INFO", logger=LOGGER.name):
        maintenance, materials, coordinated = await run_integrated_scenario(recorder=recorder)

    exchange = coordinated.exchange
    assert maintenance.status is AgentResultStatus.COMPLETE
    assert materials.status is AgentResultStatus.COMPLETE
    assert exchange.request.recurring_failure_count == 3
    assert exchange.request.recurring_failure_window_days == 90
    assert exchange.request.preferred_part_number == "P-120"
    assert exchange.response.status is ExchangeStatus.COMPLETE
    assert exchange.response.part_comparison.failed_part_assessments[0].availability_status is (
        AvailabilityStatus.UNAVAILABLE
    )
    assert exchange.response.part_comparison.preferred_part_assessments[0].eligible is True
    assert coordinated.recording.status is ExchangeRecordingStatus.COMPLETE
    assert [record.direction for record in recorder.records] == [
        ExchangeDirection.REQUEST,
        ExchangeDirection.RESPONSE,
    ]
    events = [json.loads(record.message) for record in caplog.records]
    assert [event["details"]["direction"] for event in events] == ["request", "response"]
    assert {event["case_id"] for event in events} == {"case-integrated-001"}
    assert {event["request_id"] for event in events} == {"exchange-integrated-001"}
    assert {event["trace_context"]["correlation_id"] for event in events} == {"corr-integrated-001"}
    assert not hasattr(MaintenanceAgent(FakeMaintenanceRunner(())), "approve")
    assert not hasattr(MaterialsLogisticsAgent(FakeMaterialsRunner(())), "purchase")


@pytest.mark.asyncio
async def test_stale_materials_evidence_reaches_integrated_h4_without_approval() -> None:
    maintenance, materials, coordinated = await run_integrated_scenario(stale=True)

    assert maintenance.status is AgentResultStatus.COMPLETE
    assert materials.status is AgentResultStatus.PARTIAL
    assert materials.confidence == 0.72
    assert coordinated.exchange.response.status is ExchangeStatus.PARTIAL
    assert coordinated.exchange.response.degradation_status is DegradationStatus.STALE
    assert coordinated.exchange.response.confidence == 0.72
    assert coordinated.exchange.response.warnings[0].code == "STALE_EVIDENCE"
    assert coordinated.recording.status is ExchangeRecordingStatus.COMPLETE
