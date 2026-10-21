from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator

from aog_recovery.contracts.base import ContractModel

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvidenceValidity(StrEnum):
    CURRENT = "current"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTING = "conflicting"


class Evidence(ContractModel):
    evidence_id: NonEmptyString
    source: NonEmptyString
    retrieved_at: datetime
    validity_state: EvidenceValidity
    claim_reference: NonEmptyString
    content: dict[str, object]

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class Assumption(ContractModel):
    assumption_id: NonEmptyString
    claim_reference: NonEmptyString
    statement: NonEmptyString
    evidence_references: tuple[NonEmptyString, ...]


class Unknown(ContractModel):
    claim_reference: NonEmptyString
    description: NonEmptyString
    required_evidence: tuple[NonEmptyString, ...]


class EvidenceWarning(ContractModel):
    warning_id: NonEmptyString
    claim_reference: NonEmptyString
    code: NonEmptyString
    message: NonEmptyString
    source_reference: NonEmptyString | None


class EvidenceConflict(ContractModel):
    conflict_id: NonEmptyString
    claim_reference: NonEmptyString
    evidence_references: tuple[NonEmptyString, ...] = Field(min_length=2)
    description: NonEmptyString
