import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import EvidenceWarning
from aog_recovery.controller.context import (
    ContextDirection,
    ControllerAuditRecorder,
    ControllerCaseContextRecorder,
    ControllerContextAppendError,
    InMemoryControllerContextStore,
)
from aog_recovery.coordination.models import (
    DegradationStatus,
    ExchangeStatus,
    H3H4Exchange,
    H3ReplacementStrategyRequest,
    H4AvailabilityResponse,
)
from aog_recovery.coordination.recording import (
    ExchangeDirection,
    ExchangeRecord,
    ExchangeRecordingStatus,
    InMemoryCaseContextRecorder,
    RecorderError,
    record_h3_h4_exchange,
)
from aog_recovery.materials_logistics.models import RequestedPartComparison
from aog_recovery.observability.structured import LOGGER

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def exchange(case_id: str = "case-001", exchange_id: str = "exchange-001") -> H3H4Exchange:
    trace = TraceContext(trace_id="trace-001", correlation_id="corr-001")
    request = H3ReplacementStrategyRequest(
        schema_version="1.0",
        case_id=case_id,
        exchange_id=exchange_id,
        request_id=f"{exchange_id}-request",
        trace_context=trace,
        source=AgentRole.MAINTENANCE,
        sent_at=TIMESTAMP,
        status=ExchangeStatus.COMPLETE,
        failed_part_number="P-110",
        preferred_part_number="P-120",
        aircraft_id="TEST-AIRCRAFT-001",
        station="TEST-STATION-A",
        need_by_time=TIMESTAMP,
        recurring_failure_count=3,
        recurring_failure_window_days=90,
        maintenance_evidence_references=("maintenance-evidence-001",),
        degradation_status=DegradationStatus.NONE,
        missing_data=(),
        warnings=(),
    )
    response = H4AvailabilityResponse(
        schema_version="1.0",
        case_id=case_id,
        exchange_id=exchange_id,
        response_id=f"{exchange_id}-response",
        trace_context=trace,
        source=AgentRole.MATERIALS_LOGISTICS,
        responded_at=TIMESTAMP,
        status=ExchangeStatus.PARTIAL,
        confidence=0.65,
        failed_part_number="P-110",
        preferred_part_number="P-120",
        aircraft_id="TEST-AIRCRAFT-001",
        station="TEST-STATION-A",
        need_by_time=TIMESTAMP,
        part_comparison=RequestedPartComparison(
            failed_part_number="P-110",
            failed_part_assessments=(),
            preferred_part_number="P-120",
            preferred_part_assessments=(),
            missing_part_numbers=("P-110", "P-120"),
        ),
        sourcing_options=(),
        evidence_references=(),
        degradation_status=DegradationStatus.MISSING,
        missing_data=("inventory evidence",),
        warnings=(
            EvidenceWarning(
                warning_id="warning-001",
                claim_reference="exchange-001-response",
                code="PARTIAL_DATA",
                message="synthetic source data is incomplete",
                source_reference="synthetic-source",
            ),
        ),
        errors=(),
        conflicts=(),
    )
    return H3H4Exchange(request=request, response=response)


def test_recorder_appends_request_before_response_and_correlates_audit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = InMemoryCaseContextRecorder()

    with caplog.at_level("INFO", logger=LOGGER.name):
        result = record_h3_h4_exchange(exchange(), recorder)

    assert result.status is ExchangeRecordingStatus.COMPLETE
    assert [record.direction for record in result.records] == [
        ExchangeDirection.REQUEST,
        ExchangeDirection.RESPONSE,
    ]
    assert recorder.records == result.records
    events = [json.loads(record.message) for record in caplog.records]
    assert [event["details"]["direction"] for event in events] == ["request", "response"]
    assert {event["case_id"] for event in events} == {"case-001"}
    assert {event["request_id"] for event in events} == {"exchange-001"}
    assert {event["trace_context"]["trace_id"] for event in events} == {"trace-001"}


def test_recorder_is_idempotent_for_repeated_exchange_ids() -> None:
    recorder = InMemoryCaseContextRecorder()
    peer_exchange = exchange()

    first = record_h3_h4_exchange(peer_exchange, recorder)
    second = record_h3_h4_exchange(peer_exchange, recorder)

    assert first.status is ExchangeRecordingStatus.COMPLETE
    assert second.status is ExchangeRecordingStatus.COMPLETE
    assert len(recorder.records) == 2


def test_recorder_isolates_cases_when_exchange_ids_are_reused() -> None:
    recorder = InMemoryCaseContextRecorder()

    record_h3_h4_exchange(exchange("case-001", "exchange-shared"), recorder)
    record_h3_h4_exchange(exchange("case-002", "exchange-shared"), recorder)

    assert len(recorder.records_for("case-001", "exchange-shared")) == 2
    assert len(recorder.records_for("case-002", "exchange-shared")) == 2
    assert len(recorder.records) == 4


def test_recording_failure_returns_incomplete_result_and_keeps_partial_record() -> None:
    recorder = InMemoryCaseContextRecorder(
        fail_on_directions=frozenset({ExchangeDirection.RESPONSE})
    )

    result = record_h3_h4_exchange(exchange(), recorder)

    assert result.status is ExchangeRecordingStatus.INCOMPLETE
    assert result.error is not None
    assert result.error.category == "case_context_recording_failed"
    assert [record.direction for record in result.records] == [ExchangeDirection.REQUEST]
    assert len(recorder.records) == 1


