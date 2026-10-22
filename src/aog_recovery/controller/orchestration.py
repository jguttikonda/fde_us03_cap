"""Bounded fakeable specialist fan-out and H3/H4 persistence (ARD-CTL-006/008/018)."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import ValidationError

from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import EvidenceWarning
from aog_recovery.controller.candidates import CandidateDefinition
from aog_recovery.controller.context import ControllerAuditRecorder
from aog_recovery.controller.models import (
    ControllerIntake,
    NonEmptyString,
    PerCandidateResult,
    RoutingDecision,
    SourceHealthRecord,
    SourceHealthStatus,
    WorkflowStatus,
)
from aog_recovery.coordination.recording import CaseContextRecorder, ExchangeRecordingResult
from aog_recovery.coordination.workflow import build_h3_request, coordinate_h3_h4
from aog_recovery.maintenance.models import MaintenanceAssessmentPayload
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.operations.models import OperationsOutcome, OperationsRequest, OptionKind
from aog_recovery.validation.boundaries import validate_contract_json


class CandidateSpecialistRequest(ContractModel):
    """Candidate-scoped validated inputs passed to a specialist boundary."""

    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case: AogCase
    candidate: CandidateDefinition
    available_evidence_ids: tuple[NonEmptyString, ...]


class SpecialistAssessmentPort(Protocol):
    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult: ...


class OperationsAssessmentPort(Protocol):
    async def assess(self, request: OperationsRequest) -> OperationsOutcome: ...


async def assess_candidate_specialists(
    intake: ControllerIntake,
    candidates: tuple[CandidateDefinition, ...],
    maintenance: SpecialistAssessmentPort,
    materials_logistics: SpecialistAssessmentPort,
    recorder: CaseContextRecorder,
    *,
    routing: RoutingDecision,
    settings: AogSettings | None = None,
    clock: Callable[[], datetime] | None = None,
    audit_recorder: ControllerAuditRecorder | None = None,
) -> tuple[PerCandidateResult, ...]:
    """Assess candidates with bounded concurrent specialists and retain partial failures."""
    chosen_settings = settings or AogSettings()
    now = clock or (lambda: datetime.now(UTC))
    results: list[PerCandidateResult] = []
    for candidate in candidates:
        maintenance_request = CandidateSpecialistRequest(
            schema_version="1.0",
            request_id=f"{candidate.candidate.option_id}:maintenance",
            case=intake.case,
            candidate=candidate,
            available_evidence_ids=tuple(item.evidence_id for item in intake.evidence),
        )
        materials_request = CandidateSpecialistRequest(
            schema_version="1.0",
            request_id=f"{candidate.candidate.option_id}:materials-logistics",
            case=intake.case,
            candidate=candidate,
            available_evidence_ids=tuple(item.evidence_id for item in intake.evidence),
        )
        audit_errors: list[StructuredError] = []
        routing_warnings: list[EvidenceWarning] = []
        missing_data: list[str] = list(candidate.missing_data)
        relevant_health = _candidate_source_health(routing, candidate)
        for record in relevant_health:
            if record.status is SourceHealthStatus.AVAILABLE:
                continue
            missing_data.append(f"source_health:{record.source_id}:{record.status.value}")
            routing_warnings.append(
                EvidenceWarning(
                    warning_id=f"{candidate.candidate.option_id}:{record.source_id}:{record.status.value}",
                    claim_reference=f"source-health:{record.source_id}",
                    code=f"SOURCE_{record.status.value.upper()}",
                    message=record.reason or f"Source health is {record.status.value}",
                    source_reference=record.source_id,
                )
            )
        route_issues = {
            AgentRole.MAINTENANCE: _role_route_issue(routing, AgentRole.MAINTENANCE),
            AgentRole.MATERIALS_LOGISTICS: _role_route_issue(
                routing,
                AgentRole.MATERIALS_LOGISTICS,
            ),
        }
        if audit_recorder is not None:
            for request, role in (
                (maintenance_request, AgentRole.MAINTENANCE),
                (materials_request, AgentRole.MATERIALS_LOGISTICS),
            ):
                route_issue = route_issues[role]
                error = audit_recorder.record(
                    event_id=f"{request.request_id}:{'skipped' if route_issue else 'started'}",
                    event_type="specialist_invocation",
                    case_id=intake.case.case_id,
                    request_id=request.request_id,
                    trace_context=intake.case.trace_context,
                    occurred_at=now(),
                    status="skipped" if route_issue else "started",
                    rationale=(
                        route_issue[1]
                        if route_issue
                        else f"{role.value} candidate assessment invocation started"
                    ),
                    evidence_references=candidate.candidate.eta_evidence_references,
                    details={
                        "agent_role": role.value,
                        "candidate_id": candidate.candidate.option_id,
                    },
                )
                if error is not None:
                    audit_errors.append(error)
        (
            (maintenance_result, maintenance_error),
            (materials_result, materials_error),
        ) = await asyncio.gather(
            _invoke_routed(
                maintenance,
                maintenance_request,
                AgentRole.MAINTENANCE,
                chosen_settings.agent_timeout_seconds,
                route_issues[AgentRole.MAINTENANCE],
            ),
            _invoke_routed(
                materials_logistics,
                materials_request,
                AgentRole.MATERIALS_LOGISTICS,
                chosen_settings.agent_timeout_seconds,
                route_issues[AgentRole.MATERIALS_LOGISTICS],
            ),
        )
        errors = [*audit_errors]
        errors.extend(error for error in (maintenance_error, materials_error) if error is not None)
        for result in (maintenance_result, materials_result):
            if audit_recorder is not None:
                timed_out = any(
                    error.category == "specialist_timeout"
                    and error.component == f"controller:{result.agent_role.value}"
                    for error in errors
                )
                event_type = (
                    "specialist_timeout"
                    if timed_out
                    else "specialist_failure"
                    if result.status is AgentResultStatus.FAILED
                    else "specialist_result"
                )
                error = audit_recorder.record(
                    event_id=f"{candidate.candidate.option_id}:{result.agent_role.value}:result",
                    event_type=event_type,
                    case_id=intake.case.case_id,
                    request_id=f"{candidate.candidate.option_id}:{result.agent_role.value}",
                    trace_context=intake.case.trace_context,
                    occurred_at=now(),
                    status=result.status.value,
                    rationale=f"{result.agent_role.value} result received by Controller",
                    evidence_references=result.evidence_references,
                    details={"candidate_id": candidate.candidate.option_id},
                )
                if error is not None:
                    errors.append(error)
            if result.status is AgentResultStatus.FAILED:
                embedded_error = _embedded_error(result)
                errors.append(
                    embedded_error
                    or _candidate_error(
                        "specialist_reported_failure",
                        f"{result.agent_role.value} returned a failed result",
                    )
                )

        recording: ExchangeRecordingResult | None = None
        if candidate.candidate.kind in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}:
            recording, recording_error = _record_peer_exchange(
                intake.case,
                candidate,
                maintenance_result,
                materials_result,
                recorder,
                now(),
            )
            if recording_error is not None:
                errors.append(recording_error)
                missing_data.append("h3_h4_exchange")

        incomplete = bool(errors or missing_data) or any(
            result.status is not AgentResultStatus.COMPLETE
            for result in (maintenance_result, materials_result)
        )
        results.append(
            PerCandidateResult(
                candidate=candidate.candidate,
                candidate_source=candidate.source,
                maintenance_result=maintenance_result,
                materials_logistics_result=materials_result,
                operations_result=None,
                peer_exchange_recording=recording,
                confidence=None,
                status=WorkflowStatus.PARTIAL if incomplete else WorkflowStatus.IN_PROGRESS,
                evidence=candidate.source_evidence,
                warnings=tuple(routing_warnings),
                conflicts=(),
                unknowns=(),
                missing_data=tuple(dict.fromkeys(missing_data)),
                errors=tuple(errors),
            )
        )
    return tuple(results)


async def assess_operations_candidates(
    intake: ControllerIntake,
    candidate_results: tuple[PerCandidateResult, ...],
    operations: OperationsAssessmentPort,
    *,
    clock: Callable[[], datetime] | None = None,
    audit_recorder: ControllerAuditRecorder | None = None,
) -> tuple[PerCandidateResult, ...]:
    """Invoke Operations once per candidate and retain its typed, candidate-local outcome."""
    now = clock or (lambda: datetime.now(UTC))
    results: list[PerCandidateResult] = []
    for candidate_result in candidate_results:
        candidate = candidate_result.candidate
        missing_data = list(candidate_result.missing_data)
        errors = list(candidate_result.errors)
        if candidate.readiness_eta is None:
            missing_data.append("readiness_eta")
        if not intake.affected_flight_numbers:
            missing_data.append("affected_flight_numbers")
            errors.append(
                _operations_error(
                    "operations_input_missing",
                    "Operations assessment requires affected flight numbers",
                )
            )
            if audit_recorder is not None:
                audit_error = audit_recorder.record(
                    event_id=f"{candidate.option_id}:operations:skipped",
                    event_type="operations_invocation",
                    case_id=intake.case.case_id,
                    request_id=f"{candidate.option_id}:operations",
                    trace_context=intake.case.trace_context,
                    occurred_at=now(),
                    status="skipped",
                    rationale="Operations assessment requires affected flight numbers",
                    evidence_references=candidate.eta_evidence_references,
                    details={"candidate_id": candidate.option_id},
                )
                if audit_error is not None:
                    errors.append(audit_error)
            results.append(
                _updated_candidate(
                    candidate_result,
                    operations_outcome=None,
                    missing_data=missing_data,
                    errors=errors,
                    status=WorkflowStatus.PARTIAL,
                )
            )
            continue

        request = OperationsRequest(
            schema_version="1.0",
            request_id=f"{candidate.option_id}:operations",
            case=intake.case,
            affected_flight_numbers=intake.affected_flight_numbers,
            candidates=(candidate,),
            evaluated_at=now(),
            reroute_policy=intake.reroute_policy,
            reserved_capacity=intake.reserved_capacity,
        )
        if audit_recorder is not None:
            audit_error = audit_recorder.record(
                event_id=f"{request.request_id}:started",
                event_type="operations_invocation",
                case_id=intake.case.case_id,
                request_id=request.request_id,
                trace_context=intake.case.trace_context,
                occurred_at=request.evaluated_at,
                status="started",
                rationale="Operations candidate assessment invocation started",
                evidence_references=candidate.eta_evidence_references,
                details={"candidate_id": candidate.option_id},
            )
            if audit_error is not None:
                errors.append(audit_error)
        try:
            outcome = await operations.assess(request)
            if not isinstance(outcome, OperationsOutcome):
                raise TypeError("Operations boundary returned a non-OperationsOutcome value")
            if outcome.result.agent_role is not AgentRole.OPERATIONS:
                raise ValueError("Operations boundary returned a result for the wrong role")
            if outcome.assessment is not None and any(
                item.option_id != candidate.option_id
                for item in outcome.assessment.recovery_options
            ):
                raise ValueError("Operations outcome contains another candidate's assessment")
        except Exception as error:
            timed_out = isinstance(error, TimeoutError)
            timeout_seconds = getattr(error, "timeout_seconds", None)
            timeout_detail = f" after {timeout_seconds} seconds" if timeout_seconds else ""
            invocation_error = _operations_error(
                "operations_timeout" if timed_out else "operations_invocation_failed",
                f"Operations assessment timed out{timeout_detail} for candidate "
                f"{candidate.option_id} request {request.request_id}"
                if timed_out
                else (
                    f"Operations assessment failed for candidate {candidate.option_id} "
                    f"request {request.request_id} ({type(error).__name__})"
                ),
            )
            errors.append(invocation_error)
            if timed_out:
                missing_data.append("operations_analysis")
            if audit_recorder is not None:
                audit_error = audit_recorder.record(
                    event_id=f"{request.request_id}:failed",
                    event_type="operations_timeout" if timed_out else "operations_failure",
                    case_id=intake.case.case_id,
                    request_id=request.request_id,
                    trace_context=intake.case.trace_context,
                    occurred_at=request.evaluated_at,
                    status="failed",
                    rationale="Operations candidate assessment failed",
                    evidence_references=candidate.eta_evidence_references,
                    details={
                        "candidate_id": candidate.option_id,
                        "timeout_seconds": timeout_seconds,
                    },
                )
                if audit_error is not None:
                    errors.append(audit_error)
            results.append(
                _updated_candidate(
                    candidate_result,
                    operations_outcome=None,
                    missing_data=missing_data,
                    errors=errors,
                    status=WorkflowStatus.PARTIAL,
                )
            )
            continue

        if audit_recorder is not None:
            event_type = (
                "operations_failure"
                if outcome.result.status is AgentResultStatus.FAILED or outcome.errors
                else "operations_result"
            )
            audit_error = audit_recorder.record(
                event_id=f"{request.request_id}:result",
                event_type=event_type,
                case_id=intake.case.case_id,
                request_id=request.request_id,
                trace_context=intake.case.trace_context,
                occurred_at=request.evaluated_at,
                status=outcome.result.status.value,
                rationale="Operations candidate assessment returned",
                evidence_references=outcome.result.evidence_references,
                details={"candidate_id": candidate.option_id},
            )
            if audit_error is not None:
                errors.append(audit_error)

        incomplete = bool(missing_data or errors or outcome.errors) or (
            outcome.result.status is not AgentResultStatus.COMPLETE
        )
        results.append(
            _updated_candidate(
                candidate_result,
                operations_outcome=outcome,
                missing_data=missing_data,
                errors=errors,
                status=WorkflowStatus.PARTIAL if incomplete else WorkflowStatus.IN_PROGRESS,
            )
        )
    return tuple(results)


async def _invoke(
    port: SpecialistAssessmentPort,
    request: CandidateSpecialistRequest,
    expected_role: AgentRole,
    timeout_seconds: int,
) -> tuple[AgentResult, StructuredError | None]:
    try:
        result = await asyncio.wait_for(port.assess(request), timeout=timeout_seconds)
        if not isinstance(result, AgentResult):
            raise TypeError("specialist boundary returned a non-AgentResult value")
        if result.agent_role is not expected_role:
            raise ValueError("specialist boundary returned a result for the wrong role")
        return result, None
    except TimeoutError:
        return _failed_result(
            expected_role,
            "specialist_timeout",
            "Specialist assessment timed out",
            True,
        )
    except Exception as error:
        return _failed_result(
            expected_role,
            "specialist_invocation_failed",
            f"Specialist assessment failed ({type(error).__name__})",
            False,
        )


async def _invoke_routed(
    port: SpecialistAssessmentPort,
    request: CandidateSpecialistRequest,
    role: AgentRole,
    timeout_seconds: int,
    route_issue: tuple[str, str] | None,
) -> tuple[AgentResult, StructuredError | None]:
    if route_issue is not None:
        category, message = route_issue
        return _failed_result(role, category, message, False)
    return await _invoke(port, request, role, timeout_seconds)


def _role_route_issue(
    routing: RoutingDecision,
    role: AgentRole,
) -> tuple[str, str] | None:
    if role not in routing.selected_roles:
        omission = next((item for item in routing.omitted_roles if item.agent_role is role), None)
        reason = omission.reason if omission is not None else "role was not selected"
        return "specialist_omitted", f"{role.value} was omitted from routing: {reason}"
    unavailable = next(
        (
            item
            for item in routing.source_health
            if item.agent_role is role and item.status is SourceHealthStatus.UNAVAILABLE
        ),
        None,
    )
    if unavailable is not None:
        return (
            "specialist_source_unavailable",
            f"{role.value} source is unavailable: {unavailable.reason or unavailable.source_id}",
        )
    return None


def _candidate_source_health(
    routing: RoutingDecision,
    candidate: CandidateDefinition,
) -> tuple[SourceHealthRecord, ...]:
    evidence_sources = {item.source for item in candidate.source_evidence}
    return tuple(
        record
        for record in routing.source_health
        if record.agent_role is not None or record.source_id in evidence_sources
    )


def _failed_result(
    role: AgentRole,
    category: str,
    message: str,
    retryable: bool,
) -> tuple[AgentResult, StructuredError]:
    error = StructuredError(
        schema_version="1.0",
        category=category,
        component=f"controller:{role.value}",
        message=message,
        retryable=retryable,
        case_impact=f"{role.value} candidate analysis is unavailable",
    )
    return (
        AgentResult(
            schema_version="1.0",
            agent_role=role,
            status=AgentResultStatus.FAILED,
            summary=f"{role.value} assessment failed",
            confidence=0.0,
            assumptions=(),
            evidence_references=(),
            role_payload={"error": error.model_dump(mode="json")},
        ),
        error,
    )


def _record_peer_exchange(
    case: AogCase,
    candidate: CandidateDefinition,
    maintenance_result: AgentResult,
    materials_result: AgentResult,
    recorder: CaseContextRecorder,
    occurred_at: datetime,
) -> tuple[ExchangeRecordingResult | None, StructuredError | None]:
    if candidate.failed_part_number is None:
        return None, _candidate_error(
            "peer_exchange_input_missing",
            "H3/H4 exchange requires a source-backed failed part number",
        )
    if (
        maintenance_result.status is AgentResultStatus.FAILED
        or materials_result.status is AgentResultStatus.FAILED
    ):
        return None, _candidate_error(
            "peer_exchange_inputs_unavailable",
            "H3/H4 exchange was not recorded because a specialist result failed",
        )

    maintenance_payload, maintenance_report = validate_contract_json(
        MaintenanceAssessmentPayload, maintenance_result.role_payload
    )
    materials_payload, materials_report = validate_contract_json(
        MaterialsLogisticsAgentPayload, materials_result.role_payload
    )
    if maintenance_payload is None or materials_payload is None:
        finding_count = len(maintenance_report.findings) + len(materials_report.findings)
        return None, _candidate_error(
            "peer_exchange_payload_invalid",
            f"H3/H4 payload validation failed with {finding_count} finding(s)",
        )

    option_id = candidate.candidate.option_id
    coordinated = coordinate_h3_h4(
        request=build_h3_request(
            case=case,
            maintenance_payload=maintenance_payload,
            failed_part_number=candidate.failed_part_number,
            exchange_id=f"{option_id}:h3h4",
            request_id=f"{option_id}:h3",
            sent_at=occurred_at,
            source_evidence=candidate.source_evidence,
        ),
        materials_payload=materials_payload.assessment,
        evidence_summary=materials_payload.evidence_summary,
        response_id=f"{option_id}:h4",
        responded_at=occurred_at,
        recorder=recorder,
    )
    return coordinated.recording, coordinated.recording.error


def _embedded_error(result: AgentResult) -> StructuredError | None:
    payload = result.role_payload.get("error")
    if payload is None:
        return None
    try:
        return StructuredError.model_validate(payload)
    except ValidationError:
        return _candidate_error("specialist_failure_unstructured", "Specialist reported failure")


def _candidate_error(category: str, message: str) -> StructuredError:
    return StructuredError(
        schema_version="1.0",
        category=category,
        component="controller:peer-coordination",
        message=message,
        retryable=False,
        case_impact="Candidate peer analysis is incomplete",
    )


def _operations_error(category: str, message: str) -> StructuredError:
    return StructuredError(
        schema_version="1.0",
        category=category,
        component="controller:operations",
        message=message,
        retryable=False,
        case_impact="Candidate operations analysis is incomplete",
    )


def _updated_candidate(
    candidate_result: PerCandidateResult,
    *,
    operations_outcome: OperationsOutcome | None,
    missing_data: list[str],
    errors: list[StructuredError],
    status: WorkflowStatus,
) -> PerCandidateResult:
    payload = candidate_result.model_dump(mode="python")
    payload.update(
        operations_result=operations_outcome,
        missing_data=tuple(dict.fromkeys(missing_data)),
        errors=tuple(errors),
        status=status,
    )
    return PerCandidateResult.model_validate(payload)
