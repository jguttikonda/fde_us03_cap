"""ADK Web demo service for the local synthetic AOG recovery workflow."""

import asyncio
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.adk.prompt_runner import GoogleAdkPromptRunner
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import Evidence
from aog_recovery.contracts.tool import ToolName
from aog_recovery.controller.adk_agent import ControllerAssessmentService
from aog_recovery.controller.brief import build_decision_brief, render_decision_brief
from aog_recovery.controller.candidates import build_recovery_candidates
from aog_recovery.controller.compliance import apply_compliance_gate
from aog_recovery.controller.intake import InMemoryCaseContextStore, validate_controller_intake
from aog_recovery.controller.models import (
    CandidateBuildContext,
    CandidateScoringInput,
    ComplianceGateResult,
    ControllerCandidateExecution,
    ControllerDecisionBrief,
    ControllerIntake,
    ExcludedOption,
    RecoveryCandidatePlan,
)
from aog_recovery.controller.scoring import score_candidates
from aog_recovery.controller.workflow import ControllerWorkflow, SpecialistAssessor
from aog_recovery.coordination.recording import InMemoryCaseContextRecorder
from aog_recovery.maintenance.agent import GoogleAdkMaintenancePromptRunner, MaintenanceAgent
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentInput,
    MaintenanceAssessmentPayload,
    MaintenanceRiskLevel,
)
from aog_recovery.materials_logistics.agent import (
    GoogleAdkMaterialsPromptRunner,
    MaterialsLogisticsAgent,
    MaterialsLogisticsAssessmentInput,
)
from aog_recovery.materials_logistics.models import PartRole
from aog_recovery.operations.models import (
    AlternateFlightData,
    FleetAvailabilityData,
    FlightScheduleData,
    NetworkStatusData,
    OperationsRequest,
    OptionKind,
    PackageLoadData,
    PackageServiceLevel,
    RecoveryOptionAssessment,
)
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import make_adapters

_SCENARIOS = frozenset({"part_available_local", "part_available_remote", "part_unavailable"})
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ROOT = _REPOSITORY_ROOT / "incidents" / "mock_data"


