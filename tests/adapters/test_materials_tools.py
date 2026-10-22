import json
from datetime import UTC, datetime, timedelta

import pytest
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp.client.stdio import StdioServerParameters
from pydantic import ValidationError

from aog_recovery.adapters.local import MockResponseMode
from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.materials_logistics.tools import (
    MATERIALS_TOOL_ROLE_ALLOWLIST,
    LocalMaterialsReadOnlyAdapter,
    MaterialsReadRequest,
    MaterialsToolName,
    MaterialsToolReadEnvelope,
    build_materials_adk_tool,
    build_materials_adk_tools,
    build_materials_mcp_toolset,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def evidence() -> Evidence:
    return Evidence(
        evidence_id="inventory-evidence-001",
        source="synthetic-materials-fixture",
        retrieved_at=TIMESTAMP,
        validity_state=EvidenceValidity.CURRENT,
        claim_reference="inventory-claim-001",
        content={"available_quantity": 4},
    )


def adapter(
    tool_name: MaterialsToolName = MaterialsToolName.PART_INVENTORY,
    response_mode: MockResponseMode = MockResponseMode.SUCCESS,
) -> LocalMaterialsReadOnlyAdapter:
    return LocalMaterialsReadOnlyAdapter(
        tool_name=tool_name,
        source="synthetic-materials-fixture",
        fixture_timestamp=TIMESTAMP,
        fixture_evidence=(evidence(),),
        response_mode=response_mode,
    )


def request(
    tool_name: MaterialsToolName = MaterialsToolName.PART_INVENTORY,
) -> MaterialsReadRequest:
    return MaterialsReadRequest(
        schema_version="1.0",
        request_id="materials-req-001",
        case_id="case-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
        tool_name=tool_name,
        requested_at=TIMESTAMP,
        aircraft_id="TEST-AIRCRAFT-001",
        part_number="P-110",
        station="TEST-STATION",
        quantity=1,
        access_mode="read",
    )


def test_each_materials_source_has_a_typed_read_request_and_role_allowlist() -> None:
    for tool_name, allowed_roles in MATERIALS_TOOL_ROLE_ALLOWLIST.items():
        source_adapter = adapter(tool_name)
        validated_request = request(tool_name)

        assert source_adapter.tool_name is tool_name
        assert source_adapter.allowed_roles == allowed_roles
        assert validated_request.tool_name is tool_name
        assert validated_request.access_mode == "read"
        assert all(
            not hasattr(source_adapter, action)
            for action in ("write", "purchase", "reserve", "transfer", "ship")
        )


def test_source_request_rejects_missing_required_fields_and_write_access() -> None:
    payload = request().model_dump(mode="python")
    payload["part_number"] = None

    with pytest.raises(ValidationError, match="part_number"):
        MaterialsReadRequest.model_validate(payload)

    payload = request().model_dump(mode="python")
    payload["access_mode"] = "write"

    with pytest.raises(ValidationError):
        MaterialsReadRequest.model_validate(payload)


def test_local_materials_adapter_returns_deterministic_source_evidence() -> None:
    local_adapter = adapter()

    first = local_adapter.read(request(), AgentRole.MATERIALS_LOGISTICS)
    second = local_adapter.read(request(), AgentRole.MATERIALS_LOGISTICS)

    assert first == second
    assert first.status is ToolResultStatus.SUCCESS
    assert first.evidence == (evidence(),)
    assert first.request_id == "materials-req-001"
    assert first.trace_context.correlation_id == "corr-001"


def test_materials_adapter_rejects_wrong_role_or_source_name() -> None:
    role_rejected = adapter(MaterialsToolName.ALTERNATE_PARTS).read(
        request(MaterialsToolName.ALTERNATE_PARTS),
        AgentRole.MAINTENANCE,
    )
    name_rejected = adapter(MaterialsToolName.SHIPPING).read(
        request(MaterialsToolName.PART_INVENTORY),
        AgentRole.MATERIALS_LOGISTICS,
    )

    assert role_rejected.status is ToolResultStatus.FAILED
    assert role_rejected.error is not None
    assert role_rejected.error.category == "role_not_allowlisted"
    assert name_rejected.status is ToolResultStatus.FAILED
    assert name_rejected.error is not None
    assert name_rejected.error.category == "tool_not_allowlisted"


def test_materials_adapter_failure_is_not_success_shaped() -> None:
    result = adapter(response_mode=MockResponseMode.UNAVAILABLE).read(
        request(), AgentRole.MATERIALS_LOGISTICS
    )

    assert result.status is ToolResultStatus.FAILED
    assert result.evidence is None
    assert result.error is not None
    assert result.error.category == "source_unavailable"


def test_adk_inventory_tool_routes_unavailable_reads_through_cache_fallback() -> None:
    live_adapter = adapter(response_mode=MockResponseMode.UNAVAILABLE)
    cache_adapter = LocalMaterialsReadOnlyAdapter(
        tool_name=MaterialsToolName.PART_INVENTORY,
        source="synthetic-inventory-cache",
        fixture_timestamp=TIMESTAMP,
        fixture_evidence=(
            evidence().model_copy(
                update={
                    "source": "synthetic-inventory-cache",
                    "retrieved_at": TIMESTAMP - timedelta(days=1),
                }
            ),
        ),
    )
    adk_tool = build_materials_adk_tools(
        {MaterialsToolName.PART_INVENTORY: live_adapter},
        AgentRole.MATERIALS_LOGISTICS,
        inventory_cache_adapter=cache_adapter,
    )[0]

    result_payload = adk_tool.func(request().model_dump(mode="json"))
    envelope = MaterialsToolReadEnvelope.model_validate_json(json.dumps(result_payload))

    assert len(envelope.results) == 2
    primary, cached = envelope.results
    assert primary.status is ToolResultStatus.FAILED
    assert primary.error is not None
    assert primary.error.category == "source_unavailable"
    assert cached.status is ToolResultStatus.PARTIAL
    assert cached.evidence is not None
    assert cached.evidence[0].source == "synthetic-inventory-cache"
    assert cached.evidence[0].retrieved_at == TIMESTAMP - timedelta(days=1)
    assert cached.evidence[0].validity_state is EvidenceValidity.STALE
    assert cached.warnings[0].code == "CACHED_EVIDENCE"
    assert all(item.trace_context == request().trace_context for item in envelope.results)


def test_adk_inventory_tool_does_not_fallback_on_malformed_response() -> None:
    adk_tool = build_materials_adk_tool(
        adapter(response_mode=MockResponseMode.MALFORMED),
        AgentRole.MATERIALS_LOGISTICS,
        cache_adapter=adapter(),
    )

    result_payload = adk_tool.func(request().model_dump(mode="json"))
    envelope = MaterialsToolReadEnvelope.model_validate_json(json.dumps(result_payload))

    assert len(envelope.results) == 1
    result = envelope.results[0]
    assert result.status is ToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.category == "malformed_response"


def test_cache_envelope_rejects_success_shaped_fallback() -> None:
    primary = adapter(response_mode=MockResponseMode.UNAVAILABLE).read(
        request(),
        AgentRole.MATERIALS_LOGISTICS,
    )
    cache_success = adapter().read(request(), AgentRole.MATERIALS_LOGISTICS)

    with pytest.raises(ValidationError, match="degraded cache read"):
        MaterialsToolReadEnvelope(schema_version="1.0", results=(primary, cache_success))


def test_adk_and_mcp_tools_are_limited_to_the_callers_allowlist() -> None:
    adapters = {tool_name: adapter(tool_name) for tool_name in MaterialsToolName}
    adk_tools = build_materials_adk_tools(adapters, AgentRole.MATERIALS_LOGISTICS)
    expected_names = [
        name.value
        for name, allowed_roles in MATERIALS_TOOL_ROLE_ALLOWLIST.items()
        if AgentRole.MATERIALS_LOGISTICS in allowed_roles
    ]
    mcp_toolset = build_materials_mcp_toolset(
        StdioConnectionParams(
            server_params=StdioServerParameters(command="synthetic-not-launched")
        ),
        AgentRole.MATERIALS_LOGISTICS,
    )

    assert all(isinstance(tool, FunctionTool) for tool in adk_tools)
    assert {tool.name for tool in adk_tools} == {
        f"read_{name.value}"
        for name, allowed_roles in MATERIALS_TOOL_ROLE_ALLOWLIST.items()
        if AgentRole.MATERIALS_LOGISTICS in allowed_roles
    }
    assert isinstance(mcp_toolset, McpToolset)
    assert mcp_toolset.tool_filter == [f"read_{name}" for name in expected_names]
