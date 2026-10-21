"""Visible aggregation of Materials source degradation (ARD-MLG-007, ARD-RES-003..006)."""

from aog_recovery.config import AogSettings
from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.materials_logistics.models import MaterialsEvidenceSummary
from aog_recovery.materials_logistics.tools import MaterialsToolResult

_STALE_WARNING_CODES = frozenset({"STALE_EVIDENCE", "CACHED_EVIDENCE"})


def summarize_materials_evidence(
    results: tuple[MaterialsToolResult, ...],
    confidence: float,
    settings: AogSettings,
) -> MaterialsEvidenceSummary:
    if not results:
        raise ValueError("at least one Materials source result is required")

    warnings = tuple(warning for result in results for warning in result.warnings)
    errors = tuple(result.error for result in results if result.error is not None)
    evidence = tuple(item for result in results for item in result.evidence or ())
    stale = any(item.validity_state is EvidenceValidity.STALE for item in evidence) or any(
        warning.code in _STALE_WARNING_CODES for warning in warnings
    )
    degraded = (
        stale
        or bool(warnings)
        or any(result.status is not ToolResultStatus.SUCCESS for result in results)
        or any(item.validity_state is not EvidenceValidity.CURRENT for item in evidence)
    )

    if all(result.status is ToolResultStatus.FAILED for result in results):
        status = ToolResultStatus.FAILED
    elif degraded:
        status = ToolResultStatus.PARTIAL
    else:
        status = ToolResultStatus.SUCCESS

    adjusted_confidence = (
        0.0
        if status is ToolResultStatus.FAILED
        else max(
            0.0,
            confidence - settings.materials_stale_confidence_penalty if stale else confidence,
        )
    )
    return MaterialsEvidenceSummary(
        status=status,
        confidence=adjusted_confidence,
        evidence_references=tuple(sorted({item.evidence_id for item in evidence})),
        warnings=warnings,
        errors=errors,
    )
