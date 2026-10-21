from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import EvidenceWarning

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ToolResultStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ToolName(StrEnum):
    MAINTENANCE_RECORDS = "maintenance_records"
    PART_INVENTORY = "part_inventory"
    OPERATIONS_STATUS = "operations_status"


class ToolRequest(ContractModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case_id: NonEmptyString
    trace_context: TraceContext
    tool_name: ToolName
    requested_at: datetime
    parameters: dict[str, object]
    access_mode: Literal["read"]

    @field_validator("requested_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class ToolResult(ContractModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case_id: NonEmptyString
    trace_context: TraceContext
    source: NonEmptyString
    completed_at: datetime
    status: ToolResultStatus
    warnings: tuple[EvidenceWarning, ...]
    data: dict[str, object] | None
    error: StructuredError | None

    @field_validator("completed_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_status_consistent_result(self) -> ToolResult:
        if self.status is ToolResultStatus.SUCCESS and (
            self.data is None or self.error is not None
        ):
            raise ValueError("success requires data and must not include an error")
        if self.status is ToolResultStatus.PARTIAL and (
            self.data is None or not self.warnings or self.error is not None
        ):
            raise ValueError("partial requires data and warnings, without an error")
        if self.status is ToolResultStatus.FAILED and (self.error is None or self.data is not None):
            raise ValueError("failed requires an error and must not include data")
        return self
