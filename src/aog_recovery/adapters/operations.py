import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.observability.context import correlation_scope
from aog_recovery.observability.structured import emit_event
from aog_recovery.operations.contracts import (
    AdapterReadResult,
    EvidenceState,
    OperationsAdapterRequest,
    OperationsToolName,
)

OPERATIONS_TOOL_ALLOWLIST: frozenset[OperationsToolName] = frozenset(OperationsToolName)
OPERATIONS_TOOL_ROLE_ALLOWLIST: Mapping[OperationsToolName, frozenset[AgentRole]] = (
    MappingProxyType(
        {tool_name: frozenset({AgentRole.OPERATIONS}) for tool_name in OperationsToolName}
    )
)


class OperationsReadOnlyAdapter(Protocol):
    tool_name: OperationsToolName
    allowed_roles: frozenset[AgentRole]
    source: str

    async def read(
        self,
        request: OperationsAdapterRequest,
        caller_role: AgentRole,
    ) -> AdapterReadResult: ...


class OperationsMockResponseMode(StrEnum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"
    STALE = "stale"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"


class LocalOperationsAdapter:
    def __init__(
        self,
        tool_name: OperationsToolName,
        source: str,
        fixture_timestamp: datetime,
        fixture_data: Mapping[str, object],
        response_mode: OperationsMockResponseMode = OperationsMockResponseMode.SUCCESS,
    ) -> None:
        self.tool_name = tool_name
        self.allowed_roles = OPERATIONS_TOOL_ROLE_ALLOWLIST[tool_name]
        self.source = source
        self.fixture_timestamp = fixture_timestamp
        self.fixture_data = dict(fixture_data)
        self.response_mode = response_mode

    async def read(
        self,
        request: OperationsAdapterRequest,
        caller_role: AgentRole,
    ) -> AdapterReadResult:
        with correlation_scope(request.case_id, request.trace_context, request.request_id):
            result = self._read(request, caller_role)
            emit_event(
                AuditEvent(
                    schema_version="1.0",
                    occurred_at=result.observed_at or self.fixture_timestamp,
                    event_type="tool_result",
                    case_id=result.case_id,
                    request_id=result.request_id,
                    trace_context=result.trace_context,
                    component=f"operations-adapter:{result.tool_name.value}",
                    status=result.state.value,
                    evidence_references=(),
                    rationale="Read-only Operations adapter result recorded",
                    details={
                        "source": result.source,
                        "error_category": result.error.category if result.error else None,
                    },
                )
            )
            return result

    def _read(
        self,
        request: OperationsAdapterRequest,
        caller_role: AgentRole,
    ) -> AdapterReadResult:
        if request.tool_name not in OPERATIONS_TOOL_ALLOWLIST:
            return self._failure(request, "tool_not_allowlisted", "requested tool is not allowed")
        if request.tool_name is not self.tool_name:
            return self._failure(request, "tool_not_allowlisted", "requested tool is not allowed")
        if caller_role not in self.allowed_roles:
            return self._failure(request, "role_not_allowlisted", "caller role is not allowed")
        if self.response_mode in {
            OperationsMockResponseMode.UNAVAILABLE,
            OperationsMockResponseMode.TIMEOUT,
            OperationsMockResponseMode.MALFORMED,
        }:
            categories = {
                OperationsMockResponseMode.UNAVAILABLE: "source_unavailable",
                OperationsMockResponseMode.TIMEOUT: "timeout",
                OperationsMockResponseMode.MALFORMED: "malformed_response",
            }
            messages = {
                OperationsMockResponseMode.UNAVAILABLE: "synthetic source is unavailable",
                OperationsMockResponseMode.TIMEOUT: "synthetic source request timed out",
                OperationsMockResponseMode.MALFORMED: "synthetic response is malformed",
            }
            return self._failure(
                request,
                categories[self.response_mode],
                messages[self.response_mode],
                retryable=self.response_mode is OperationsMockResponseMode.TIMEOUT,
            )

        state = {
            OperationsMockResponseMode.SUCCESS: EvidenceState.CURRENT,
            OperationsMockResponseMode.STALE: EvidenceState.STALE,
            OperationsMockResponseMode.PARTIAL: EvidenceState.PARTIAL,
            OperationsMockResponseMode.CONFLICTING: EvidenceState.CONFLICTING,
        }[self.response_mode]
        return AdapterReadResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            tool_name=self.tool_name,
            source=self.source,
            observed_at=self.fixture_timestamp,
            state=state,
            data=dict(self.fixture_data),
            error=None,
        )

    def _failure(
        self,
        request: OperationsAdapterRequest,
        category: str,
        message: str,
        retryable: bool = False,
    ) -> AdapterReadResult:
        return AdapterReadResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            tool_name=request.tool_name,
            source=self.source,
            observed_at=self.fixture_timestamp,
            state=EvidenceState.UNAVAILABLE,
            data=None,
            error=StructuredError(
                schema_version="1.0",
                category=category,
                component=f"operations-adapter:{self.tool_name.value}",
                message=message,
                retryable=retryable,
                case_impact="requested Operations evidence is unavailable",
            ),
        )


class OperationsAdapterExecutor:
    def __init__(self, timeout_seconds: float, max_retries: int) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def read(
        self,
        adapter: OperationsReadOnlyAdapter,
        request: OperationsAdapterRequest,
        caller_role: AgentRole,
    ) -> AdapterReadResult:
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    adapter.read(request, caller_role),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError:
                result = self._timeout_result(adapter, request)
            if result.error is None or not result.error.retryable or attempt == self.max_retries:
                return result
        raise RuntimeError("Operations adapter retry loop ended without a result")

    @staticmethod
    def _timeout_result(
        adapter: OperationsReadOnlyAdapter,
        request: OperationsAdapterRequest,
    ) -> AdapterReadResult:
        result = AdapterReadResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            tool_name=adapter.tool_name,
            source=adapter.source,
            observed_at=datetime.now(UTC),
            state=EvidenceState.UNAVAILABLE,
            data=None,
            error=StructuredError(
                schema_version="1.0",
                category="timeout",
                component=f"operations-adapter:{adapter.tool_name.value}",
                message="Operations read exceeded its configured timeout.",
                retryable=True,
                case_impact="requested Operations evidence is unavailable",
            ),
        )
        emit_event(
            AuditEvent(
                schema_version="1.0",
                occurred_at=result.observed_at or datetime.now(UTC),
                event_type="tool_timeout",
                case_id=result.case_id,
                request_id=result.request_id,
                trace_context=result.trace_context,
                component=f"operations-adapter:{adapter.tool_name.value}",
                status=result.state.value,
                evidence_references=(),
                rationale="Read-only Operations adapter timed out",
                details={"error_category": "timeout"},
            )
        )
        return result
