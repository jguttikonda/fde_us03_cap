"""Controller specialist orchestration for one candidate (ARD-CTL-006..009/018)."""

import asyncio
import json
from collections.abc import Mapping
from typing import Protocol

from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.contracts.agent import (
    AgentResult,
    AgentResultStatus,
    AgentRole,
    StructuredError,
)
from aog_recovery.contracts.evidence import Evidence, EvidenceWarning
from aog_recovery.contracts.tool import ToolName
from aog_recovery.controller.intake import ControllerCaseContext
from aog_recovery.controller.models import (
    ControllerCandidateExecution,
    ControllerIntake,
    ControllerWorkflowStatus,
)
from aog_recovery.coordination.models import H3H4Exchange
from aog_recovery.coordination.recording import (
    CaseContextRecorder,
    ExchangeRecordingResult,
)
from aog_recovery.coordination.workflow import build_h3_request, coordinate_h3_h4
from aog_recovery.maintenance.agent import _available_evidence_ids
from aog_recovery.maintenance.models import (
    MaintenanceAssessmentInput,
    MaintenanceAssessmentPayload,
)
from aog_recovery.materials_logistics.agent import (
    MaterialsLogisticsAgentPayload,
    MaterialsLogisticsAssessmentInput,
)
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import (
    CandidateOption,
    EtaBasis,
    OperationsOutcome,
    OperationsRequest,
    OptionKind,
)
from aog_recovery.validation.boundaries import validate_agent_result
from aog_recovery.validation.models import ValidationFinding


class SpecialistAssessor(Protocol):
    async def assess(self, payload: object) -> AgentResult: ...


