from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from aog_recovery.contracts.base import ContractModel

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TraceContext(ContractModel):
    trace_id: NonEmptyString
    correlation_id: NonEmptyString


class AogCase(ContractModel):
    case_id: NonEmptyString
    aircraft_id: NonEmptyString
    event_type: NonEmptyString
    defect_summary: NonEmptyString
    location: NonEmptyString
    event_at: datetime
    created_at: datetime
    schema_version: Literal["1.0"]
    trace_context: TraceContext
    # Latest time the aircraft or part is needed; supplied by intake, used by sourcing agents.
    need_by: datetime | None = None

    @field_validator("need_by")
    @classmethod
    def require_timezone_aware_need_by(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("event_at", "created_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value
