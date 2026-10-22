"""Full Controller workflow over deterministic synthetic specialist and Operations ports."""

from datetime import timedelta
from decimal import Decimal

from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole, StructuredError
from aog_recovery.contracts.evidence import EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.context import (
    ControllerAuditRecorder,
    ControllerCaseContextRecorder,
    InMemoryControllerContextStore,
)
from aog_recovery.controller.demo import DEMO_TIME, DemoScenario, build_demo_intake
from aog_recovery.controller.operations_adapter import BoundedAsyncOperationsAdapter
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
    RecurringFailureSummary,
    RepairabilityStatus,
)
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartRole,
    TraceabilityStatus,
)
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import default_adapters


class _SyntheticMaintenancePort:
    def __init__(self, scenario: DemoScenario) -> None:
        self._scenario = scenario

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        available = set(request.available_evidence_ids)
        history_references = tuple(
            reference
            for reference in (
                "maintenance-history-P110-1",
                "maintenance-history-P110-2",
                "maintenance-history-P110-3",
            )
            if reference in available
        )
        evidence_references = tuple(
            sorted(
                available.intersection(
                    {
                        "approval-evidence-001",
                        "eta-evidence-001",
                        "engineering-preference-P120",
                        "need-by-P120",
                        "parts-ready-P120",
                        *history_references,
                    }
                )
            )
        )
        repair_hours = 3.0 if self._scenario is DemoScenario.TIME_CONFLICT else 2.0
        return_time = DEMO_TIME + timedelta(hours=repair_hours)
        maintenance_payload = MaintenanceAssessmentPayload(
            schema_version="1.0",
            repairability_status=RepairabilityStatus.FEASIBLE,
            root_cause=None,
            recurring_failure=RecurringFailureSummary(
                part_number="P-110",
                occurrences=3,
                window_days=90,
                evidence_references=history_references,
            ),
            preferred_replacement_part="P-120",
            preferred_replacement_evidence_references=("engineering-preference-P120",),
            required_actions=("replace_hydraulic_pump",),
            estimated_ground_time_hours=repair_hours,
            ground_time_unavailable_reason=None,
            estimated_repair_labor_cost_usd=Decimal("125.00"),
            need_by_time=DEMO_TIME + timedelta(hours=8),
            parts_ready_at=DEMO_TIME,
            return_to_service_time=return_time,
            meets_need_by_time=True,
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
                status=ApprovalEvidenceStatus.APPROVAL_RECORDED,
                approver_role="maintenance_airworthiness_authority",
                source_reference="approval-evidence-001",
                recorded_at=DEMO_TIME,
            ),
            recommendation=MaintenanceRecommendation(
                decision=MaintenanceRecommendationDecision.REPAIR,
                confidence=0.95,
                rationale="Synthetic maintenance evidence supports the replacement repair path.",
                next_steps=("Human review is required before any operational action.",),
            ),
        )
        return AgentResult(
            schema_version="1.0",
            agent_role=AgentRole.MAINTENANCE,
            status=AgentResultStatus.COMPLETE,
            summary="Synthetic Maintenance assessment for P-110 and preferred P-120.",
            confidence=0.95,
            assumptions=(),
            evidence_references=evidence_references,
            role_payload=maintenance_payload.model_dump(mode="json"),
        )


