import asyncio
import json
from datetime import UTC, datetime

import pytest

from aog_recovery.adapters.operations import (
    OPERATIONS_TOOL_ALLOWLIST,
    OPERATIONS_TOOL_ROLE_ALLOWLIST,
    LocalOperationsAdapter,
    OperationsAdapterExecutor,
    OperationsMockResponseMode,
)
from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.case import TraceContext
from aog_recovery.observability.structured import LOGGER
from aog_recovery.operations.contracts import (
    AdapterReadResult,
    EvidenceState,
    OperationsAdapterRequest,
    OperationsToolName,
)

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
TRACE = TraceContext(trace_id="trace-ops-001", correlation_id="corr-ops-001")


def request(
    tool_name: OperationsToolName = OperationsToolName.VALIDATE_FLIGHT_SCHEDULE,
) -> OperationsAdapterRequest:
    return OperationsAdapterRequest(
        schema_version="1.0",
        request_id="request-ops-001",
        case_id="case-ops-001",
        trace_context=TRACE,
        tool_name=tool_name,
        requested_at=NOW,
        parameters={"flight_id": "FX401"},
        access_mode="read",
    )


def adapter(
    response_mode: OperationsMockResponseMode = OperationsMockResponseMode.SUCCESS,
    tool_name: OperationsToolName = OperationsToolName.VALIDATE_FLIGHT_SCHEDULE,
) -> LocalOperationsAdapter:
    return LocalOperationsAdapter(
        tool_name=tool_name,
        source="synthetic-operations-fixture",
        fixture_timestamp=NOW,
        fixture_data={"flight_id": "FX401", "route": "MEM-IND"},
        response_mode=response_mode,
    )


def test_registered_operations_tools_are_explicit_and_allowlisted() -> None:
    assert OPERATIONS_TOOL_ALLOWLIST == frozenset(
        {
            OperationsToolName.VALIDATE_FLIGHT_SCHEDULE,
            OperationsToolName.DETECT_ROUTE_CONFLICTS,
            OperationsToolName.CHECK_FLEET_AVAILABILITY,
            OperationsToolName.APPLY_DISRUPTION_THRESHOLDS,
            OperationsToolName.CHECK_LOAD_REDISTRIBUTION,
        }
    )


def test_role_allowlist_cannot_be_modified_at_runtime() -> None:
    with pytest.raises(TypeError):
        OPERATIONS_TOOL_ROLE_ALLOWLIST[OperationsToolName.VALIDATE_FLIGHT_SCHEDULE] = frozenset(
            {AgentRole.CONTROLLER}
        )


@pytest.mark.asyncio
async def test_local_adapter_returns_typed_read_only_result_and_audit_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_fixture_value = "sensitive-operations-fixture-value"
    local_adapter = LocalOperationsAdapter(
        tool_name=OperationsToolName.VALIDATE_FLIGHT_SCHEDULE,
        source="synthetic-operations-fixture",
        fixture_timestamp=NOW,
        fixture_data={"flight_id": "FX401", "private_note": private_fixture_value},
    )

    with caplog.at_level("INFO", logger=LOGGER.name):
        result = await local_adapter.read(request(), AgentRole.OPERATIONS)

    assert result.state is EvidenceState.CURRENT
    assert result.data == {"flight_id": "FX401", "private_note": private_fixture_value}
    assert result.request_id == "request-ops-001"
    assert result.case_id == "case-ops-001"
    assert result.trace_context == TRACE
    event = json.loads(caplog.records[0].message)
    assert event["case_id"] == result.case_id
    assert event["request_id"] == result.request_id
    assert event["status"] == EvidenceState.CURRENT.value
    assert private_fixture_value not in caplog.text
    assert not hasattr(local_adapter, "write")


@pytest.mark.asyncio
async def test_adapter_rejects_caller_outside_operations_role() -> None:
    result = await adapter().read(request(), AgentRole.CONTROLLER)

    assert result.state is EvidenceState.UNAVAILABLE
    assert result.data is None
    assert result.error is not None
    assert result.error.category == "role_not_allowlisted"


@pytest.mark.asyncio
async def test_adapter_rejects_tool_not_bound_to_adapter() -> None:
    result = await adapter().read(
        request(OperationsToolName.CHECK_FLEET_AVAILABILITY),
        AgentRole.OPERATIONS,
    )

    assert result.state is EvidenceState.UNAVAILABLE
    assert result.error is not None
    assert result.error.category == "tool_not_allowlisted"


