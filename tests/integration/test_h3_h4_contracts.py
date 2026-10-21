from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.case import TraceContext
from aog_recovery.coordination.models import (
    DegradationStatus,
    ExchangeStatus,
    H3H4Exchange,
    H3ReplacementStrategyRequest,
    H4AvailabilityResponse,
)
from aog_recovery.materials_logistics.models import (
    AvailabilityStatus,
    PartReadinessAssessment,
    PartRole,
    RequestedPartComparison,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def request() -> H3ReplacementStrategyRequest:
    return H3ReplacementStrategyRequest(
        schema_version="1.0",
        case_id="case-001",
        exchange_id="exchange-001",
        request_id="request-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
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


def response() -> H4AvailabilityResponse:
    part = PartReadinessAssessment(
        part_number="P-110",
        role=PartRole.FAILED_PART,
        availability_status=AvailabilityStatus.UNAVAILABLE,
        physically_available=False,
        practical_quantity=0,
        practically_available=False,
        location_consistent=True,
        eligible=True,
        findings=(),
        evidence_references=("inventory-evidence-001",),
    )
    return H4AvailabilityResponse(
        schema_version="1.0",
        case_id="case-001",
        exchange_id="exchange-001",
        response_id="response-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
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
            failed_part_assessments=(part,),
            preferred_part_number="P-120",
            preferred_part_assessments=(),
            missing_part_numbers=("P-120",),
        ),
        sourcing_options=(),
        evidence_references=("inventory-evidence-001",),
        degradation_status=DegradationStatus.MISSING,
        missing_data=("P-120 inventory",),
        warnings=(),
        errors=(),
        conflicts=(),
    )


def test_h3_h4_round_trip_preserves_exchange_and_degradation() -> None:
    exchange = H3H4Exchange(request=request(), response=response())

    assert exchange.request.exchange_id == exchange.response.exchange_id
    assert exchange.request.trace_context == exchange.response.trace_context
    assert exchange.response.part_comparison.missing_part_numbers == ("P-120",)
    assert exchange.response.degradation_status is DegradationStatus.MISSING


def test_exchange_rejects_mismatched_case_exchange_or_trace_ids() -> None:
    mismatched_case = response().model_copy(update={"case_id": "other-case"})
    with pytest.raises(ValidationError, match="case_id values must match"):
        H3H4Exchange(request=request(), response=mismatched_case)

    mismatched_exchange = response().model_copy(update={"exchange_id": "other-exchange"})
    with pytest.raises(ValidationError, match="exchange_id values must match"):
        H3H4Exchange(request=request(), response=mismatched_exchange)

    mismatched_trace = response().model_copy(
        update={"trace_context": TraceContext(trace_id="other-trace", correlation_id="corr-001")}
    )
    with pytest.raises(ValidationError, match="trace_context values must match"):
        H3H4Exchange(request=request(), response=mismatched_trace)


def test_h3_rejects_unsupported_schema_and_incomplete_recurrence_pair() -> None:
    payload = request().model_dump(mode="python")
    payload["schema_version"] = "2.0"

    with pytest.raises(ValidationError):
        H3ReplacementStrategyRequest.model_validate(payload)

    payload = request().model_dump(mode="python")
    payload["recurring_failure_window_days"] = None
    with pytest.raises(ValidationError, match="supplied together"):
        H3ReplacementStrategyRequest.model_validate(payload)


def test_h4_rejects_mismatched_nested_part_ids_and_unexplained_failures() -> None:
    mismatched_comparison = response().model_dump(mode="python")
    mismatched_comparison["part_comparison"]["failed_part_number"] = "P-999"
    with pytest.raises(ValidationError, match="comparison failed-part number"):
        H4AvailabilityResponse.model_validate(mismatched_comparison)

    unexplained_failure = response().model_dump(mode="python")
    unexplained_failure["status"] = ExchangeStatus.FAILED
    with pytest.raises(ValidationError, match="requires a structured error"):
        H4AvailabilityResponse.model_validate(unexplained_failure)
