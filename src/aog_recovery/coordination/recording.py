"""Append-only H3/H4 recording boundary (ARD-SYS-002/004, ARD-SEC-009)."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import Field, field_validator, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.coordination.models import (
    ExchangeStatus,
    H3H4Exchange,
    H3ReplacementStrategyRequest,
    H4AvailabilityResponse,
)
from aog_recovery.observability.context import correlation_scope
from aog_recovery.observability.structured import emit_event


class ExchangeDirection(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"


class ExchangeRecordingStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class ExchangeRecord(ContractModel):
    case_id: str = Field(min_length=1)
    exchange_id: str = Field(min_length=1)
    trace_context: TraceContext
    direction: ExchangeDirection
    occurred_at: datetime
    status: ExchangeStatus
    evidence_references: tuple[str, ...]
    message: H3ReplacementStrategyRequest | H4AvailabilityResponse

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_record_matches_message(self) -> ExchangeRecord:
        if self.message.case_id != self.case_id:
            raise ValueError("record case_id must match message")
        if self.message.exchange_id != self.exchange_id:
            raise ValueError("record exchange_id must match message")
        if self.message.trace_context != self.trace_context:
            raise ValueError("record trace_context must match message")
        if self.direction is ExchangeDirection.REQUEST:
            if not isinstance(self.message, H3ReplacementStrategyRequest):
                raise ValueError("request record must contain an H3 request")
        elif not isinstance(self.message, H4AvailabilityResponse):
            raise ValueError("response record must contain an H4 response")
        return self


class ExchangeRecordingResult(ContractModel):
    case_id: str = Field(min_length=1)
    exchange_id: str = Field(min_length=1)
    status: ExchangeRecordingStatus
    records: tuple[ExchangeRecord, ...]
    error: StructuredError | None

    @model_validator(mode="after")
    def require_recording_status_consistency(self) -> ExchangeRecordingResult:
        if self.status is ExchangeRecordingStatus.COMPLETE and (
            len(self.records) != 2 or self.error is not None
        ):
            raise ValueError("complete recording requires request and response records")
        if self.status is ExchangeRecordingStatus.INCOMPLETE and (
            len(self.records) >= 2 or self.error is None
        ):
            raise ValueError("incomplete recording requires a failure and fewer than two records")
        return self


class CaseContextRecorder(Protocol):
    def append(self, record: ExchangeRecord) -> None: ...


class RecorderError(Exception):
    pass


class InMemoryCaseContextRecorder:
    def __init__(
        self,
        fail_on_directions: frozenset[ExchangeDirection] = frozenset(),
    ) -> None:
        self._records: dict[tuple[str, str], list[ExchangeRecord]] = {}
        self._fail_on_directions = fail_on_directions

    def append(self, record: ExchangeRecord) -> None:
        if record.direction in self._fail_on_directions:
            raise RecorderError(f"synthetic {record.direction.value} append failure")
        key = (record.case_id, record.exchange_id)
        existing_records = self._records.setdefault(key, [])
        matching_direction = next(
            (existing for existing in existing_records if existing.direction is record.direction),
            None,
        )
        if matching_direction is not None:
            if matching_direction == record:
                return
            raise RecorderError("exchange direction already has a different record")
        if record.direction is ExchangeDirection.RESPONSE and not any(
            item.direction is ExchangeDirection.REQUEST for item in existing_records
        ):
            raise RecorderError("H4 response cannot be recorded before its H3 request")
        existing_records.append(record)

    def records_for(self, case_id: str, exchange_id: str) -> tuple[ExchangeRecord, ...]:
        return tuple(self._records.get((case_id, exchange_id), ()))

    @property
    def records(self) -> tuple[ExchangeRecord, ...]:
        return tuple(record for records in self._records.values() for record in records)


def record_h3_h4_exchange(
    exchange: H3H4Exchange,
    recorder: CaseContextRecorder,
) -> ExchangeRecordingResult:
    records: list[ExchangeRecord] = []
    for direction, message in (
        (ExchangeDirection.REQUEST, exchange.request),
        (ExchangeDirection.RESPONSE, exchange.response),
    ):
        record = _record_for_message(direction, message)
        try:
            recorder.append(record)
        except RecorderError as exc:
            _emit_recording_event(record, ExchangeRecordingStatus.INCOMPLETE.value)
            return ExchangeRecordingResult(
                case_id=exchange.request.case_id,
                exchange_id=exchange.request.exchange_id,
                status=ExchangeRecordingStatus.INCOMPLETE,
                records=tuple(records),
                error=StructuredError(
                    schema_version="1.0",
                    category="case_context_recording_failed",
                    component="case-context-recorder",
                    message=str(exc),
                    retryable=False,
                    case_impact="H3/H4 exchange was not fully recorded",
                ),
            )
        _emit_recording_event(record, "recorded")
        records.append(record)
    return ExchangeRecordingResult(
        case_id=exchange.request.case_id,
        exchange_id=exchange.request.exchange_id,
        status=ExchangeRecordingStatus.COMPLETE,
        records=tuple(records),
        error=None,
    )


def _record_for_message(
    direction: ExchangeDirection,
    message: H3ReplacementStrategyRequest | H4AvailabilityResponse,
) -> ExchangeRecord:
    if isinstance(message, H3ReplacementStrategyRequest):
        occurred_at = message.sent_at
        evidence_references = message.maintenance_evidence_references
    else:
        occurred_at = message.responded_at
        evidence_references = message.evidence_references
    return ExchangeRecord(
        case_id=message.case_id,
        exchange_id=message.exchange_id,
        trace_context=message.trace_context,
        direction=direction,
        occurred_at=occurred_at,
        status=message.status,
        evidence_references=evidence_references,
        message=message,
    )


def _emit_recording_event(record: ExchangeRecord, status: str) -> None:
    with correlation_scope(record.case_id, record.trace_context, record.exchange_id):
        emit_event(
            AuditEvent(
                schema_version="1.0",
                occurred_at=record.occurred_at,
                event_type="peer_exchange_recorded",
                case_id=record.case_id,
                request_id=record.exchange_id,
                trace_context=record.trace_context,
                component=f"coordination-recorder:{record.direction.value}",
                status=status,
                evidence_references=record.evidence_references,
                rationale="H3/H4 peer message recording outcome",
                details={
                    "exchange_id": record.exchange_id,
                    "direction": record.direction.value,
                },
            )
        )
