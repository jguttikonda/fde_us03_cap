"""Deterministic compliance eligibility and pending human handoff (ARD-CTL-017, ARD-GOV-008)."""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from aog_recovery.contracts.agent import AgentResultStatus, StructuredError
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.controller.aggregation import aggregate_candidate_result
from aog_recovery.controller.context import ControllerAuditRecorder
from aog_recovery.controller.models import (
    CandidateHandoff,
    PerCandidateResult,
    RoutingDecision,
    UnrankedHandoff,
    WorkflowStatus,
)
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    MaintenanceAssessmentPayload,
    RepairabilityStatus,
)
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    CompatibilityStatus,
    TraceabilityStatus,
)
from aog_recovery.operations.models import OptionKind
from aog_recovery.validation.boundaries import validate_contract_json
from aog_recovery.validation.confidence import (
    ConfidenceAssessment,
    ConfidenceDisposition,
    assess_confidence,
)
from aog_recovery.validation.human_gate import assess_human_gate

_REPAIR_KINDS = frozenset({OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE})
_AUTHORIZED_MAINTENANCE_ROLES = frozenset(
    {
        "maintenance_airworthiness_authority",
        "aircraft_maintenance_technician",
        "aircraft_maintenance_engineer",
    }
)


def build_unranked_handoff(
    case: AogCase,
    candidate_results: tuple[PerCandidateResult, ...],
    *,
    routing: RoutingDecision | None = None,
    audit_recorder: ControllerAuditRecorder | None = None,
    occurred_at: datetime | None = None,
) -> UnrankedHandoff:
    """Aggregate candidates, exclude compliance failures, and require human approval."""
    event_time = occurred_at or datetime.now(UTC)
    aggregated = tuple(aggregate_candidate_result(item) for item in candidate_results)
    audit_errors: list[StructuredError] = []
    if audit_recorder is not None:
        for result in aggregated:
            error = audit_recorder.record(
                event_id=f"{case.case_id}:{result.candidate.option_id}:aggregated",
                event_type="controller_aggregation",
                case_id=case.case_id,
                request_id=f"{result.candidate.option_id}:aggregate",
                trace_context=case.trace_context,
                occurred_at=event_time,
                status=result.status.value,
                rationale="Validated candidate findings were aggregated",
                evidence_references=tuple(item.evidence_id for item in result.evidence),
                details={
                    "candidate_id": result.candidate.option_id,
                    "missing_data_count": len(result.missing_data),
                    "error_count": len(result.errors),
                },
            )
            if error is not None:
                audit_errors.append(error)
            if result.conflicts or result.operations_conflicts:
                error = audit_recorder.record(
                    event_id=f"{case.case_id}:{result.candidate.option_id}:conflict",
                    event_type="controller_conflict",
                    case_id=case.case_id,
                    request_id=f"{result.candidate.option_id}:aggregate",
                    trace_context=case.trace_context,
                    occurred_at=event_time,
                    status="escalation_required",
                    rationale="Conflicting candidate evidence was preserved for human review",
                    evidence_references=tuple(
                        reference
                        for conflict in result.conflicts
                        for reference in conflict.evidence_references
                    ),
                    details={
                        "candidate_id": result.candidate.option_id,
                        "evidence_conflict_count": len(result.conflicts),
                        "operations_conflict_count": len(result.operations_conflicts),
                    },
                )
                if error is not None:
                    audit_errors.append(error)
    handoffs = tuple(_gate_candidate(item) for item in aggregated)
    evidence_by_id = {
        evidence.evidence_id: evidence
        for result in aggregated
        for evidence in _all_evidence(result)
    }
    evidence = tuple(evidence_by_id[key] for key in sorted(evidence_by_id))
    conflicts = _unique(
        (conflict for result in aggregated for conflict in result.conflicts),
        lambda conflict: conflict.conflict_id,
    )
    operations_conflicts = _unique(
        (conflict for result in aggregated for conflict in result.operations_conflicts),
        lambda conflict: conflict.conflict_id,
    )
    warnings = _unique(
        (warning for result in aggregated for warning in result.warnings),
        lambda warning: warning.warning_id,
    )
    unknowns = _unique(
        (unknown for result in aggregated for unknown in result.unknowns),
        lambda unknown: unknown.claim_reference,
    )
    errors = (*tuple(error for result in aggregated for error in result.errors), *audit_errors)
    missing_data = tuple(
        dict.fromkeys(missing for result in aggregated for missing in result.missing_data)
    )

    confidence_value = min(
        (result.confidence.confidence for result in aggregated if result.confidence is not None),
        default=0.0,
    )
    confidence = assess_confidence(confidence_value, conflicts, unknowns)
    requires_repair_approval = any(result.candidate.kind in _REPAIR_KINDS for result in aggregated)
    human_gate = assess_human_gate(
        decisions=(),
        case_id=case.case_id,
        recommendation_version="unranked-handoff-v1",
        requires_repair_or_part_approval=requires_repair_approval,
    )
    status = _workflow_status(aggregated, confidence)

    handoff = UnrankedHandoff(
        schema_version="1.0",
        case=case,
        status=status,
        candidates=handoffs,
        confidence=confidence,
        human_gate=human_gate,
        evidence=evidence,
        warnings=warnings,
        conflicts=conflicts,
        unknowns=unknowns,
        missing_data=missing_data,
        errors=errors,
        operations_conflicts=operations_conflicts,
        routing=routing,
    )
    if audit_recorder is not None:
        error = audit_recorder.record(
            event_id=f"{case.case_id}:unranked-handoff",
            event_type="controller_handoff",
            case_id=case.case_id,
            request_id=f"{case.case_id}:handoff",
            trace_context=case.trace_context,
            occurred_at=event_time,
            status=handoff.status.value,
            rationale="Unranked advisory handoff requires a human decision",
            evidence_references=tuple(item.evidence_id for item in handoff.evidence),
            details={
                "candidate_count": len(handoff.candidates),
                "excluded_count": sum(not item.eligible for item in handoff.candidates),
                "human_gate_status": handoff.human_gate.status.value,
            },
        )
        if error is not None:
            return handoff.model_copy(
                update={
                    "status": (
                        handoff.status
                        if handoff.status is WorkflowStatus.ESCALATION_REQUIRED
                        else WorkflowStatus.PARTIAL
                    ),
                    "errors": (*handoff.errors, error),
                }
            )
    return handoff


