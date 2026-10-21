from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.evidence import EvidenceConflict, Unknown

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConfidenceDisposition(StrEnum):
    PREFERRED = "preferred"
    PROVISIONAL = "provisional"
    ESCALATION_REQUIRED = "escalation_required"


class ConfidenceAssessment(ContractModel):
    confidence: float = Field(ge=0.0, le=1.0)
    disposition: ConfidenceDisposition
    conflict_references: tuple[NonEmptyString, ...]
    unknown_claim_references: tuple[NonEmptyString, ...]
    human_approval_required: Literal[True]


def assess_confidence(
    confidence: float,
    conflicts: tuple[EvidenceConflict, ...],
    unknowns: tuple[Unknown, ...],
) -> ConfidenceAssessment:
    if conflicts or confidence < 0.50:
        disposition = ConfidenceDisposition.ESCALATION_REQUIRED
    elif confidence < 0.70:
        disposition = ConfidenceDisposition.PROVISIONAL
    else:
        disposition = ConfidenceDisposition.PREFERRED

    return ConfidenceAssessment(
        confidence=confidence,
        disposition=disposition,
        conflict_references=tuple(conflict.conflict_id for conflict in conflicts),
        unknown_claim_references=tuple(unknown.claim_reference for unknown in unknowns),
        human_approval_required=True,
    )