class _SyntheticMaterialsPort:
    def __init__(self, scenario: DemoScenario) -> None:
        self._scenario = scenario

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        candidate = request.candidate
        sourcing = candidate.sourcing_options[0]
        cached = self._scenario is DemoScenario.CACHE_DEGRADED
        inventory_evidence = "inventory-cache-p120" if cached else "inventory-live-p120"
        warning = EvidenceWarning(
            warning_id=f"{candidate.candidate.option_id}-cached-inventory",
            claim_reference="inventory-availability-p120",
            code="CACHED_EVIDENCE",
            message="Live inventory is unavailable; P-120 quantity comes from stale cache.",
            source_reference="synthetic-inventory-cache",
        )
        source_error = StructuredError(
            schema_version="1.0",
            category="source_unavailable",
            component="materials-adapter:part_inventory",
            message="Synthetic live inventory source is unavailable.",
            retryable=False,
            case_impact="Material readiness uses explicitly degraded cached evidence.",
        )
        evidence_summary = MaterialsEvidenceSummary(
            status=ToolResultStatus.PARTIAL if cached else ToolResultStatus.SUCCESS,
            confidence=0.72 if cached else 0.95,
            evidence_references=(inventory_evidence, "part-eligibility-001", "quote-P120"),
            warnings=(warning,) if cached else (),
            errors=(source_error,) if cached else (),
        )
        materials_payload = MaterialsLogisticsAgentPayload(
            schema_version="1.0",
            assessment=MaterialsLogisticsAssessmentPayload(
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
                        retrieved_at=DEMO_TIME,
                        validity_state=EvidenceValidity.CURRENT,
                        claim_reference="inventory-availability-p110",
                    ),
                    PartAvailabilityRecord(
                        part_number="P-120",
                        role=PartRole.PREFERRED_REPLACEMENT,
                        required_quantity=1,
                        available_quantity=1,
                        minimum_stock_threshold=1,
                        location="TEST-STATION-B",
                        source="synthetic-inventory-cache" if cached else "synthetic-inventory",
                        retrieved_at=DEMO_TIME - timedelta(days=1) if cached else DEMO_TIME,
                        validity_state=EvidenceValidity.STALE
                        if cached
                        else EvidenceValidity.CURRENT,
                        claim_reference="inventory-availability-p120",
                    ),
                ),
                part_eligibility=(
                    PartEligibilityEvidence(
                        part_number="P-120",
                        compatibility=CompatibilityStatus.COMPATIBLE,
                        authorization=AuthorizationStatus.AUTHORIZED,
                        traceability=TraceabilityStatus.VERIFIED,
                        checked_by_role="materials_inventory_specialist",
                        evidence_references=("part-eligibility-001",),
                    ),
                ),
                sourcing_options=(sourcing,),
                confidence=0.72 if cached else 0.95,
                risk_factors=(),
                assumptions=(),
                missing_data=(),
            ),
            evidence_summary=evidence_summary,
        )
        result_evidence = tuple(
            sorted(
                set(evidence_summary.evidence_references).intersection(
                    request.available_evidence_ids
                )
            )
        )
        return AgentResult(
            schema_version="1.0",
            agent_role=AgentRole.MATERIALS_LOGISTICS,
            status=AgentResultStatus.PARTIAL if cached else AgentResultStatus.COMPLETE,
            summary=(
                "Materials assessment uses stale cached inventory."
                if cached
                else "Synthetic Materials assessment verifies P-120 availability and eligibility."
            ),
            confidence=0.72 if cached else 0.95,
            assumptions=(),
            evidence_references=result_evidence,
            role_payload=materials_payload.model_dump(mode="json"),
        )


async def run_controller_demo_workflow(scenario: DemoScenario) -> ControllerWorkflowResult:
    """Run one named synthetic case through the real deterministic Controller workflow."""
    context_store = InMemoryControllerContextStore()
    context_recorder = ControllerCaseContextRecorder(context_store)
    workflow = ControllerWorkflow(
        _SyntheticMaintenancePort(scenario),
        _SyntheticMaterialsPort(scenario),
        BoundedAsyncOperationsAdapter(
            OperationsAgent(
                default_adapters(),
                settings=OperationsSettings.model_validate({}),
            ),
            settings=AogSettings.model_validate({}),
        ),
        context_recorder,
        settings=AogSettings.model_validate({}),
        audit_recorder=ControllerAuditRecorder(context_store),
        clock=lambda: DEMO_TIME,
    )
    intake = build_demo_intake(scenario)
    return await workflow.run(intake.model_dump(mode="json"))
