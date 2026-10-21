import json
from datetime import UTC, datetime

import pytest

from aog_recovery.adapters.local import LocalReadOnlyAdapter, MockResponseMode
from aog_recovery.adk.context import bind_invocation_context
from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResultStatus
from aog_recovery.observability.context import current_correlation_context
from aog_recovery.observability.structured import LOGGER

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def request(tool_name: ToolName = ToolName.MAINTENANCE_RECORDS) -> ToolRequest:
    return ToolRequest(
        schema_version="1.0",
        request_id="req-001",
        case_id="case-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
        tool_name=tool_name,
        requested_at=TIMESTAMP,
        parameters={"aircraft_id": "N123AB"},
        access_mode="read",
    )


def adapter(response_mode: MockResponseMode = MockResponseMode.SUCCESS) -> LocalReadOnlyAdapter:
    return LocalReadOnlyAdapter(
        tool_name=ToolName.MAINTENANCE_RECORDS,
        source="synthetic-maintenance-fixture",
        fixture_timestamp=TIMESTAMP,
        fixture_data={"record_id": "synthetic-001", "status": "pending"},
        response_mode=response_mode,
    )


def test_local_adapter_returns_repeatable_fixture_results(caplog: pytest.LogCaptureFixture) -> None:
    local_adapter = adapter()

    with caplog.at_level("INFO", logger=LOGGER.name):
        first = local_adapter.read(request(), AgentRole.MAINTENANCE)
    second = local_adapter.read(request(), AgentRole.MAINTENANCE)

    assert first == second
    assert first.status is ToolResultStatus.SUCCESS
    assert first.data == {"record_id": "synthetic-001", "status": "pending"}
    event = json.loads(caplog.records[0].message)
    assert event["case_id"] == first.case_id
    assert event["request_id"] == first.request_id
    assert event["trace_context"] == first.trace_context.model_dump(mode="json")


def test_adapter_correlation_context_is_reset_after_call() -> None:
    adapter().read(request(), AgentRole.MAINTENANCE)

    assert current_correlation_context() is None


def test_adk_invocation_binding_propagates_case_trace_and_request_ids() -> None:
    with bind_invocation_context("case-001", request().trace_context, "req-001") as context:
        assert context.case_id == "case-001"
        assert context.trace_id == "trace-001"
        assert context.correlation_id == "corr-001"
        assert context.request_id == "req-001"
        assert current_correlation_context() == context


def test_local_adapter_rejects_caller_outside_role_allowlist() -> None:
    result = adapter().read(request(), AgentRole.OPERATIONS)

    assert result.status is ToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.category == "role_not_allowlisted"
    assert result.data is None


def test_local_adapter_rejects_tool_outside_adapter_contract() -> None:
    result = adapter().read(request(ToolName.PART_INVENTORY), AgentRole.MAINTENANCE)

    assert result.status is ToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.category == "tool_not_allowlisted"


def test_local_adapter_exposes_no_operational_write_method() -> None:
    assert not hasattr(adapter(), "write")


def test_failure_modes_are_explicit_and_never_success_shaped() -> None:
    for response_mode, expected_category in (
        (MockResponseMode.UNAVAILABLE, "source_unavailable"),
        (MockResponseMode.TIMEOUT, "timeout"),
        (MockResponseMode.MALFORMED, "malformed_response"),
    ):
        result = adapter(response_mode).read(request(), AgentRole.MAINTENANCE)

        assert result.status is ToolResultStatus.FAILED
        assert result.data is None
        assert result.error is not None
        assert result.error.category == expected_category


def test_degraded_modes_keep_warning_and_partial_data_visible() -> None:
    for response_mode, expected_code in (
        (MockResponseMode.STALE, "STALE_EVIDENCE"),
        (MockResponseMode.PARTIAL, "PARTIAL_DATA"),
        (MockResponseMode.CONFLICTING, "CONFLICTING_DATA"),
    ):
        result = adapter(response_mode).read(request(), AgentRole.MAINTENANCE)

        assert result.status is ToolResultStatus.PARTIAL
        assert result.data is not None
        assert result.warnings[0].code == expected_code
        assert result.error is None


def test_timeout_result_is_stable_and_preserves_request_identity() -> None:
    timed_out_adapter = adapter(MockResponseMode.TIMEOUT)

    first = timed_out_adapter.read(request(), AgentRole.MAINTENANCE)
    second = timed_out_adapter.read(request(), AgentRole.MAINTENANCE)

    assert first == second
    assert first.request_id == "req-001"
    assert first.error is not None and first.error.retryable