class ControllerWorkflow:
    def __init__(
        self,
        maintenance_agent: SpecialistAssessor,
        materials_agent: SpecialistAssessor,
        case_context: ControllerCaseContext,
        recorder: CaseContextRecorder,
    ) -> None:
        self._maintenance_agent = maintenance_agent
        self._materials_agent = materials_agent
        self._case_context = case_context
        self._recorder = recorder

    async def assess_candidate(
        self,
        intake: ControllerIntake,
        maintenance_input: MaintenanceAssessmentInput,
        materials_input: MaterialsLogisticsAssessmentInput,
        operations_request: OperationsRequest,
        operations_adapters: Mapping[ToolName, ReadOnlyAdapter],
        candidate_option_id: str,
    ) -> ControllerCandidateExecution:
        case_id = intake.case.case_id
        if any(
            candidate_case_id != case_id
            for candidate_case_id in (
                maintenance_input.case.case_id,
                materials_input.case.case_id,
                operations_request.case.case_id,
                self._case_context.case_id,
            )
        ):
            return _failed_execution(
                case_id,
                candidate_option_id,
                "case_id_mismatch",
                "Controller inputs do not share the active case identifier",
            )
        if not any(item.option_id == candidate_option_id for item in operations_request.candidates):
            return _failed_execution(
                case_id,
                candidate_option_id,
                "candidate_not_found",
                "Operations request does not contain the candidate option",
            )

        maintenance_result, materials_result = await asyncio.gather(
            self._maintenance_agent.assess(maintenance_input.model_dump(mode="python")),
            self._materials_agent.assess(materials_input.model_dump(mode="python")),
        )
        maintenance_evidence = _maintenance_evidence_ids(maintenance_input)
        materials_evidence = _materials_evidence_ids(materials_input)
        findings = (
            *_validate_specialist_result(
                maintenance_result,
                AgentRole.MAINTENANCE,
                maintenance_evidence,
            ),
            *_validate_specialist_result(
                materials_result,
                AgentRole.MATERIALS_LOGISTICS,
                materials_evidence,
            ),
        )
        if findings:
            return _partial_execution(
                case_id,
                candidate_option_id,
                maintenance_result,
                materials_result,
                findings=tuple(findings),
                missing_data=("validated_specialist_results",),
            )

        if (
            maintenance_result.status is AgentResultStatus.FAILED
            or materials_result.status is AgentResultStatus.FAILED
        ):
            return _partial_execution(
                case_id,
                candidate_option_id,
                maintenance_result,
                materials_result,
                missing_data=("failed_specialist_analysis",),
                warnings=_failure_warnings(maintenance_result, materials_result),
                errors=_specialist_failure_errors(maintenance_result, materials_result),
            )

        try:
            maintenance_payload = MaintenanceAssessmentPayload.model_validate_json(
                json.dumps(maintenance_result.role_payload)
            )
            materials_payload = MaterialsLogisticsAgentPayload.model_validate_json(
                json.dumps(materials_result.role_payload)
            )
        except Exception as error:
            return _partial_execution(
                case_id,
                candidate_option_id,
                maintenance_result,
                materials_result,
                findings=(
                    ValidationFinding(
                        field_path="role_payload",
                        code="specialist_payload_invalid",
                        message=f"specialist payload failed validation: {type(error).__name__}",
                    ),
                ),
                missing_data=("validated_specialist_payload",),
            )

        maintenance_evidence_records = _maintenance_evidence_records(maintenance_input)
        peer_request = build_h3_request(
            case=intake.case,
            maintenance_payload=maintenance_payload,
            failed_part_number=intake.failed_part_number,
            exchange_id=f"{case_id}-{intake.request_id}-{candidate_option_id}-h3h4",
            request_id=f"{intake.request_id}-{candidate_option_id}-h3",
            sent_at=intake.evaluated_at,
            source_evidence=maintenance_evidence_records,
        )
        coordinated = coordinate_h3_h4(
            peer_request,
            materials_payload.assessment,
            materials_payload.evidence_summary,
            response_id=f"{intake.request_id}-h4",
            responded_at=intake.evaluated_at,
            recorder=self._recorder,
        )

        updated_request = _request_with_candidate_readiness(
            operations_request,
            candidate_option_id,
            maintenance_payload,
            maintenance_result,
        )
        operations_outcome = OperationsAgent(operations_adapters).assess(updated_request)
        all_evidence = maintenance_evidence | materials_evidence
        all_evidence.update(item.evidence_id for item in operations_outcome.evidence)
        operations_report = validate_agent_result(
            operations_outcome.result.model_dump(mode="python"), all_evidence
        )
        if not operations_report.is_valid:
            return _partial_execution(
                case_id,
                candidate_option_id,
                maintenance_result,
                materials_result,
                peer_exchange=coordinated.exchange,
                peer_recording=coordinated.recording,
                operations_outcome=operations_outcome,
                findings=operations_report.findings,
                missing_data=("validated_operations_result",),
            )

        missing_data = set(maintenance_payload.missing_data)
        missing_data.update(materials_payload.assessment.missing_data)
        if operations_outcome.assessment is not None:
            missing_data.update(operations_outcome.assessment.missing_data)
            missing_data.update(operations_outcome.assessment.missing_analysis)
        warnings = _specialist_warnings(
            maintenance_payload,
            materials_payload,
            operations_outcome,
        )
        specialist_conflicts = tuple(
            dict.fromkeys(
                warning.message for warning in warnings if "CONFLICT" in warning.code.upper()
            )
        )
        status = (
            ControllerWorkflowStatus.ESCALATED
            if (
                specialist_conflicts
                or coordinated.exchange.response.status.value == "conflicted"
                or any(
                    result.status is AgentResultStatus.ESCALATION_REQUIRED
                    for result in (maintenance_result, materials_result, operations_outcome.result)
                )
            )
            else ControllerWorkflowStatus.COMPLETE
            if (
                maintenance_result.status is AgentResultStatus.COMPLETE
                and materials_result.status is AgentResultStatus.COMPLETE
                and coordinated.recording.error is None
                and operations_outcome.result.status is AgentResultStatus.COMPLETE
                and not missing_data
            )
            else ControllerWorkflowStatus.PARTIAL
        )
        return ControllerCandidateExecution(
            schema_version="1.0",
            case_id=case_id,
            candidate_option_id=candidate_option_id,
            status=status,
            maintenance_result=maintenance_result,
            materials_result=materials_result,
            peer_exchange=coordinated.exchange,
            peer_recording=coordinated.recording,
            operations_outcome=operations_outcome,
            validation_findings=(),
            missing_data=tuple(sorted(missing_data)),
            warnings=warnings,
            specialist_conflicts=specialist_conflicts,
            conflicts=operations_outcome.conflicts,
            unknowns=operations_outcome.unknowns,
            errors=operations_outcome.errors,
        )


