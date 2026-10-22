"""Direct Maintenance H3 to Materials & Logistics H4 coordination (ARD-SYS-003..004)."""

from datetime import datetime

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.coordination.models import (
    DegradationStatus,
    ExchangeStatus,
    H3H4Exchange,
    H3ReplacementStrategyRequest,
    H4AvailabilityResponse,
)
from aog_recovery.coordination.recording import (
    CaseContextRecorder,
    ExchangeRecordingResult,
    record_h3_h4_exchange,
)
from aog_recovery.maintenance.models import MaintenanceAssessmentPayload
from aog_recovery.materials_logistics.availability import evaluate_materials_availability
from aog_recovery.materials_logistics.models import (
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
)
from aog_recovery.materials_logistics.sourcing import compare_requested_parts


class CoordinatedPeerExchange(ContractModel):
    exchange: H3H4Exchange
    recording: ExchangeRecordingResult


def build_h3_request(
    case: AogCase,
    maintenance_payload: MaintenanceAssessmentPayload,
    failed_part_number: str,
    exchange_id: str,
    request_id: str,
    sent_at: datetime,
    source_evidence: tuple[Evidence, ...],
) -> H3ReplacementStrategyRequest:
    evidence_references = {item.evidence_id for item in source_evidence}
    if maintenance_payload.root_cause is not None:
        evidence_references.update(maintenance_payload.root_cause.evidence_references)
    if maintenance_payload.recurring_failure is not None:
        evidence_references.update(maintenance_payload.recurring_failure.evidence_references)
    evidence_references.update(maintenance_payload.preferred_replacement_evidence_references)
    if maintenance_payload.approval_evidence.source_reference is not None:
        evidence_references.add(maintenance_payload.approval_evidence.source_reference)

    missing_data = set(maintenance_payload.missing_data)
    conflicts: list[str] = []
    if not evidence_references:
        missing_data.add("maintenance_evidence_references")
    if maintenance_payload.need_by_time is None:
        missing_data.add("need_by_time")
    recurrence = maintenance_payload.recurring_failure
    if recurrence is not None and recurrence.part_number != failed_part_number:
        conflicts.append(
            f"recurrence part {recurrence.part_number} differs from failed part "
            f"{failed_part_number}"
        )

    evidence_warnings: list[EvidenceWarning] = []
    for evidence in source_evidence:
        if evidence.validity_state is EvidenceValidity.CONFLICTING:
            conflicts.append(f"conflicting maintenance evidence: {evidence.claim_reference}")
        if evidence.validity_state is not EvidenceValidity.CURRENT:
            warning_code = {
                EvidenceValidity.PARTIAL: "PARTIAL_DATA",
                EvidenceValidity.STALE: "STALE_EVIDENCE",
                EvidenceValidity.CONFLICTING: "CONFLICTING_DATA",
            }[evidence.validity_state]
            evidence_warnings.append(
                EvidenceWarning(
                    warning_id=f"{request_id}-{evidence.evidence_id}",
                    claim_reference=evidence.claim_reference,
                    code=warning_code,
                    message=f"maintenance evidence is {evidence.validity_state.value}",
                    source_reference=evidence.source,
                )
            )
    evidence_warnings.extend(
        EvidenceWarning(
            warning_id=f"{request_id}-maintenance-warning-{index}",
            claim_reference=f"maintenance-assessment:{case.case_id}",
            code="MAINTENANCE_WARNING",
            message=warning,
            source_reference=None,
        )
        for index, warning in enumerate(maintenance_payload.warnings, start=1)
    )

    if conflicts:
        status = ExchangeStatus.CONFLICTED
        degradation = DegradationStatus.CONFLICTING
    elif any(item.validity_state is EvidenceValidity.STALE for item in source_evidence):
        status = ExchangeStatus.PARTIAL
        degradation = DegradationStatus.STALE
    elif (
        missing_data
        or evidence_warnings
        or any(item.validity_state is EvidenceValidity.PARTIAL for item in source_evidence)
    ):
        status = ExchangeStatus.PARTIAL
        degradation = DegradationStatus.MISSING if missing_data else DegradationStatus.PARTIAL
    else:
        status = ExchangeStatus.COMPLETE
        degradation = DegradationStatus.NONE

    return H3ReplacementStrategyRequest(
        schema_version="1.0",
        case_id=case.case_id,
        exchange_id=exchange_id,
        request_id=request_id,
        trace_context=case.trace_context,
        source=AgentRole.MAINTENANCE,
        sent_at=sent_at,
        status=status,
        failed_part_number=failed_part_number,
        preferred_part_number=maintenance_payload.preferred_replacement_part,
        aircraft_id=case.aircraft_id,
        station=case.location,
        need_by_time=maintenance_payload.need_by_time,
        recurring_failure_count=recurrence.occurrences if recurrence is not None else None,
        recurring_failure_window_days=recurrence.window_days if recurrence is not None else None,
        maintenance_evidence_references=tuple(sorted(evidence_references)),
        degradation_status=degradation,
        missing_data=tuple(sorted(missing_data)),
        warnings=tuple(evidence_warnings),
        conflicts=tuple(dict.fromkeys(conflicts)),
    )


