"""Append-only Controller case context and H3/H4 recorder adapter (ARD-CTL-005, ARD-SYS-002/004)."""

import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.coordination.recording import (
    CaseContextRecorder,
    ExchangeDirection,
    ExchangeRecord,
    RecorderError,
)
from aog_recovery.observability.context import correlation_scope
from aog_recovery.observability.structured import emit_event, serialize_event

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContextDirection(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"


class ControllerContextEvent(ContractModel):
    """Immutable persisted event carrying externally explainable workflow evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: str = "1.0"
    event_id: NonEmptyString
    event_type: NonEmptyString
    case_id: NonEmptyString
    trace_context: TraceContext
    occurred_at: datetime
    direction: ContextDirection
    status: NonEmptyString
    evidence_references: tuple[NonEmptyString, ...]
    exchange_id: NonEmptyString | None = None
    exchange_record: ExchangeRecord | None = None
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_consistent_exchange_record(self) -> ControllerContextEvent:
        if self.direction is ContextDirection.EVENT:
            if self.exchange_id is not None or self.exchange_record is not None:
                raise ValueError("general events cannot contain peer exchange data")
            return self
        if self.exchange_record is None or self.exchange_id is None:
            raise ValueError("peer exchange events require exchange_id and exchange_record")
        if self.exchange_record.case_id != self.case_id:
            raise ValueError("event case_id must match exchange record")
        if self.exchange_record.exchange_id != self.exchange_id:
            raise ValueError("event exchange_id must match exchange record")
        if self.exchange_record.trace_context != self.trace_context:
            raise ValueError("event trace context must match exchange record")
        if self.exchange_record.direction.value != self.direction.value:
            raise ValueError("event direction must match exchange record")
        return self


class ControllerContextAppendError(RecorderError):
    """A context event could not be appended without loss or mutation."""


class ControllerContextStore(Protocol):
    def append(self, event: ControllerContextEvent) -> None: ...

    def events_for(self, case_id: str) -> tuple[ControllerContextEvent, ...]: ...


class ControllerAuditRecorder:
    """Persist and emit concise redacted Controller lifecycle events (ARD-OBS-001..004)."""

    def __init__(self, store: ControllerContextStore) -> None:
        self._store = store

    def record(
        self,
        *,
        event_id: str,
        event_type: str,
        case_id: str,
        request_id: str | None,
        trace_context: TraceContext,
        occurred_at: datetime,
        status: str,
        rationale: str,
        evidence_references: tuple[str, ...] = (),
        details: dict[str, object] | None = None,
    ) -> StructuredError | None:
        audit_event = AuditEvent(
            schema_version="1.0",
            occurred_at=occurred_at,
            event_type=event_type,
            case_id=case_id,
            request_id=request_id,
            trace_context=trace_context,
            component="controller",
            status=status,
            evidence_references=evidence_references,
            rationale=rationale[:500],
            details=details or {},
        )
        try:
            safe_details = json.loads(serialize_event(audit_event))["details"]
            context_event = ControllerContextEvent(
                event_id=event_id,
                event_type=event_type,
                case_id=case_id,
                trace_context=trace_context,
                occurred_at=occurred_at,
                direction=ContextDirection.EVENT,
                status=status,
                evidence_references=evidence_references,
                details=safe_details,
            )
            with correlation_scope(case_id, trace_context, request_id):
                self._store.append(context_event)
                emit_event(audit_event)
        except Exception as error:
            return StructuredError(
                schema_version="1.0",
                category="controller_audit_append_failed",
                component="controller-audit-recorder",
                message=f"Controller audit event was not retained ({type(error).__name__})",
                retryable=False,
                case_impact=f"Audit event '{event_type}' is unavailable in case context",
            )
        return None


class InMemoryControllerContextStore:
    """Deterministic local store; production persistence can implement the same append port."""

    def __init__(self, fail_on_event_ids: frozenset[str] = frozenset()) -> None:
        self._events: dict[str, list[ControllerContextEvent]] = {}
        self._fail_on_event_ids = fail_on_event_ids

    def append(self, event: ControllerContextEvent) -> None:
        if event.event_id in self._fail_on_event_ids:
            raise ControllerContextAppendError("synthetic Controller context append failure")

        case_events = self._events.setdefault(event.case_id, [])
        existing = next((item for item in case_events if item.event_id == event.event_id), None)
        if existing is not None:
            if existing == event:
                return
            raise ControllerContextAppendError("event ID already has different content")

        if event.direction is ContextDirection.RESPONSE and not any(
            item.direction is ContextDirection.REQUEST and item.exchange_id == event.exchange_id
            for item in case_events
        ):
            raise ControllerContextAppendError("peer response cannot be recorded before request")
        case_events.append(event)

    def events_for(self, case_id: str) -> tuple[ControllerContextEvent, ...]:
        return tuple(self._events.get(case_id, ()))

    @property
    def events(self) -> tuple[ControllerContextEvent, ...]:
        return tuple(event for case_events in self._events.values() for event in case_events)


class ControllerCaseContextRecorder(CaseContextRecorder):
    """Persist existing H3/H4 messages through the Controller's case context port."""

    def __init__(self, store: ControllerContextStore) -> None:
        self._store = store
        self.audit = ControllerAuditRecorder(store)

    def append(self, record: ExchangeRecord) -> None:
        direction = (
            ContextDirection.REQUEST
            if record.direction is ExchangeDirection.REQUEST
            else ContextDirection.RESPONSE
        )
        self._store.append(
            ControllerContextEvent(
                event_id=f"peer-exchange:{record.exchange_id}:{direction.value}",
                event_type="peer_exchange",
                case_id=record.case_id,
                trace_context=record.trace_context,
                occurred_at=record.occurred_at,
                direction=direction,
                status=record.status.value,
                evidence_references=record.evidence_references,
                exchange_id=record.exchange_id,
                exchange_record=record,
            )
        )
