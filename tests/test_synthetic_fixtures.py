import json
from collections.abc import Callable

from aog_recovery.adapters.local import LocalReadOnlyAdapter, MockResponseMode
from aog_recovery.contracts.agent import AgentResult, AgentRole
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import Evidence, EvidenceConflict
from aog_recovery.contracts.governance import HumanDecisionRecord
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult, ToolResultStatus


def test_shared_synthetic_fixtures_are_stable_and_contain_no_secrets(
    valid_case_payload: dict[str, object],
    valid_case: AogCase,
    current_evidence: object,
    stale_evidence: object,
    partial_evidence: object,
    conflicting_evidence: tuple[Evidence, Evidence, EvidenceConflict],
    agent_result_payload: dict[str, object],
    agent_result: AgentResult,
    invalid_case_payload: dict[str, object],
    successful_tool_result: ToolResult,
    failed_tool_result: ToolResult,
    human_decision_record: HumanDecisionRecord,
    trace_context: object,
    tool_request_factory: Callable[[ToolName], ToolRequest],
    local_adapter_factory: Callable[[MockResponseMode], LocalReadOnlyAdapter],
) -> None:
    tool_request = tool_request_factory(ToolName.MAINTENANCE_RECORDS)
    local_adapter = local_adapter_factory(MockResponseMode.SUCCESS)
    adapter_result = local_adapter.read(tool_request, AgentRole.MAINTENANCE)
    repeated_result = local_adapter.read(tool_request, AgentRole.MAINTENANCE)
    serialized = json.dumps(
        {
            "case": valid_case.model_dump(mode="json"),
            "current_evidence": current_evidence.model_dump(mode="json"),
            "stale_evidence": stale_evidence.model_dump(mode="json"),
            "partial_evidence": partial_evidence.model_dump(mode="json"),
            "conflicting_evidence": [item.model_dump(mode="json") for item in conflicting_evidence],
            "agent_result": agent_result_payload,
            "typed_agent_result": agent_result.model_dump(mode="json"),
            "invalid_case": invalid_case_payload,
            "successful_tool_result": successful_tool_result.model_dump(mode="json"),
            "failed_tool_result": failed_tool_result.model_dump(mode="json"),
            "human_decision": human_decision_record.model_dump(mode="json"),
            "trace_context": trace_context.model_dump(mode="json"),
            "tool_request": tool_request.model_dump(mode="json"),
            "adapter_result": adapter_result.model_dump(mode="json"),
        },
        sort_keys=True,
        default=str,
    )

    assert valid_case_payload["case_id"] == "case-synthetic-001"
    assert "case_id" not in invalid_case_payload
    assert adapter_result == repeated_result
    assert adapter_result.status is ToolResultStatus.SUCCESS
    assert serialized == json.dumps(json.loads(serialized), sort_keys=True)
    assert "synthetic" in serialized.casefold()
    assert "GOOGLE_API_KEY" not in serialized
    assert "provider_api_key" not in serialized
