import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import EvidenceWarning
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
