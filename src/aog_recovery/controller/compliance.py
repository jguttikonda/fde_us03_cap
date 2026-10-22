"""Deterministic compliance gate; excluded candidates are never scored (ARD-CTL-017)."""

from aog_recovery.controller.models import (
    ComplianceGateResult,
    ExcludedOption,
    RecoveryCandidatePlan,
    RecoveryOptionKind,
)
from aog_recovery.maintenance.models import ApprovalEvidenceStatus, EngineeringApprovalEvidence
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    CompatibilityStatus,
    TraceabilityStatus,
)
from aog_recovery.operations.models import OptionKind


def apply_compliance_gate(
    candidates: tuple[RecoveryCandidatePlan, ...],
    approval_evidence: EngineeringApprovalEvidence,
) -> ComplianceGateResult:
    eligible: list[RecoveryCandidatePlan] = []
    excluded: list[ExcludedOption] = []
    repair_kinds = {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}

    for candidate in candidates:
        if candidate.option.kind not in repair_kinds:
            eligible.append(candidate)
            continue

        reasons: list[str] = []
        evidence_references = {record.claim_reference for record in candidate.inventory_records}
        if candidate.eligibility is not None:
            evidence_references.update(candidate.eligibility.evidence_references)
        if approval_evidence.source_reference is not None:
            evidence_references.add(approval_evidence.source_reference)

        if approval_evidence.status is not ApprovalEvidenceStatus.APPROVAL_RECORDED:
            reasons.append("engineering or airworthiness approval is not recorded")
        if candidate.part_number is None:
            reasons.append("repair candidate has no identified part")
        if candidate.eligibility is None:
            reasons.append(
                "part compatibility, authorization, and traceability evidence is missing"
            )
        else:
            if candidate.eligibility.compatibility is not CompatibilityStatus.COMPATIBLE:
                reasons.append("part compatibility is not confirmed")
            if candidate.eligibility.authorization is not AuthorizationStatus.AUTHORIZED:
                reasons.append("part authorization is not confirmed")
            if candidate.eligibility.traceability is not TraceabilityStatus.VERIFIED:
                reasons.append("part traceability is not verified")

        if reasons:
            excluded.append(
                ExcludedOption(
                    option_id=candidate.option.option_id,
                    kind=_recovery_option_kind(candidate.option.kind),
                    reasons=tuple(reasons),
                    evidence_references=tuple(sorted(evidence_references)),
                )
            )
        else:
            eligible.append(candidate)

    return ComplianceGateResult(
        eligible_candidates=tuple(eligible),
        excluded_options=tuple(excluded),
    )


def _recovery_option_kind(kind: OptionKind) -> RecoveryOptionKind:
    return RecoveryOptionKind(kind.value)
