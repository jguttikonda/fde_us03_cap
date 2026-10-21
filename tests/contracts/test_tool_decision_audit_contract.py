from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.governance import (
    HumanDecisionRecord,
    HumanDecisionType,
    ReviewerRole,
)
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult, ToolResultStatus

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
TRACE_CONTEXT = TraceContext(trace_id="trace-001", correlation_id="corr-001")


def test_tool_request_requires_correlation_and_read_only_mode() -> None:
    request = ToolRequest(
        schema_version="1.0",
        request_id="req-001",
        case_id="case-001",
        trace_context=TRACE_CONTEXT,
        tool_name=ToolName.MAINTENANCE_RECORDS,
        requested_at=TIMESTAMP,
        parameters={"aircraft_id": "N123AB"},
        access_mode="read",
    )

    assert request.trace_context.correlation_id == "corr-001"
    assert request.access_mode == "read"


def test_successful_tool_result_has_source_status_and_data() -> None:
    result = ToolResult(
        schema_version="1.0",
        request_id="req-001",
        case_id="case-001",
        trace_context=TRACE_CONTEXT,
        source="synthetic-maintenance-system",
        completed_at=TIMESTAMP,
        status=ToolResultStatus.SUCCESS,
        warnings=(),
        data={"record": "synthetic"},
        error=None,
    )

    assert result.source == "synthetic-maintenance-system"
    assert result.status is ToolResultStatus.SUCCESS


def test_failed_tool_result_requires_explicit_structured_error() -> None:
    error = StructuredError(
        schema_version="1.0",
        category="timeout",
        component="maintenance-adapter",
        message="Synthetic request timed out",
        retryable=True,
        case_impact="maintenance evidence is unavailable",
    )
    result = ToolResult(
        schema_version="1.0",
        request_id="req-002",
        case_id="case-001",
        trace_context=TRACE_CONTEXT,
        source="synthetic-maintenance-system",
        completed_at=TIMESTAMP,
        status=ToolResultStatus.FAILED,
        warnings=(),
        data=None,
        error=error,
    )

    assert result.error is error


def test_tool_failure_cannot_have_success_shaped_data() -> None:
    with pytest.raises(ValidationError, match="failed requires an error"):
        ToolResult(
            schema_version="1.0",
            request_id="req-003",
            case_id="case-001",
            trace_context=TRACE_CONTEXT,
            source="synthetic-maintenance-system",
            completed_at=TIMESTAMP,
            status=ToolResultStatus.FAILED,
            warnings=(),
            data={"record": "synthetic"},
            error=None,
        )


def test_human_decision_is_bound_to_recommendation_and_role() -> None:
    decision = HumanDecisionRecord(
        schema_version="1.0",
        decision_id="decision-001",
        case_id="case-001",
        decision=HumanDecisionType.APPROVE,
        selected_action="repair",
        selected_option_id="option-001",
        reviewer_id="synthetic-reviewer-001",
        reviewer_role=ReviewerRole.MAINTENANCE_AIRWORTHINESS,
        decided_at=TIMESTAMP,
        rationale="Synthetic approval test record",
        recommendation_version="recommendation-v2",
    )

    assert decision.recommendation_version == "recommendation-v2"
    assert decision.reviewer_role is ReviewerRole.MAINTENANCE_AIRWORTHINESS


def test_audit_event_retains_case_and_trace_metadata() -> None:
    event = AuditEvent(
        schema_version="1.0",
        occurred_at=TIMESTAMP,
        event_type="tool_result",
        case_id="case-001",
        request_id="req-001",
        trace_context=TRACE_CONTEXT,
        component="maintenance-adapter",
        status="success",
        evidence_references=("ev-001",),
        rationale="Synthetic source returned a valid record",
        details={"source": "synthetic-maintenance-system"},
    )

    assert event.case_id == "case-001"
    assert event.trace_context.trace_id == "trace-001"
    assert event.details["source"] == "synthetic-maintenance-system"
