"""Evidence-grounded per-candidate aggregation (ARD-CTL-006..008, ARD-GOV-002..005)."""

import json
from collections import defaultdict
from collections.abc import Callable
from hashlib import sha256

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, StructuredError
from aog_recovery.contracts.evidence import (
    Evidence,
    EvidenceConflict,
    EvidenceValidity,
    EvidenceWarning,
    Unknown,
)
from aog_recovery.controller.models import PerCandidateResult, WorkflowStatus
from aog_recovery.maintenance.models import MaintenanceAssessmentPayload
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.operations.models import OperationsOutcome
from aog_recovery.validation.boundaries import validate_agent_result, validate_contract_json
from aog_recovery.validation.confidence import (
    ConfidenceDisposition,
    assess_confidence,
)

_MISSING_RESULT_CAP = 0.49
_DEGRADED_EVIDENCE_CAP = 0.69


def aggregate_candidate_result(
    candidate_result: PerCandidateResult,
) -> PerCandidateResult:
    """Validate specialist envelopes/payloads and return a deterministic aggregate."""
    errors = list(candidate_result.errors)
    missing_data = list(candidate_result.missing_data)
    warnings = list(candidate_result.warnings)
    conflicts = list(candidate_result.conflicts)
    unknowns = list(candidate_result.unknowns)
    operations_conflicts = list(candidate_result.operations_conflicts)

    available_evidence = {item.evidence_id: item for item in candidate_result.evidence}
    outcome = candidate_result.operations_result
    if outcome is not None:
        available_evidence.update({item.evidence_id: item for item in outcome.evidence})
        warnings.extend(outcome.warnings)
        conflicts.extend(outcome.conflicts)
        unknowns.extend(outcome.unknowns)
        if outcome.assessment is not None:
            operations_conflicts.extend(outcome.assessment.conflicts)
            for option in outcome.assessment.recovery_options:
                missing_data.extend(option.missing_inputs)

    source_conflicts, source_warnings = _evidence_degradation(tuple(available_evidence.values()))
    conflicts.extend(source_conflicts)
    warnings.extend(source_warnings)

    required_results = (
        ("maintenance", candidate_result.maintenance_result),
        ("materials_logistics", candidate_result.materials_logistics_result),
        ("operations", outcome.result if outcome is not None else None),
    )
    confidence_values: list[float] = []
    missing_required_result = False
    for label, result in required_results:
        if result is None:
            missing_data.append(f"{label}_result")
            missing_required_result = True
            continue
        if result.status is AgentResultStatus.FAILED:
            missing_required_result = True
            _append_failed_result_error(errors, result)
        confidence_values.append(result.confidence)
        _validate_agent_result(result, set(available_evidence), errors, unknowns, label)

    if candidate_result.maintenance_result is not None:
        _validate_role_payload(
            candidate_result.maintenance_result,
            MaintenanceAssessmentPayload,
            errors,
            "maintenance",
        )
    if candidate_result.materials_logistics_result is not None:
        _validate_role_payload(
            candidate_result.materials_logistics_result,
            MaterialsLogisticsAgentPayload,
            errors,
            "materials_logistics",
        )
    if outcome is not None:
        validated_outcome, report = validate_contract_json(OperationsOutcome, outcome.model_dump())
        if validated_outcome is None:
            errors.append(_validation_error("operations", len(report.findings)))
        confidence_values.append(outcome.confidence.confidence)

    if not confidence_values:
        confidence = 0.0
    else:
        confidence = min(confidence_values)
    if missing_required_result or errors:
        confidence = min(confidence, _MISSING_RESULT_CAP)
    elif (
        missing_data
        or errors
        or unknowns
        or conflicts
        or any(
            evidence.validity_state is not EvidenceValidity.CURRENT
            for evidence in available_evidence.values()
        )
    ):
        confidence = min(confidence, _DEGRADED_EVIDENCE_CAP)
    if operations_conflicts or any(
        evidence.validity_state is EvidenceValidity.CONFLICTING
        for evidence in available_evidence.values()
    ):
        confidence = min(confidence, _MISSING_RESULT_CAP)

    conflicts = _unique_by(conflicts, lambda item: item.conflict_id)
    warnings = _unique_by(warnings, lambda item: item.warning_id)
    unknowns = _unique_by(unknowns, lambda item: item.claim_reference)
    missing_data = list(dict.fromkeys(missing_data))
    for item in missing_data:
        claim_reference = f"{candidate_result.candidate.option_id}:{item}"
        if not any(unknown.claim_reference == claim_reference for unknown in unknowns):
            unknowns.append(
                Unknown(
                    claim_reference=claim_reference,
                    description=f"Required candidate input is missing: {item}",
                    required_evidence=(item,),
                )
            )

    assessment = assess_confidence(confidence, tuple(conflicts), tuple(unknowns))
    status = candidate_result.status
    if assessment.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
        status = WorkflowStatus.ESCALATION_REQUIRED
    elif assessment.disposition is ConfidenceDisposition.PROVISIONAL:
        status = WorkflowStatus.PROVISIONAL
    elif missing_data or errors:
        status = WorkflowStatus.PARTIAL

    return candidate_result.model_copy(
        update={
            "confidence": assessment,
            "status": status,
            "warnings": tuple(warnings),
            "conflicts": tuple(conflicts),
            "unknowns": tuple(unknowns),
            "missing_data": tuple(missing_data),
            "errors": tuple(errors),
            "operations_conflicts": tuple(
                _unique_by(operations_conflicts, lambda item: item.conflict_id)
            ),
        }
    )


