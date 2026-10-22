"""Typed, read-only Materials & Logistics source adapters (ARD-MLG-001..009)."""

import json
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


class MaterialsToolReadEnvelope(ContractModel):
    """Primary inventory result plus its optional, separately labeled cache result."""

    schema_version: Literal["1.0"]
    results: tuple[MaterialsToolResult, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def require_correlated_fallback_results(self) -> MaterialsToolReadEnvelope:
        primary = self.results[0]
        if any(
            (item.request_id, item.case_id, item.trace_context)
            != (primary.request_id, primary.case_id, primary.trace_context)
            for item in self.results[1:]
        ):
            raise ValueError("inventory results must match request and case context")
        if len(self.results) == 2 and (
            primary.status is not ToolResultStatus.FAILED
            or self.results[1].status not in {ToolResultStatus.PARTIAL, ToolResultStatus.FAILED}
        ):
            raise ValueError("cache result requires a failed primary and degraded cache read")
        return self


class MaterialsReadOnlyAdapter(Protocol):
    tool_name: MaterialsToolName
    allowed_roles: frozenset[AgentRole]

    def read(
        self,
        request: MaterialsReadRequest,
        caller_role: AgentRole,
    ) -> MaterialsToolResult: ...


def read_inventory_with_cache_fallback(
    source_adapter: MaterialsReadOnlyAdapter,
    cache_adapter: MaterialsReadOnlyAdapter | None,
    request: MaterialsReadRequest,
    caller_role: AgentRole,
) -> tuple[MaterialsToolResult, ...]:
    source_result = source_adapter.read(request, caller_role)
    if (
        request.tool_name is not MaterialsToolName.PART_INVENTORY
        or source_result.error is None
        or source_result.error.category not in {"source_unavailable", "timeout"}
        or cache_adapter is None
        or cache_adapter.tool_name is not MaterialsToolName.PART_INVENTORY
        or caller_role not in cache_adapter.allowed_roles
    ):
        return (source_result,)

    cache_result = cache_adapter.read(request, caller_role)
    if (
        cache_result.request_id != request.request_id
        or cache_result.case_id != request.case_id
        or cache_result.trace_context != request.trace_context
    ):
        return (
            source_result,
            _cache_failure(
                request,
                cache_result.source,
                cache_result.completed_at,
                "cache_contract_mismatch",
                "cached inventory response does not match the request context",
            ),
        )
    if cache_result.status is ToolResultStatus.FAILED:
        return (source_result, cache_result)
    if not cache_result.evidence:
        return (
            source_result,
            _cache_failure(
                request,
                cache_result.source,
                cache_result.completed_at,
                "cache_evidence_unavailable",
                "cached inventory response contains no evidence",
            ),
        )

    cached_result = cache_result.model_copy(
        update={
            "status": ToolResultStatus.PARTIAL,
            "evidence": tuple(
                evidence.model_copy(update={"validity_state": EvidenceValidity.STALE})
                for evidence in cache_result.evidence
            ),
            "warnings": (
                *cache_result.warnings,
                EvidenceWarning(
                    warning_id=f"cached-evidence-{request.request_id}",
                    claim_reference=f"tool-request:{request.request_id}",
                    code="CACHED_EVIDENCE",
                    message="inventory source failed; cached evidence may be stale",
                    source_reference=cache_result.source,
                ),
            ),
            "error": None,
        }
    )
    return source_result, cached_result


def _cache_failure(
    request: MaterialsReadRequest,
    source: str,
    completed_at: datetime,
    category: str,
    message: str,
) -> MaterialsToolResult:
    return MaterialsToolResult(
        schema_version="1.0",
        request_id=request.request_id,
        case_id=request.case_id,
        trace_context=request.trace_context,
        source=source,
        completed_at=completed_at,
        status=ToolResultStatus.FAILED,
        evidence=None,
        warnings=(),
        error=StructuredError(
            schema_version="1.0",
            category=category,
            component="materials-adapter:part_inventory_cache",
            message=message,
            retryable=False,
            case_impact="cached inventory evidence is unavailable",
        ),
    )


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
    *,
    cache_adapter: MaterialsReadOnlyAdapter | None = None,
) -> FunctionTool:
    if caller_role not in adapter.allowed_roles:
        raise PermissionError(f"{caller_role.value} cannot access {adapter.tool_name.value}")
    if cache_adapter is not None and (
        adapter.tool_name is not MaterialsToolName.PART_INVENTORY
        or cache_adapter.tool_name is not MaterialsToolName.PART_INVENTORY
    ):
        raise ValueError("inventory cache fallback is only valid for part inventory")

    def read_source(request: dict[str, object]) -> dict[str, object]:
        """Read one allowlisted Materials source using a validated request."""
        try:
            validated_request = MaterialsReadRequest.model_validate_json(
                json.dumps({**request, "tool_name": adapter.tool_name.value})
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise ValueError("materials source request failed schema validation") from exc
        if cache_adapter is None:
            return adapter.read(validated_request, caller_role).model_dump(mode="json")
        results = read_inventory_with_cache_fallback(
            adapter,
            cache_adapter,
            validated_request,
            caller_role,
        )
        return MaterialsToolReadEnvelope(schema_version="1.0", results=results).model_dump(
            mode="json"
        )

    read_source.__name__ = f"read_{adapter.tool_name.value}"
    read_source.__doc__ = (
        f"Read synthetic {adapter.tool_name.value.replace('_', ' ')} evidence using a validated "
        "read request. Valid inputs include request, case, trace, tool, and part/station fields. "
        "Returns one Materials result, or a versioned source/cache envelope when a cache adapter "
        "is configured. Cache is queried only for unavailable or timed-out inventory; malformed "
        "and unauthorized reads are not retried. Failed reads remain structured results."
    )
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
    *,
    inventory_cache_adapter: MaterialsReadOnlyAdapter | None = None,
) -> tuple[FunctionTool, ...]:
    return tuple(
        build_materials_adk_tool(
            adapter,
            caller_role,
            cache_adapter=(
                inventory_cache_adapter if tool_name is MaterialsToolName.PART_INVENTORY else None
            ),
        )
        for tool_name, adapter in adapters.items()
        if caller_role in MATERIALS_TOOL_ROLE_ALLOWLIST[tool_name]
    )