def _validate_specialist_result(
    result: AgentResult,
    expected_role: AgentRole,
    available_evidence: set[str],
) -> tuple[ValidationFinding, ...]:
    findings: list[ValidationFinding] = []
    if result.agent_role is not expected_role:
        findings.append(
            ValidationFinding(
                field_path="agent_role",
                code="specialist_role_mismatch",
                message=f"expected {expected_role.value}, received {result.agent_role.value}",
            )
        )
    report = validate_agent_result(result.model_dump(mode="python"), available_evidence)
    findings.extend(report.findings)
    return tuple(findings)


def _maintenance_evidence_records(payload: MaintenanceAssessmentInput) -> tuple[Evidence, ...]:
    evidence: list[Evidence] = list(payload.maintenance_history)
    evidence.extend(payload.engineering_constraints)
    evidence.extend(payload.safety_conditions)
    if payload.aircraft_metadata is not None:
        evidence.append(payload.aircraft_metadata)
    if payload.work_order is not None:
        evidence.append(payload.work_order.evidence)
    return tuple(evidence)


def _maintenance_evidence_ids(payload: MaintenanceAssessmentInput) -> set[str]:
    # Reuse Maintenance's definition so both agents accept the same references.
    return _available_evidence_ids(payload)


def _materials_evidence_ids(payload: MaterialsLogisticsAssessmentInput) -> set[str]:
    references = set(payload.evidence_summary.evidence_references)
    references.update(record.claim_reference for record in payload.assessment.part_availability)
    for eligibility in payload.assessment.part_eligibility:
        references.update(eligibility.evidence_references)
    for sourcing_option in payload.assessment.sourcing_options:
        references.update(sourcing_option.evidence_references)
    return references


def _request_with_candidate_readiness(
    request: OperationsRequest,
    candidate_option_id: str,
    maintenance: MaintenanceAssessmentPayload,
    maintenance_result: AgentResult,
) -> OperationsRequest:
    selected_candidate: CandidateOption | None = None
    for candidate in request.candidates:
        if candidate.option_id != candidate_option_id:
            continue
        if candidate.kind is OptionKind.SWAP:
            selected_candidate = candidate
        else:
            selected_candidate = CandidateOption.model_validate(
                {
                    **candidate.model_dump(mode="python"),
                    "readiness_eta": maintenance.return_to_service_time,
                    "eta_basis": (
                        EtaBasis.ESTIMATED
                        if maintenance.return_to_service_time is not None
                        else None
                    ),
                    "eta_evidence_references": (
                        maintenance_result.evidence_references
                        if maintenance.return_to_service_time is not None
                        else ()
                    ),
                }
            )
        break
    if selected_candidate is None:
        raise ValueError(f"candidate '{candidate_option_id}' is not in the Operations request")
    return request.model_copy(update={"candidates": (selected_candidate,)})


