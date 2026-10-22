from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum

from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.evidence import EvidenceWarning
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult, ToolResultStatus
from aog_recovery.observability.context import correlation_scope
from aog_recovery.observability.structured import emit_event

TOOL_ROLE_ALLOWLIST: dict[ToolName, frozenset[AgentRole]] = {
    ToolName.MAINTENANCE_RECORDS: frozenset({AgentRole.CONTROLLER, AgentRole.MAINTENANCE}),
    ToolName.PART_INVENTORY: frozenset(
        {AgentRole.CONTROLLER, AgentRole.MAINTENANCE, AgentRole.MATERIALS_LOGISTICS}
    ),
    ToolName.OPERATIONS_STATUS: frozenset({AgentRole.CONTROLLER, AgentRole.OPERATIONS}),
    ToolName.FLIGHT_SCHEDULE: frozenset({AgentRole.CONTROLLER, AgentRole.OPERATIONS}),
    ToolName.FLEET_AVAILABILITY: frozenset({AgentRole.CONTROLLER, AgentRole.OPERATIONS}),
    ToolName.PACKAGE_LOAD: frozenset({AgentRole.CONTROLLER, AgentRole.OPERATIONS}),
    ToolName.ALTERNATE_FLIGHTS: frozenset({AgentRole.CONTROLLER, AgentRole.OPERATIONS}),
}


class MockResponseMode(StrEnum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"
    STALE = "stale"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"


class LocalReadOnlyAdapter:
    def __init__(
        self,
        tool_name: ToolName,
        source: str,
        fixture_timestamp: datetime,
        fixture_data: Mapping[str, object],
        response_mode: MockResponseMode,
    ) -> None:
        self.tool_name = tool_name
        self.allowed_roles = TOOL_ROLE_ALLOWLIST[tool_name]
        self.source = source
        self.fixture_timestamp = fixture_timestamp
        self.fixture_data = dict(fixture_data)
        self.response_mode = response_mode

    def read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult:
        with correlation_scope(request.case_id, request.trace_context, request.request_id):
            result = self._read(request, caller_role)
            emit_event(
                AuditEvent(
                    schema_version="1.0",
                    occurred_at=result.completed_at,
                    event_type="tool_result",
                    case_id=result.case_id,
                    request_id=result.request_id,
                    trace_context=result.trace_context,
                    component=f"local-adapter:{self.tool_name.value}",
                    status=result.status.value,
                    evidence_references=(),
                    rationale="Read-only adapter result recorded",
                    details={
                        "source": result.source,
                        "warning_codes": [warning.code for warning in result.warnings],
                        "error_category": result.error.category if result.error else None,
                    },
                )
            )
            return result

    def _read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult:
        if request.tool_name is not self.tool_name:
            return self._failure(request, "tool_not_allowlisted", "requested tool is not allowed")
        if caller_role not in self.allowed_roles:
            return self._failure(request, "role_not_allowlisted", "caller role is not allowed")
        if self.response_mode is MockResponseMode.UNAVAILABLE:
            return self._failure(request, "source_unavailable", "synthetic source is unavailable")
        if self.response_mode is MockResponseMode.TIMEOUT:
            return self._failure(
                request,
                "timeout",
                "synthetic source request timed out",
                retryable=True,
            )
        if self.response_mode is MockResponseMode.MALFORMED:
            return self._failure(
                request,
                "malformed_response",
                "synthetic source returned malformed data",
            )
        if self.response_mode in {
            MockResponseMode.STALE,
            MockResponseMode.PARTIAL,
            MockResponseMode.CONFLICTING,
        }:
            warning_code = {
                MockResponseMode.STALE: "STALE_EVIDENCE",
                MockResponseMode.PARTIAL: "PARTIAL_DATA",
                MockResponseMode.CONFLICTING: "CONFLICTING_DATA",
            }[self.response_mode]
            warning_message = {
                MockResponseMode.STALE: "synthetic source data is stale",
                MockResponseMode.PARTIAL: "synthetic source data is incomplete",
                MockResponseMode.CONFLICTING: "synthetic sources disagree",
            }[self.response_mode]
            return ToolResult(
                schema_version="1.0",
                request_id=request.request_id,
                case_id=request.case_id,
                trace_context=request.trace_context,
                source=self.source,
                completed_at=self.fixture_timestamp,
                status=ToolResultStatus.PARTIAL,
                warnings=(
                    EvidenceWarning(
                        warning_id=f"warning-{request.request_id}",
                        claim_reference=f"tool-request:{request.request_id}",
                        code=warning_code,
                        message=warning_message,
                        source_reference=self.source,
                    ),
                ),
                data=dict(self.fixture_data),
                error=None,
            )

        return ToolResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            source=self.source,
            completed_at=self.fixture_timestamp,
            status=ToolResultStatus.SUCCESS,
            warnings=(),
            data=dict(self.fixture_data),
            error=None,
        )

    def _failure(
        self,
        request: ToolRequest,
        category: str,
        message: str,
        retryable: bool = False,
    ) -> ToolResult:
        return ToolResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            source=self.source,
            completed_at=self.fixture_timestamp,
            status=ToolResultStatus.FAILED,
            warnings=(),
            data=None,
            error=StructuredError(
                schema_version="1.0",
                category=category,
                component=f"local-adapter:{self.tool_name.value}",
                message=message,
                retryable=retryable,
                case_impact="requested read is unavailable",
            ),
        )