class DemoControllerService(ControllerAssessmentService):
    """Run the Controller workflow with local mock sources and existing ADK specialists."""

    def __init__(
        self,
        maintenance_agent: SpecialistAssessor | None = None,
        materials_agent: SpecialistAssessor | None = None,
    ) -> None:
        model_name = OperationsSettings().adk_model
        prompt_runner = GoogleAdkPromptRunner(model_name)
        self._maintenance = maintenance_agent or MaintenanceAgent(
            GoogleAdkMaintenancePromptRunner(prompt_runner)
        )
        self._materials = materials_agent or MaterialsLogisticsAgent(
            GoogleAdkMaterialsPromptRunner(prompt_runner)
        )

    async def assess(self, payload: Mapping[str, object]) -> dict[str, object]:
        scenario_id = payload.get("scenario_id", "part_available_remote")
        if not isinstance(scenario_id, str) or scenario_id not in _SCENARIOS:
            return {
                "status": "rejected",
                "findings": [
                    {
                        "field_path": "scenario_id",
                        "code": "unknown_synthetic_scenario",
                        "message": f"Choose one of: {', '.join(sorted(_SCENARIOS))}.",
                    }
                ],
                "chat_response": (
                    "I can't run the assessment because that synthetic scenario is not available. "
                    f"Choose one of: {', '.join(sorted(_SCENARIOS))}."
                ),
                "human_approval_required": True,
            }

        intake_payload = {key: value for key, value in payload.items() if key != "scenario_id"}
        validation = validate_controller_intake(intake_payload)
        if validation.intake is None:
            return {
                "status": "awaiting_data",
                "findings": [finding.model_dump(mode="json") for finding in validation.findings],
                "chat_response": (
                    "Please provide the missing or corrected case details listed below. "
                    "No specialist assessment has run yet.\n"
                    + "\n".join(
                        f"- {finding.field_path}: {finding.message}"
                        for finding in validation.findings
                    )
                ),
                "human_approval_required": True,
            }

        try:
            result = await self._assess_validated(validation.intake, scenario_id)
        except Exception as error:
            return {
                "status": "failed",
                "case_id": validation.intake.case.case_id,
                "error": {
                    "category": "controller_assessment_failed",
                    "component": "controller-demo-service",
                    "error_type": type(error).__name__,
                    "retryable": False,
                },
                "warnings": [
                    f"Controller assessment failed: {type(error).__name__}. "
                    "No recommendation was produced."
                ],
                "chat_response": (
                    "The Controller assessment failed before producing a recommendation. "
                    "No recovery option is endorsed and no operational action was taken. "
                    "Please retry once; if the error persists, escalate the case to the "
                    "authorized Operations and Maintenance/airworthiness reviewers."
                ),
                "human_approval_required": True,
            }
        return {
            "status": result.status.value,
            "scenario_id": scenario_id,
            "data_source": "synthetic local fixtures",
            "brief": result.model_dump(mode="json"),
            "chat_response": render_decision_brief(result),
            "human_approval_required": True,
        }

    async def _assess_validated(
        self,
        intake: ControllerIntake,
        scenario_id: str,
    ) -> ControllerDecisionBrief:
        materials_data = _materials_input(scenario_id, intake.case)
        maintenance_data = _maintenance_input(materials_data, intake.case)
        work_order = maintenance_data.work_order
        maintenance_evidence = tuple(
            item.evidence_id for item in _maintenance_evidence(maintenance_data)
        )
        plans = build_recovery_candidates(
            CandidateBuildContext(
                schema_version="1.0",
                case=intake.case,
                request_id=intake.request_id,
                evaluated_at=intake.evaluated_at,
                failed_part_number=intake.failed_part_number,
                preferred_replacement_part=_preferred_part(materials_data),
                estimated_repair_duration_hours=(
                    work_order.estimated_repair_duration_hours if work_order is not None else None
                ),
                maintenance_evidence_references=maintenance_evidence,
                materials_assessment=materials_data.assessment,
            )
        )
        operations_request, adapters, package_load = _operations_inputs(
            intake.case,
            intake.request_id,
            intake.evaluated_at,
            intake.affected_flight_numbers,
            plans,
            scenario_id,
        )
        context = InMemoryCaseContextStore().start_case(intake)
        recorder = InMemoryCaseContextRecorder()
        workflow = ControllerWorkflow(
            self._maintenance,
            self._materials,
            context,
            recorder,
        )
        executions = tuple(
            await asyncio.gather(
                *(
                    workflow.assess_candidate(
                        intake,
                        maintenance_data,
                        materials_data,
                        operations_request,
                        adapters,
                        plan.option.option_id,
                    )
                    for plan in plans
                )
            )
        )

        eligible_plans: list[RecoveryCandidatePlan] = []
        excluded_options: list[ExcludedOption] = []
        score_inputs: list[CandidateScoringInput] = []
        execution_by_id = {item.candidate_option_id: item for item in executions}
        for plan in plans:
            execution = execution_by_id[plan.option.option_id]
            maintenance_payload = _maintenance_payload(execution)
            approval = (
                maintenance_payload.approval_evidence
                if maintenance_payload is not None
                else EngineeringApprovalEvidence(
                    status=ApprovalEvidenceStatus.UNKNOWN,
                    approver_role=None,
                    source_reference=None,
                    recorded_at=None,
                )
            )
            gated = apply_compliance_gate((plan,), approval)
            excluded_options.extend(gated.excluded_options)
            eligible_plans.extend(gated.eligible_candidates)
            if gated.eligible_candidates:
                score_inputs.append(
                    _score_input(
                        plan,
                        execution,
                        maintenance_payload,
                        package_load,
                        intake.evaluated_at,
                        intake.affected_flight_numbers,
                    )
                )

        scoring = score_candidates(
            ComplianceGateResult(
                eligible_candidates=tuple(eligible_plans),
                excluded_options=tuple(excluded_options),
            ),
            tuple(score_inputs),
        )
        return build_decision_brief(
            executions,
            scoring,
            recommendation_version=f"{intake.case.case_id}-{intake.request_id}",
            case=intake.case,
        )


def _read_json(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((_FIXTURE_ROOT / name).read_text(encoding="utf-8")),
    )