def build_h4_response(
    request: H3ReplacementStrategyRequest,
    materials_payload: MaterialsLogisticsAssessmentPayload,
    evidence_summary: MaterialsEvidenceSummary,
    response_id: str,
    responded_at: datetime,
) -> H4AvailabilityResponse:
    deterministic = evaluate_materials_availability(
        materials_payload,
        target_station=request.station,
        need_by_time=request.need_by_time,
    )
    comparison = compare_requested_parts(
        deterministic,
        failed_part_number=request.failed_part_number,
        preferred_part_number=request.preferred_part_number,
    )

    missing_data = set(request.missing_data)
    missing_data.update(materials_payload.missing_data)
    missing_data.update(comparison.missing_part_numbers)
    conflicts = list(request.conflicts)
    stale = any(warning.code == "STALE_EVIDENCE" for warning in evidence_summary.warnings)
    degraded_part_findings = False
    for part in deterministic.parts:
        for finding in part.findings:
            if "conflicting" in finding:
                conflicts.append(f"{part.part_number}: {finding}")
                degraded_part_findings = True
            elif "stale" in finding:
                stale = True
                degraded_part_findings = True
            elif finding.endswith("_unknown") or finding.endswith("_missing"):
                missing_data.add(f"{part.part_number}: {finding}")
                degraded_part_findings = True
            elif "partial" in finding:
                degraded_part_findings = True

    warnings = list(request.warnings)
    warnings.extend(evidence_summary.warnings)
    evidence_references = set(request.maintenance_evidence_references)
    evidence_references.update(evidence_summary.evidence_references)
    for part in (*comparison.failed_part_assessments, *comparison.preferred_part_assessments):
        evidence_references.update(part.evidence_references)
    relevant_part_numbers = {request.failed_part_number, request.preferred_part_number}
    sourcing_options = tuple(
        option
        for option in materials_payload.sourcing_options
        if option.part_number in relevant_part_numbers
    )
    for option in sourcing_options:
        evidence_references.update(option.evidence_references)

    if evidence_summary.status is ToolResultStatus.FAILED:
        status = ExchangeStatus.FAILED
        degradation = DegradationStatus.UNAVAILABLE
    elif conflicts:
        status = ExchangeStatus.CONFLICTED
        degradation = DegradationStatus.CONFLICTING
    elif stale:
        status = ExchangeStatus.PARTIAL
        degradation = DegradationStatus.STALE
    elif (
        evidence_summary.status is ToolResultStatus.PARTIAL
        or missing_data
        or warnings
        or degraded_part_findings
    ):
        status = ExchangeStatus.PARTIAL
        degradation = DegradationStatus.MISSING if missing_data else DegradationStatus.PARTIAL
    else:
        status = ExchangeStatus.COMPLETE
        degradation = DegradationStatus.NONE

    return H4AvailabilityResponse(
        schema_version="1.0",
        case_id=request.case_id,
        exchange_id=request.exchange_id,
        response_id=response_id,
        trace_context=request.trace_context,
        source=AgentRole.MATERIALS_LOGISTICS,
        responded_at=responded_at,
        status=status,
        confidence=min(evidence_summary.confidence, materials_payload.confidence),
        failed_part_number=request.failed_part_number,
        preferred_part_number=request.preferred_part_number,
        aircraft_id=request.aircraft_id,
        station=request.station,
        need_by_time=request.need_by_time,
        part_comparison=comparison,
        sourcing_options=sourcing_options,
        evidence_references=tuple(sorted(evidence_references)),
        degradation_status=degradation,
        missing_data=tuple(sorted(missing_data)),
        warnings=tuple(warnings),
        errors=evidence_summary.errors,
        conflicts=tuple(dict.fromkeys(conflicts)),
    )


def coordinate_h3_h4(
    request: H3ReplacementStrategyRequest,
    materials_payload: MaterialsLogisticsAssessmentPayload,
    evidence_summary: MaterialsEvidenceSummary,
    response_id: str,
    responded_at: datetime,
    recorder: CaseContextRecorder,
) -> CoordinatedPeerExchange:
    response = build_h4_response(
        request,
        materials_payload,
        evidence_summary,
        response_id,
        responded_at,
    )
    exchange = H3H4Exchange(request=request, response=response)
    recording = record_h3_h4_exchange(exchange, recorder)
    return CoordinatedPeerExchange(exchange=exchange, recording=recording)