@pytest.mark.parametrize(
    ("response_mode", "category", "retryable"),
    [
        (OperationsMockResponseMode.UNAVAILABLE, "source_unavailable", False),
        (OperationsMockResponseMode.TIMEOUT, "timeout", True),
        (OperationsMockResponseMode.MALFORMED, "malformed_response", False),
    ],
)
@pytest.mark.asyncio
async def test_adapter_errors_are_structured_and_never_success_shaped(
    response_mode: OperationsMockResponseMode,
    category: str,
    retryable: bool,
) -> None:
    result = await adapter(response_mode).read(request(), AgentRole.OPERATIONS)

    assert result.state is EvidenceState.UNAVAILABLE
    assert result.data is None
    assert result.error is not None
    assert result.error.category == category
    assert result.error.retryable is retryable


@pytest.mark.parametrize(
    ("response_mode", "state"),
    [
        (OperationsMockResponseMode.STALE, EvidenceState.STALE),
        (OperationsMockResponseMode.PARTIAL, EvidenceState.PARTIAL),
        (OperationsMockResponseMode.CONFLICTING, EvidenceState.CONFLICTING),
    ],
)
@pytest.mark.asyncio
async def test_adapter_preserves_degraded_evidence_state(
    response_mode: OperationsMockResponseMode,
    state: EvidenceState,
) -> None:
    result = await adapter(response_mode).read(request(), AgentRole.OPERATIONS)

    assert result.state is state
    assert result.data is not None
    assert result.error is None


def test_adapter_request_rejects_write_access_and_unknown_fields() -> None:
    payload = request().model_dump()
    payload["access_mode"] = "write"

    with pytest.raises(ValueError):
        OperationsAdapterRequest.model_validate(payload)

    payload = request().model_dump()
    payload["unexpected"] = "must be rejected"
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        OperationsAdapterRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_executor_applies_timeout_and_bounded_idempotent_retries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class SlowAdapter:
        tool_name = OperationsToolName.VALIDATE_FLIGHT_SCHEDULE
        allowed_roles = frozenset({AgentRole.OPERATIONS})
        source = "slow-synthetic-source"

        def __init__(self) -> None:
            self.request_ids: list[str] = []

        async def read(
            self,
            adapter_request: OperationsAdapterRequest,
            caller_role: AgentRole,
        ) -> AdapterReadResult:
            self.request_ids.append(adapter_request.request_id)
            await asyncio.sleep(0.05)
            return await adapter().read(adapter_request, caller_role)

    slow_adapter = SlowAdapter()
    with caplog.at_level("INFO", logger=LOGGER.name):
        result = await OperationsAdapterExecutor(timeout_seconds=0.001, max_retries=1).read(
            slow_adapter,
            request(),
            AgentRole.OPERATIONS,
        )

    assert result.state is EvidenceState.UNAVAILABLE
    assert result.error is not None
    assert result.error.category == "timeout"
    assert len(slow_adapter.request_ids) == 2
    assert slow_adapter.request_ids == ["request-ops-001", "request-ops-001"]
    timeout_events = [
        json.loads(record.message)
        for record in caplog.records
        if json.loads(record.message)["event_type"] == "tool_timeout"
    ]
    assert len(timeout_events) == 2
    assert all(event["case_id"] == "case-ops-001" for event in timeout_events)
    assert all(
        event["trace_context"]["correlation_id"] == TRACE.correlation_id for event in timeout_events
    )
    assert all(event["schema_version"] == "1.0" for event in timeout_events)


@pytest.mark.asyncio
async def test_executor_retries_only_retryable_structured_failures() -> None:
    class RetryThenSuccessAdapter:
        tool_name = OperationsToolName.VALIDATE_FLIGHT_SCHEDULE
        allowed_roles = frozenset({AgentRole.OPERATIONS})
        source = "retry-synthetic-source"

        def __init__(self) -> None:
            self.calls = 0

        async def read(
            self,
            adapter_request: OperationsAdapterRequest,
            caller_role: AgentRole,
        ) -> AdapterReadResult:
            self.calls += 1
            if self.calls == 1:
                return AdapterReadResult(
                    schema_version="1.0",
                    request_id=adapter_request.request_id,
                    case_id=adapter_request.case_id,
                    trace_context=adapter_request.trace_context,
                    tool_name=self.tool_name,
                    source=self.source,
                    observed_at=NOW,
                    state=EvidenceState.UNAVAILABLE,
                    data=None,
                    error=StructuredError(
                        schema_version="1.0",
                        category="temporary_unavailable",
                        component="retry-synthetic-source",
                        message="Synthetic temporary failure.",
                        retryable=True,
                        case_impact="Synthetic evidence is temporarily unavailable.",
                    ),
                )
            return await adapter().read(adapter_request, caller_role)

    retry_adapter = RetryThenSuccessAdapter()
    result = await OperationsAdapterExecutor(timeout_seconds=1, max_retries=1).read(
        retry_adapter,
        request(),
        AgentRole.OPERATIONS,
    )

    assert retry_adapter.calls == 2
    assert result.state is EvidenceState.CURRENT