def _materials_input(scenario_id: str, case: AogCase) -> MaterialsLogisticsAssessmentInput:
    document = _read_json("materials_logistics_agent.json")
    scenario = next(item for item in document["scenarios"] if item["scenario_id"] == scenario_id)
    payload = dict(scenario["input"])
    payload["case"] = case.model_dump(mode="json")
    return MaterialsLogisticsAssessmentInput.model_validate_json(json.dumps(payload))


def _maintenance_input(
    materials: MaterialsLogisticsAssessmentInput,
    case: AogCase,
) -> MaintenanceAssessmentInput:
    payload = _read_json("maintenance_agent.json")["input"]
    payload = dict(payload)
    payload["case"] = case.model_dump(mode="json")
    # Synthetic fixtures are rebound to the user's aircraft and station; their content stays mock.
    metadata = payload.get("aircraft_metadata")
    if isinstance(metadata, dict):
        payload["aircraft_metadata"] = {
            **metadata,
            "claim_reference": f"aircraft-status-{case.aircraft_id}",
            "content": {
                **metadata["content"],
                "aircraft_id": case.aircraft_id,
                "station": case.location,
            },
        }
    work_order = payload.get("work_order")
    if isinstance(work_order, dict):
        payload["work_order"] = {**work_order, "aircraft_id": case.aircraft_id}
    payload["need_by_time"] = (
        case.need_by.isoformat() if case.need_by is not None else payload["need_by_time"]
    )
    preferred_part = _preferred_part(materials)
    source = next(
        (
            item
            for item in materials.assessment.sourcing_options
            if item.part_number == preferred_part
        ),
        None,
    )
    payload["parts_ready_at"] = source.eta_at.isoformat() if source and source.eta_at else None
    payload["parts_readiness_evidence_reference"] = (
        source.evidence_references[0] if source and source.evidence_references else None
    )
    return MaintenanceAssessmentInput.model_validate_json(json.dumps(payload))


def _preferred_part(payload: MaterialsLogisticsAssessmentInput) -> str | None:
    record = next(
        (
            item
            for item in payload.assessment.part_availability
            if item.role is PartRole.PREFERRED_REPLACEMENT
        ),
        None,
    )
    return record.part_number if record is not None else None


def _maintenance_evidence(payload: MaintenanceAssessmentInput) -> tuple[Evidence, ...]:
    evidence = [
        *payload.maintenance_history,
        *payload.engineering_constraints,
        *payload.safety_conditions,
    ]
    if payload.aircraft_metadata is not None:
        evidence.append(payload.aircraft_metadata)
    if payload.work_order is not None:
        evidence.append(payload.work_order.evidence)
    return tuple(evidence)


def _operations_inputs(
    case: AogCase,
    request_id: str,
    evaluated_at: datetime,
    affected_flights: tuple[str, ...],
    plans: tuple[RecoveryCandidatePlan, ...],
    scenario_id: str,
) -> tuple[OperationsRequest, Mapping[ToolName, ReadOnlyAdapter], PackageLoadData]:
    document = _read_json("operations_agent.json")
    scenario = next(item for item in document["scenarios"] if item["scenario_id"] == scenario_id)
    raw_request = dict(scenario["request"])
    raw_request.update(
        {
            "request_id": f"{request_id}-operations",
            "case": case.model_dump(mode="json"),
            "affected_flight_numbers": list(affected_flights),
            "candidates": [plan.option.model_dump(mode="json") for plan in plans],
            "evaluated_at": evaluated_at.isoformat(),
        }
    )
    operations_request = OperationsRequest.model_validate_json(json.dumps(raw_request))
    source = document["source_data"]
    schedule = FlightScheduleData.model_validate_json(json.dumps(source["flight_schedule"]))
    fleet = FleetAvailabilityData.model_validate_json(json.dumps(source["fleet_availability"]))
    packages = PackageLoadData.model_validate_json(json.dumps(source["package_load"]))
    alternates = AlternateFlightData.model_validate_json(json.dumps(source["alternate_flights"]))
    network = NetworkStatusData.model_validate_json(json.dumps(source["operations_status"]))
    adapters = make_adapters(
        schedule,
        fleet,
        packages,
        network,
        alternates=alternates,
        retrieved_at=evaluated_at,
    )
    return operations_request, adapters, packages