def _validate_agent_result(
    result: AgentResult,
    evidence_ids: set[str],
    errors: list[StructuredError],
    unknowns: list[Unknown],
    label: str,
) -> None:
    validated, report = validate_contract_json(AgentResult, result.model_dump())
    if validated is None:
        errors.append(_validation_error(label, len(report.findings)))
        return
    report = validate_agent_result(result.model_dump(), evidence_ids)
    if not report.is_valid:
        errors.append(_validation_error(label, len(report.findings)))
        for finding in report.findings:
            unknowns.append(
                Unknown(
                    claim_reference=f"{label}:{finding.field_path}",
                    description="Specialist referenced evidence unavailable to the Controller",
                    required_evidence=(finding.field_path,),
                )
            )


def _validate_role_payload(
    result: AgentResult,
    model: type[MaintenanceAssessmentPayload] | type[MaterialsLogisticsAgentPayload],
    errors: list[StructuredError],
    label: str,
) -> None:
    if result.status is AgentResultStatus.FAILED:
        return
    _, report = validate_contract_json(model, result.role_payload)
    if not report.is_valid:
        errors.append(_validation_error(label, len(report.findings)))


def _append_failed_result_error(errors: list[StructuredError], result: AgentResult) -> None:
    try:
        error = StructuredError.model_validate(result.role_payload.get("error"))
    except Exception:
        error = _validation_error(result.agent_role.value, 1)
    errors.append(error)


def _validation_error(component: str, finding_count: int) -> StructuredError:
    return StructuredError(
        schema_version="1.0",
        category="specialist_result_validation_failed",
        component=f"controller:{component}",
        message=f"Specialist result validation failed with {finding_count} finding(s)",
        retryable=False,
        case_impact="Candidate evidence is incomplete and requires review",
    )


def _evidence_degradation(
    evidence: tuple[Evidence, ...],
) -> tuple[list[EvidenceConflict], list[EvidenceWarning]]:
    by_claim: dict[str, list[Evidence]] = defaultdict(list)
    warnings: list[EvidenceWarning] = []
    for item in evidence:
        by_claim[item.claim_reference].append(item)
        if item.validity_state is not EvidenceValidity.CURRENT:
            warnings.append(
                EvidenceWarning(
                    warning_id=f"controller-{item.evidence_id}-{item.validity_state.value}",
                    claim_reference=item.claim_reference,
                    code=f"{item.validity_state.value.upper()}_EVIDENCE",
                    message=f"Evidence from {item.source} is {item.validity_state.value}",
                    source_reference=item.source,
                )
            )

    conflicts: list[EvidenceConflict] = []
    for claim_reference, records in sorted(by_claim.items()):
        if len(records) < 2:
            continue
        values = {
            json.dumps(record.content, sort_keys=True, separators=(",", ":")) for record in records
        }
        if len(values) < 2:
            continue
        references = tuple(sorted({record.evidence_id for record in records}))
        if len(references) < 2:
            continue
        conflict_id = (
            "conflict-"
            + sha256((claim_reference + "|" + "|".join(references)).encode("utf-8")).hexdigest()[
                :12
            ]
        )
        conflicts.append(
            EvidenceConflict(
                conflict_id=conflict_id,
                claim_reference=claim_reference,
                evidence_references=references,
                description="Source records disagree on the claim value",
            )
        )
    return conflicts, warnings


def _unique_by[T](items: list[T], key: Callable[[T], str]) -> list[T]:
    unique: dict[str, T] = {}
    for item in items:
        unique.setdefault(key(item), item)
    return list(unique.values())