def _failed_execution(
    case_id: str,
    candidate_option_id: str,
    category: str,
    message: str,
) -> ControllerCandidateExecution:
    error = StructuredError(
        schema_version="1.0",
        category=category,
        component="controller-workflow",
        message=message,
        retryable=False,
        case_impact="Candidate assessment did not proceed.",
    )
    return ControllerCandidateExecution(
        schema_version="1.0",
        case_id=case_id,
        candidate_option_id=candidate_option_id,
        status=ControllerWorkflowStatus.FAILED,
        maintenance_result=None,
        materials_result=None,
        peer_exchange=None,
        peer_recording=None,
        operations_outcome=None,
        validation_findings=(),
        missing_data=(),
        warnings=(),
        specialist_conflicts=(),
        conflicts=(),
        unknowns=(),
        errors=(error,),
    )


def _partial_execution(
    case_id: str,
    candidate_option_id: str,
    maintenance_result: AgentResult | None,
    materials_result: AgentResult | None,
    *,
    peer_exchange: H3H4Exchange | None = None,
    peer_recording: ExchangeRecordingResult | None = None,
    operations_outcome: OperationsOutcome | None = None,
    findings: tuple[ValidationFinding, ...] = (),
    missing_data: tuple[str, ...] = (),
    warnings: tuple[EvidenceWarning, ...] = (),
    errors: tuple[StructuredError, ...] = (),
) -> ControllerCandidateExecution:
    return ControllerCandidateExecution(
        schema_version="1.0",
        case_id=case_id,
        candidate_option_id=candidate_option_id,
        status=ControllerWorkflowStatus.PARTIAL,
        maintenance_result=maintenance_result,
        materials_result=materials_result,
        peer_exchange=peer_exchange,
        peer_recording=peer_recording,
        operations_outcome=operations_outcome,
        validation_findings=findings,
        missing_data=missing_data,
        warnings=warnings,
        specialist_conflicts=tuple(
            warning.message for warning in warnings if "CONFLICT" in warning.code.upper()
        ),
        conflicts=operations_outcome.conflicts if operations_outcome is not None else (),
        unknowns=operations_outcome.unknowns if operations_outcome is not None else (),
        errors=(
            *errors,
            *(operations_outcome.errors if operations_outcome is not None else ()),
        ),
    )


def _specialist_warnings(
    maintenance: MaintenanceAssessmentPayload,
    materials: MaterialsLogisticsAgentPayload,
    operations: OperationsOutcome,
) -> tuple[EvidenceWarning, ...]:
    maintenance_warnings = tuple(
        EvidenceWarning(
            warning_id=f"maintenance-{index}",
            claim_reference="maintenance-assessment",
            code=(
                "CONFLICTING_DATA" if "conflict" in warning.casefold() else "MAINTENANCE_WARNING"
            ),
            message=warning,
            source_reference=None,
        )
        for index, warning in enumerate(maintenance.warnings, start=1)
    )
    unique_warnings: dict[str, EvidenceWarning] = {}
    for warning in (
        *maintenance_warnings,
        *materials.evidence_summary.warnings,
        *operations.warnings,
    ):
        unique_warnings.setdefault(warning.warning_id, warning)
    return tuple(unique_warnings.values())


def _failure_warnings(
    maintenance: AgentResult,
    materials: AgentResult,
) -> tuple[EvidenceWarning, ...]:
    return tuple(
        EvidenceWarning(
            warning_id=f"{result.agent_role.value}-failed",
            claim_reference=f"{result.agent_role.value}-assessment",
            code="SPECIALIST_FAILED",
            message=result.summary,
            source_reference=None,
        )
        for result in (maintenance, materials)
        if result.status is AgentResultStatus.FAILED
    )


def _specialist_failure_errors(
    maintenance: AgentResult,
    materials: AgentResult,
) -> tuple[StructuredError, ...]:
    return tuple(
        StructuredError(
            schema_version="1.0",
            category=f"{result.agent_role.value}_failed",
            component=f"{result.agent_role.value}-agent",
            message=result.summary,
            retryable=False,
            case_impact="Specialist analysis is unavailable; candidate is incomplete.",
        )
        for result in (maintenance, materials)
        if result.status is AgentResultStatus.FAILED
    )
