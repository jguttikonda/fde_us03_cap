"""Versioned Maintenance H3 and Materials & Logistics H4 contracts (ARD-SYS-004)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import EvidenceWarning
from aog_recovery.materials_logistics.models import RequestedPartComparison, SourcingOption

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExchangeStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    CONFLICTED = "conflicted"
    FAILED = "failed"


class DegradationStatus(StrEnum):
    NONE = "none"
    MISSING = "missing"
    STALE = "stale"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"


class H3ReplacementStrategyRequest(ContractModel):
    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    exchange_id: NonEmptyString
    request_id: NonEmptyString
    trace_context: TraceContext
    source: Literal[AgentRole.MAINTENANCE]
    sent_at: datetime
    status: ExchangeStatus
    failed_part_number: NonEmptyString
    preferred_part_number: NonEmptyString | None
    aircraft_id: NonEmptyString
    station: NonEmptyString | None
    need_by_time: datetime | None
    recurring_failure_count: Annotated[int, Field(ge=0)] | None
    recurring_failure_window_days: Annotated[int, Field(ge=1)] | None
    maintenance_evidence_references: tuple[NonEmptyString, ...]
    degradation_status: DegradationStatus
    missing_data: tuple[NonEmptyString, ...]
    warnings: tuple[EvidenceWarning, ...]
    conflicts: tuple[NonEmptyString, ...] = ()

    @field_validator("sent_at", "need_by_time")
    @classmethod
    def require_timezone_aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_complete_recurrence_window(self) -> H3ReplacementStrategyRequest:
        if (self.recurring_failure_count is None) != (self.recurring_failure_window_days is None):
            raise ValueError("recurrence count and window must be supplied together")
        return self

    @model_validator(mode="after")
    def require_conflict_details(self) -> H3ReplacementStrategyRequest:
        if self.status is ExchangeStatus.CONFLICTED and not self.conflicts:
            raise ValueError("conflicted H3 request requires conflict details")
        return self


class H4AvailabilityResponse(ContractModel):
    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    exchange_id: NonEmptyString
    response_id: NonEmptyString
    trace_context: TraceContext
    source: Literal[AgentRole.MATERIALS_LOGISTICS]
    responded_at: datetime
    status: ExchangeStatus
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    failed_part_number: NonEmptyString
    preferred_part_number: NonEmptyString | None
    aircraft_id: NonEmptyString
    station: NonEmptyString | None
    need_by_time: datetime | None
    part_comparison: RequestedPartComparison
    sourcing_options: tuple[SourcingOption, ...]
    evidence_references: tuple[NonEmptyString, ...]
    degradation_status: DegradationStatus
    missing_data: tuple[NonEmptyString, ...]
    warnings: tuple[EvidenceWarning, ...]
    errors: tuple[StructuredError, ...]
    conflicts: tuple[NonEmptyString, ...]

    @field_validator("responded_at", "need_by_time")
    @classmethod
    def require_timezone_aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_status_and_comparison_consistency(self) -> H4AvailabilityResponse:
        if self.part_comparison.failed_part_number != self.failed_part_number:
            raise ValueError("H4 comparison failed-part number must match the response")
        if self.part_comparison.preferred_part_number != self.preferred_part_number:
            raise ValueError("H4 comparison preferred-part number must match the response")
        if self.status is ExchangeStatus.FAILED and not self.errors:
            raise ValueError("failed H4 response requires a structured error")
        if self.status is ExchangeStatus.CONFLICTED and not self.conflicts:
            raise ValueError("conflicted H4 response requires conflict details")
        return self


class H3H4Exchange(ContractModel):
    request: H3ReplacementStrategyRequest
    response: H4AvailabilityResponse

    @model_validator(mode="after")
    def require_correlated_messages(self) -> H3H4Exchange:
        request = self.request
        response = self.response
        if request.case_id != response.case_id:
            raise ValueError("H3/H4 case_id values must match")
        if request.exchange_id != response.exchange_id:
            raise ValueError("H3/H4 exchange_id values must match")
        if request.trace_context != response.trace_context:
            raise ValueError("H3/H4 trace_context values must match")
        if request.failed_part_number != response.failed_part_number:
            raise ValueError("H3/H4 failed_part_number values must match")
        if request.preferred_part_number != response.preferred_part_number:
            raise ValueError("H3/H4 preferred_part_number values must match")
        if request.aircraft_id != response.aircraft_id:
            raise ValueError("H3/H4 aircraft_id values must match")
        if request.station != response.station:
            raise ValueError("H3/H4 station values must match")
        if request.need_by_time != response.need_by_time:
            raise ValueError("H3/H4 need_by_time values must match")
        return self