def test_recorder_rejects_response_before_request_and_has_no_mutating_api() -> None:
    peer_exchange = exchange()
    response = peer_exchange.response
    record = ExchangeRecord(
        case_id=response.case_id,
        exchange_id=response.exchange_id,
        trace_context=response.trace_context,
        direction=ExchangeDirection.RESPONSE,
        occurred_at=response.responded_at,
        status=response.status,
        evidence_references=response.evidence_references,
        message=response,
    )
    recorder = InMemoryCaseContextRecorder()

    with pytest.raises(RecorderError, match="cannot be recorded before"):
        recorder.append(record)

    assert not hasattr(recorder, "update")
    assert not hasattr(recorder, "delete")
    assert recorder.records == ()


def test_exchange_record_rejects_message_identifier_mismatch() -> None:
    request = exchange().request

    with pytest.raises(ValidationError, match="record case_id must match"):
        ExchangeRecord(
            case_id="other-case",
            exchange_id=request.exchange_id,
            trace_context=request.trace_context,
            direction=ExchangeDirection.REQUEST,
            occurred_at=request.sent_at,
            status=request.status,
            evidence_references=request.maintenance_evidence_references,
            message=request,
        )


def test_controller_context_adapter_preserves_metadata_and_order() -> None:
    store = InMemoryControllerContextStore()
    peer_exchange = exchange()

    result = record_h3_h4_exchange(peer_exchange, ControllerCaseContextRecorder(store))
    events = store.events_for("case-001")

    assert result.status is ExchangeRecordingStatus.COMPLETE
    assert [event.direction for event in events] == [
        ContextDirection.REQUEST,
        ContextDirection.RESPONSE,
    ]
    assert [event.occurred_at for event in events] == [TIMESTAMP, TIMESTAMP]
    assert {event.trace_context.correlation_id for event in events} == {"corr-001"}
    assert all(event.exchange_record is not None for event in events)


def test_controller_context_adapter_is_idempotent_and_case_isolated() -> None:
    store = InMemoryControllerContextStore()
    recorder = ControllerCaseContextRecorder(store)

    record_h3_h4_exchange(exchange("case-001", "exchange-shared"), recorder)
    repeated = record_h3_h4_exchange(exchange("case-001", "exchange-shared"), recorder)
    record_h3_h4_exchange(exchange("case-002", "exchange-shared"), recorder)

    assert repeated.status is ExchangeRecordingStatus.COMPLETE
    assert len(store.events_for("case-001")) == 2
    assert len(store.events_for("case-002")) == 2
    assert len(store.events) == 4


def test_controller_context_append_failure_is_visible() -> None:
    store = InMemoryControllerContextStore(
        fail_on_event_ids=frozenset({"peer-exchange:exchange-001:response"})
    )

    result = record_h3_h4_exchange(exchange(), ControllerCaseContextRecorder(store))

    assert result.status is ExchangeRecordingStatus.INCOMPLETE
    assert result.error is not None
    assert result.error.category == "case_context_recording_failed"
    assert [event.direction for event in store.events_for("case-001")] == [ContextDirection.REQUEST]


def test_controller_context_store_rejects_response_before_request() -> None:
    peer_exchange = exchange()
    response = peer_exchange.response
    record = ExchangeRecord(
        case_id=response.case_id,
        exchange_id=response.exchange_id,
        trace_context=response.trace_context,
        direction=ExchangeDirection.RESPONSE,
        occurred_at=response.responded_at,
        status=response.status,
        evidence_references=response.evidence_references,
        message=response,
    )
    store = InMemoryControllerContextStore()

    with pytest.raises(ControllerContextAppendError, match="before request"):
        ControllerCaseContextRecorder(store).append(record)

    assert store.events_for("case-001") == ()


def test_controller_audit_events_are_correlated_redacted_and_case_isolated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryControllerContextStore()
    audit = ControllerAuditRecorder(store)
    trace = TraceContext(trace_id="trace-001", correlation_id="corr-001")

    with caplog.at_level("INFO", logger=LOGGER.name):
        error = audit.record(
            event_id="case-001:routing",
            event_type="controller_routing",
            case_id="case-001",
            request_id="request-001",
            trace_context=trace,
            occurred_at=TIMESTAMP,
            status="selected",
            rationale="Deterministic specialist route recorded",
            evidence_references=("evidence-001",),
            details={
                "selected_roles": ["maintenance"],
                "api_token": "synthetic-secret",
                "nested": {"authorization": "synthetic-auth"},
            },
        )
        audit.record(
            event_id="case-002:routing",
            event_type="controller_routing",
            case_id="case-002",
            request_id="request-002",
            trace_context=TraceContext(trace_id="trace-002", correlation_id="corr-002"),
            occurred_at=TIMESTAMP,
            status="selected",
            rationale="Second isolated case",
        )

    assert error is None
    case_events = store.events_for("case-001")
    assert len(case_events) == 1
    assert case_events[0].direction is ContextDirection.EVENT
    assert case_events[0].trace_context.correlation_id == "corr-001"
    assert case_events[0].evidence_references == ("evidence-001",)
    assert case_events[0].details["api_token"] == "[REDACTED]"
    assert case_events[0].details["nested"]["authorization"] == "[REDACTED]"
    assert len(store.events_for("case-002")) == 1
    serialized = "\n".join(record.message for record in caplog.records)
    assert "synthetic-secret" not in serialized
    assert "synthetic-auth" not in serialized
    assert "corr-001" in serialized


def test_controller_audit_append_failure_is_returned_as_structured_error() -> None:
    store = InMemoryControllerContextStore(fail_on_event_ids=frozenset({"case-001:intake"}))
    audit = ControllerAuditRecorder(store)

    error = audit.record(
        event_id="case-001:intake",
        event_type="controller_intake_validated",
        case_id="case-001",
        request_id="request-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
        occurred_at=TIMESTAMP,
        status="accepted",
        rationale="Validated intake",
    )

    assert error is not None
    assert error.category == "controller_audit_append_failed"
    assert store.events_for("case-001") == ()