def _gate_candidate(result: PerCandidateResult) -> CandidateHandoff:
    reasons: list[str] = []
    if result.candidate.kind in _REPAIR_KINDS:
        reasons.extend(_maintenance_exclusions(result))
        reasons.extend(_part_exclusions(result))
    reasons = list(dict.fromkeys(reasons))
    return CandidateHandoff(
        result=result,
        eligible=not reasons,
        exclusion_reasons=tuple(reasons),
    )


def _maintenance_exclusions(result: PerCandidateResult) -> list[str]:
    agent_result = result.maintenance_result
    if agent_result is None or agent_result.status is AgentResultStatus.FAILED:
        return ["Maintenance approval evidence is unavailable"]
    payload, report = validate_contract_json(
        MaintenanceAssessmentPayload,
        agent_result.role_payload,
    )
    if payload is None:
        return [f"Maintenance approval payload is invalid ({len(report.findings)} finding(s))"]

    approval = payload.approval_evidence
    reasons: list[str] = []
    if payload.repairability_status is not RepairabilityStatus.FEASIBLE:
        reasons.append(f"Repairability is {payload.repairability_status.value}, not feasible")
    if approval.status is not ApprovalEvidenceStatus.APPROVAL_RECORDED:
        reasons.append(f"Engineering approval is {approval.status.value}")
    if approval.approver_role not in _AUTHORIZED_MAINTENANCE_ROLES:
        reasons.append("Engineering approver role is not an authorized maintenance role")
    if approval.source_reference is None or not _has_current_evidence(
        result, (approval.source_reference,)
    ):
        reasons.append("Engineering approval lacks current source evidence")
    return reasons


def _part_exclusions(result: PerCandidateResult) -> list[str]:
    agent_result = result.materials_logistics_result
    if agent_result is None or agent_result.status is AgentResultStatus.FAILED:
        return ["Part authorization and traceability results are unavailable"]
    payload, report = validate_contract_json(
        MaterialsLogisticsAgentPayload,
        agent_result.role_payload,
    )
    if payload is None:
        return [
            "Part authorization and traceability payload is invalid "
            f"({len(report.findings)} finding(s))"
        ]

    required_parts = tuple(
        sorted({option.part_number for option in result.candidate_source.sourcing_options})
    )
    if not required_parts:
        return ["Candidate has no validated replacement-part sourcing path"]

    reasons: list[str] = []
    for part_number in required_parts:
        records = tuple(
            item for item in payload.assessment.part_eligibility if item.part_number == part_number
        )
        if len(records) != 1:
            reasons.append(
                f"Part {part_number} has "
                f"{'no' if not records else 'conflicting'} eligibility record"
            )
            continue
        record = records[0]
        if record.compatibility is not CompatibilityStatus.COMPATIBLE:
            reasons.append(f"Part {part_number} compatibility is {record.compatibility.value}")
        if record.authorization is not AuthorizationStatus.AUTHORIZED:
            reasons.append(f"Part {part_number} authorization is {record.authorization.value}")
        if record.traceability is not TraceabilityStatus.VERIFIED:
            reasons.append(f"Part {part_number} traceability is {record.traceability.value}")
        if not record.evidence_references or not _has_current_evidence(
            result, record.evidence_references
        ):
            reasons.append(f"Part {part_number} eligibility lacks current source evidence")
    return reasons


def _has_current_evidence(result: PerCandidateResult, references: tuple[str, ...]) -> bool:
    evidence_by_id = {item.evidence_id: item for item in _all_evidence(result)}
    return bool(references) and all(
        reference in evidence_by_id
        and evidence_by_id[reference].validity_state is EvidenceValidity.CURRENT
        for reference in references
    )


def _all_evidence(result: PerCandidateResult) -> tuple[Evidence, ...]:
    operations_evidence = result.operations_result.evidence if result.operations_result else ()
    return (*result.evidence, *operations_evidence)


def _workflow_status(
    results: tuple[PerCandidateResult, ...],
    confidence: ConfidenceAssessment,
) -> WorkflowStatus:
    if confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
        return WorkflowStatus.ESCALATION_REQUIRED
    if confidence.disposition is ConfidenceDisposition.PROVISIONAL:
        return WorkflowStatus.PROVISIONAL
    if any(result.status is WorkflowStatus.PARTIAL for result in results):
        return WorkflowStatus.PARTIAL
    return WorkflowStatus.PENDING_HUMAN_APPROVAL


def _unique[T](items: Iterable[T], key: Callable[[T], str]) -> tuple[T, ...]:
    unique: dict[str, T] = {}
    for item in items:
        unique.setdefault(key(item), item)
    return tuple(unique.values())
