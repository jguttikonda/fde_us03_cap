from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AuditEvent(ContractModel):
    schema_version: Literal["1.0"]
    occurred_at: datetime
    event_type: NonEmptyString
    case_id: NonEmptyString
    request_id: NonEmptyString | None
    trace_context: TraceContext
    component: NonEmptyString
    status: NonEmptyString
    evidence_references: tuple[NonEmptyString, ...]
    rationale: Annotated[str, StringConstraints(max_length=500)] | None
    details: dict[str, object]

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value