def _maintenance_payload(
    execution: ControllerCandidateExecution,
) -> MaintenanceAssessmentPayload | None:
    if execution.maintenance_result is None:
        return None
    try:
        return MaintenanceAssessmentPayload.model_validate_json(
            json.dumps(execution.maintenance_result.role_payload)
        )
    except Exception:
        return None


def _hours_until(target: datetime | None, evaluated_at: datetime) -> float | None:
    if target is None:
        return None
    return (target - evaluated_at).total_seconds() / 3600.0


def _swap_risk(option: RecoveryOptionAssessment) -> str:
    aircraft = option.substitute_aircraft_id or "the substitute aircraft"
    ready = (
        f" being ready by {option.earliest_feasible_departure:%H:%MZ}"
        if option.earliest_feasible_departure is not None
        else " being available"
    )
    impact = f"; {option.impact_level.value} operational impact" if option.impact_level else ""
    return f"Depends on {aircraft}{ready}{impact}."


def _score_input(
    plan: RecoveryCandidatePlan,
    execution: ControllerCandidateExecution,
    maintenance: MaintenanceAssessmentPayload | None,
    package_load: PackageLoadData,
    evaluated_at: datetime,
    affected_flights: tuple[str, ...],
) -> CandidateScoringInput:
    operations_assessment = (
        execution.operations_outcome.assessment
        if execution.operations_outcome is not None
        else None
    )
    operation_option = (
        next(
            (
                item
                for item in operations_assessment.recovery_options
                if item.option_id == plan.option.option_id
            ),
            None,
        )
        if operations_assessment is not None
        else None
    )
    package = operation_option.package if operation_option is not None else None
    costs = operation_option.cost if operation_option is not None else None
    priority_count = sum(
        group.count
        for group in package_load.groups
        if group.flight_number in affected_flights
        and group.service_level is PackageServiceLevel.PRIORITY
    )
    total_count = (
        package.affected_package_count if package is not None and package.assessed else None
    )
    package_counts_available = (
        total_count is not None
        and priority_count is not None
        and package is not None
        and package.unprotected_count is not None
        and package.unprotected_time_critical_count is not None
    )
    repair_labor = (
        maintenance.estimated_repair_labor_cost_usd
        if maintenance is not None and plan.option.kind is not OptionKind.SWAP
        else (Decimal("0") if plan.option.kind is OptionKind.SWAP else None)
    )
    sourcing_cost = (
        plan.sourcing_option.estimated_cost_usd
        if plan.sourcing_option is not None
        else (Decimal("0") if plan.part_number is None else None)
    )
    operations_cost = Decimal(costs.total_usd) if costs is not None and costs.complete else None
    risk_metrics = maintenance.risk_metrics if maintenance is not None else None
    return CandidateScoringInput(
        option_id=plan.option.option_id,
        return_to_service_hours=_hours_until(
            plan.option.readiness_eta
            or (
                operation_option.earliest_feasible_departure
                if operation_option is not None and plan.option.kind is OptionKind.SWAP
                else None
            ),
            evaluated_at,
        ),
        impact_level=operation_option.impact_level if operation_option is not None else None,
        total_package_count=total_count if package_counts_available else None,
        priority_package_count=priority_count if package_counts_available else None,
        unprotected_package_count=(
            package.unprotected_count if package_counts_available and package is not None else None
        ),
        unprotected_priority_package_count=(
            package.unprotected_time_critical_count
            if package_counts_available and package is not None
            else None
        ),
        affected_flight_numbers=affected_flights,
        maintenance_risk_levels=(
            (
                risk_metrics.delay_risk,
                risk_metrics.parts_dependency_risk,
                risk_metrics.repair_complexity_risk,
            )
            if risk_metrics is not None
            else (MaintenanceRiskLevel.UNKNOWN,)
        ),
        risk_factors=(
            (_swap_risk(operation_option),)
            if plan.option.kind is OptionKind.SWAP and operation_option is not None
            else maintenance.technical_risks
            if maintenance is not None
            else ("Maintenance evidence unavailable",)
        ),
        repair_labor_cost_usd=repair_labor,
        part_and_sourcing_cost_usd=sourcing_cost,
        operations_cost_usd=operations_cost,
    )
