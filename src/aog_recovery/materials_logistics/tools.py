"""Typed, read-only Materials & Logistics source adapters (ARD-MLG-001..009)."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from pydantic import Field, ValidationError, model_validator

from aog_recovery.adapters.local import MockResponseMode
from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus


class MaterialsToolName(StrEnum):
    MAINTENANCE_RECORDS = "maintenance_records"
    PART_INVENTORY = "part_inventory"
    ALTERNATE_PARTS = "alternate_parts"
    TRANSFER = "transfer"
    SUPPLIER = "supplier"
    SHIPPING = "shipping"


MATERIALS_TOOL_ROLE_ALLOWLIST: dict[MaterialsToolName, frozenset[AgentRole]] = {
    MaterialsToolName.MAINTENANCE_RECORDS: frozenset({AgentRole.CONTROLLER, AgentRole.MAINTENANCE}),
    MaterialsToolName.PART_INVENTORY: frozenset(
        {AgentRole.CONTROLLER, AgentRole.MAINTENANCE, AgentRole.MATERIALS_LOGISTICS}
    ),
    MaterialsToolName.ALTERNATE_PARTS: frozenset(
        {AgentRole.CONTROLLER, AgentRole.MATERIALS_LOGISTICS}
    ),
    MaterialsToolName.TRANSFER: frozenset({AgentRole.CONTROLLER, AgentRole.MATERIALS_LOGISTICS}),
    MaterialsToolName.SUPPLIER: frozenset({AgentRole.CONTROLLER, AgentRole.MATERIALS_LOGISTICS}),
    MaterialsToolName.SHIPPING: frozenset({AgentRole.CONTROLLER, AgentRole.MATERIALS_LOGISTICS}),
}


class MaterialsReadRequest(ContractModel):
    schema_version: Literal["1.0"]
    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    trace_context: TraceContext
    tool_name: MaterialsToolName
    requested_at: datetime
    aircraft_id: str | None = None
    part_number: str | None = None
    station: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    access_mode: Literal["read"]

    @model_validator(mode="after")
    def require_tool_inputs(self) -> MaterialsReadRequest:
        required_fields: dict[MaterialsToolName, tuple[str, ...]] = {
            MaterialsToolName.MAINTENANCE_RECORDS: ("aircraft_id",),
            MaterialsToolName.PART_INVENTORY: ("part_number", "station", "quantity"),
            MaterialsToolName.ALTERNATE_PARTS: ("part_number", "aircraft_id"),
            MaterialsToolName.TRANSFER: ("part_number", "station", "quantity"),
            MaterialsToolName.SUPPLIER: ("part_number", "quantity"),
            MaterialsToolName.SHIPPING: ("part_number", "station", "quantity"),
        }
        missing = [
            field_name
            for field_name in required_fields[self.tool_name]
            if getattr(self, field_name) is None
        ]
        if missing:
            raise ValueError(f"{self.tool_name.value} requires: {', '.join(missing)}")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return self


class MaterialsToolResult(ContractModel):
    schema_version: Literal["1.0"]
    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    trace_context: TraceContext
    source: str = Field(min_length=1)
    completed_at: datetime
    status: ToolResultStatus
    evidence: tuple[Evidence, ...] | None
    warnings: tuple[EvidenceWarning, ...]
    error: StructuredError | None

    @model_validator(mode="after")
    def require_status_consistent_result(self) -> MaterialsToolResult:
        if self.status is ToolResultStatus.SUCCESS and (
            self.evidence is None or self.error is not None or self.warnings
        ):
            raise ValueError("success requires evidence and cannot include warnings or errors")
        if self.status is ToolResultStatus.PARTIAL and (
            self.evidence is None or not self.warnings or self.error is not None
        ):
            raise ValueError("partial requires evidence and warnings, without an error")
        if self.status is ToolResultStatus.FAILED and (
            self.evidence is not None or self.error is None
        ):
            raise ValueError("failed requires an error and must not include evidence")
        if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return self


class MaterialsReadOnlyAdapter(Protocol):
    tool_name: MaterialsToolName
    allowed_roles: frozenset[AgentRole]

    def read(
        self,
        request: MaterialsReadRequest,
        caller_role: AgentRole,
    ) -> MaterialsToolResult: ...


class LocalMaterialsReadOnlyAdapter:
    def __init__(
        self,
        tool_name: MaterialsToolName,
        source: str,
        fixture_timestamp: datetime,
        fixture_evidence: tuple[Evidence, ...],
        response_mode: MockResponseMode = MockResponseMode.SUCCESS,
    ) -> None:
        self.tool_name = tool_name
        self.allowed_roles = MATERIALS_TOOL_ROLE_ALLOWLIST[tool_name]
        self.source = source
        self.fixture_timestamp = fixture_timestamp
        self.fixture_evidence = fixture_evidence
        self.response_mode = response_mode

    def read(
        self,
        request: MaterialsReadRequest,
        caller_role: AgentRole,
    ) -> MaterialsToolResult:
        if request.tool_name is not self.tool_name:
            return self._failure(request, "tool_not_allowlisted", "requested tool is not allowed")
        if caller_role not in self.allowed_roles:
            return self._failure(request, "role_not_allowlisted", "caller role is not allowed")
        if self.response_mode in {
            MockResponseMode.UNAVAILABLE,
            MockResponseMode.TIMEOUT,
            MockResponseMode.MALFORMED,
        }:
            categories = {
                MockResponseMode.UNAVAILABLE: "source_unavailable",
                MockResponseMode.TIMEOUT: "timeout",
                MockResponseMode.MALFORMED: "malformed_response",
            }
            messages = {
                MockResponseMode.UNAVAILABLE: "synthetic source is unavailable",
                MockResponseMode.TIMEOUT: "synthetic source request timed out",
                MockResponseMode.MALFORMED: "synthetic source returned malformed data",
            }
            return self._failure(
                request,
                categories[self.response_mode],
                messages[self.response_mode],
                retryable=self.response_mode is MockResponseMode.TIMEOUT,
            )
        if self.response_mode in {
            MockResponseMode.STALE,
            MockResponseMode.PARTIAL,
            MockResponseMode.CONFLICTING,
        }:
            validity_states = {
                MockResponseMode.STALE: EvidenceValidity.STALE,
                MockResponseMode.PARTIAL: EvidenceValidity.PARTIAL,
                MockResponseMode.CONFLICTING: EvidenceValidity.CONFLICTING,
            }
            warning_codes = {
                MockResponseMode.STALE: "STALE_EVIDENCE",
                MockResponseMode.PARTIAL: "PARTIAL_DATA",
                MockResponseMode.CONFLICTING: "CONFLICTING_DATA",
            }
            warning_messages = {
                MockResponseMode.STALE: "synthetic source data is stale",
                MockResponseMode.PARTIAL: "synthetic source data is incomplete",
                MockResponseMode.CONFLICTING: "synthetic sources disagree",
            }
            return MaterialsToolResult(
                schema_version="1.0",
                request_id=request.request_id,
                case_id=request.case_id,
                trace_context=request.trace_context,
                source=self.source,
                completed_at=self.fixture_timestamp,
                status=ToolResultStatus.PARTIAL,
                evidence=tuple(
                    item.model_copy(update={"validity_state": validity_states[self.response_mode]})
                    for item in self.fixture_evidence
                ),
                warnings=(
                    EvidenceWarning(
                        warning_id=f"warning-{request.request_id}",
                        claim_reference=f"tool-request:{request.request_id}",
                        code=warning_codes[self.response_mode],
                        message=warning_messages[self.response_mode],
                        source_reference=self.source,
                    ),
                ),
                error=None,
            )
        return MaterialsToolResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            source=self.source,
            completed_at=self.fixture_timestamp,
            status=ToolResultStatus.SUCCESS,
            evidence=self.fixture_evidence,
            warnings=(),
            error=None,
        )

    def _failure(
        self,
        request: MaterialsReadRequest,
        category: str,
        message: str,
        retryable: bool = False,
    ) -> MaterialsToolResult:
        return MaterialsToolResult(
            schema_version="1.0",
            request_id=request.request_id,
            case_id=request.case_id,
            trace_context=request.trace_context,
            source=self.source,
            completed_at=self.fixture_timestamp,
            status=ToolResultStatus.FAILED,
            evidence=None,
            warnings=(),
            error=StructuredError(
                schema_version="1.0",
                category=category,
                component=f"materials-adapter:{self.tool_name.value}",
                message=message,
                retryable=retryable,
                case_impact="requested read is unavailable",
            ),
        )


def build_materials_adk_tool(
    adapter: MaterialsReadOnlyAdapter,
    caller_role: AgentRole,
) -> FunctionTool:
    if caller_role not in adapter.allowed_roles:
        raise PermissionError(f"{caller_role.value} cannot access {adapter.tool_name.value}")

    def read_source(request: dict[str, object]) -> dict[str, object]:
        """Read one allowlisted Materials source using a validated request."""
        try:
            validated_request = MaterialsReadRequest.model_validate(
                {**request, "tool_name": adapter.tool_name.value}
            )
        except ValidationError as exc:
            raise ValueError("materials source request failed schema validation") from exc
        result = adapter.read(validated_request, caller_role)
        return result.model_dump(mode="json")

    read_source.__name__ = f"read_{adapter.tool_name.value}"
    read_source.__doc__ = f"Read synthetic {adapter.tool_name.value.replace('_', ' ')} evidence."
    return FunctionTool(func=read_source)


def build_materials_mcp_toolset(
    connection_params: StdioConnectionParams,
    caller_role: AgentRole,
) -> McpToolset:
    allowed_tools = [
        f"read_{tool_name.value}"
        for tool_name, allowed_roles in MATERIALS_TOOL_ROLE_ALLOWLIST.items()
        if caller_role in allowed_roles
    ]
    if not allowed_tools:
        raise PermissionError(f"{caller_role.value} has no Materials source tools")
    return McpToolset(connection_params=connection_params, tool_filter=allowed_tools)


def build_materials_adk_tools(
    adapters: Mapping[MaterialsToolName, MaterialsReadOnlyAdapter],
    caller_role: AgentRole,
) -> tuple[FunctionTool, ...]:
    return tuple(
        build_materials_adk_tool(adapter, caller_role)
        for tool_name, adapter in adapters.items()
        if caller_role in MATERIALS_TOOL_ROLE_ALLOWLIST[tool_name]
    )
