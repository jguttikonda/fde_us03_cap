from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from aog_recovery.adapters.local import LocalReadOnlyAdapter, MockResponseMode
from aog_recovery.contracts.agent import (
    AgentResult,
    AgentResultStatus,
    AgentRole,
    StructuredError,
)
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import (
    Evidence,
    EvidenceConflict,
    EvidenceValidity,
)
from aog_recovery.contracts.governance import (
    HumanDecisionRecord,
    HumanDecisionType,
    ReviewerRole,
)
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult, ToolResultStatus

SYNTHETIC_TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


@pytest.fixture
def trace_context() -> TraceContext:
    return TraceContext(trace_id="trace-synthetic-001", correlation_id="corr-synthetic-001")


@pytest.fixture
def valid_case_payload(trace_context: TraceContext) -> dict[str, object]:
    return {
        "case_id": "case-synthetic-001",
        "aircraft_id": "TEST-AIRCRAFT-001",
        "event_type": "synthetic_defect",
        "defect_summary": "Synthetic test condition",
        "location": "TEST-STATION-001",
        "event_at": SYNTHETIC_TIMESTAMP,
        "created_at": SYNTHETIC_TIMESTAMP,
        "schema_version": "1.0",
        "trace_context": trace_context.model_dump(),
    }


@pytest.fixture
def invalid_case_payload(valid_case_payload: dict[str, object]) -> dict[str, object]:
    invalid_payload = valid_case_payload.copy()
    del invalid_payload["case_id"]
    return invalid_payload


@pytest.fixture
def valid_case(valid_case_payload: dict[str, object]) -> AogCase:
    return AogCase.model_validate(valid_case_payload)


@pytest.fixture
def current_evidence() -> Evidence:
    return Evidence(
        evidence_id="evidence-synthetic-current",
        source="synthetic-fixture-source",
        retrieved_at=SYNTHETIC_TIMESTAMP,
        validity_state=EvidenceValidity.CURRENT,
        claim_reference="claim-synthetic-current",
        content={"state": "synthetic"},
    )


@pytest.fixture
def stale_evidence() -> Evidence:
    return Evidence(
        evidence_id="evidence-synthetic-stale",
        source="synthetic-fixture-source",
        retrieved_at=SYNTHETIC_TIMESTAMP,
        validity_state=EvidenceValidity.STALE,
        claim_reference="claim-synthetic-stale",
        content={"state": "synthetic-stale"},
    )


@pytest.fixture
def partial_evidence() -> Evidence:
    return Evidence(
        evidence_id="evidence-synthetic-partial",
        source="synthetic-fixture-source",
        retrieved_at=SYNTHETIC_TIMESTAMP,
        validity_state=EvidenceValidity.PARTIAL,
        claim_reference="claim-synthetic-partial",
        content={"state": "synthetic-partial"},
    )


@pytest.fixture
def conflicting_evidence() -> tuple[Evidence, Evidence, EvidenceConflict]:
    first = Evidence(
        evidence_id="evidence-synthetic-conflict-a",
        source="synthetic-source-a",
        retrieved_at=SYNTHETIC_TIMESTAMP,
        validity_state=EvidenceValidity.CONFLICTING,
        claim_reference="claim-synthetic-conflict",
        content={"finding": "synthetic-a"},
    )
    second = Evidence(
        evidence_id="evidence-synthetic-conflict-b",
        source="synthetic-source-b",
        retrieved_at=SYNTHETIC_TIMESTAMP,
        validity_state=EvidenceValidity.CONFLICTING,
        claim_reference="claim-synthetic-conflict",
        content={"finding": "synthetic-b"},
    )
    conflict = EvidenceConflict(
        conflict_id="conflict-synthetic-001",
        claim_reference="claim-synthetic-conflict",
        evidence_references=(first.evidence_id, second.evidence_id),
        description="Synthetic sources disagree",
    )
    return first, second, conflict


@pytest.fixture
def agent_result_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "agent_role": AgentRole.MAINTENANCE,
        "status": AgentResultStatus.PARTIAL,
        "summary": "Synthetic result",
        "confidence": 0.69,
        "assumptions": (),
        "evidence_references": ("evidence-synthetic-current",),
        "role_payload": {"finding": "synthetic"},
    }


@pytest.fixture
def agent_result(agent_result_payload: dict[str, object]) -> AgentResult:
    return AgentResult.model_validate(agent_result_payload)


@pytest.fixture
def tool_request_factory(
    trace_context: TraceContext,
) -> Callable[[ToolName], ToolRequest]:
    def make_request(tool_name: ToolName = ToolName.MAINTENANCE_RECORDS) -> ToolRequest:
        return ToolRequest(
            schema_version="1.0",
            request_id="request-synthetic-001",
            case_id="case-synthetic-001",
            trace_context=trace_context,
            tool_name=tool_name,
            requested_at=SYNTHETIC_TIMESTAMP,
            parameters={"fixture_id": "synthetic-input-001"},
            access_mode="read",
        )

    return make_request


@pytest.fixture
def successful_tool_result(trace_context: TraceContext) -> ToolResult:
    return ToolResult(
        schema_version="1.0",
        request_id="request-synthetic-001",
        case_id="case-synthetic-001",
        trace_context=trace_context,
        source="synthetic-fixture-source",
        completed_at=SYNTHETIC_TIMESTAMP,
        status=ToolResultStatus.SUCCESS,
        warnings=(),
        data={"fixture_id": "synthetic-result-001"},
        error=None,
    )


@pytest.fixture
def failed_tool_result(trace_context: TraceContext) -> ToolResult:
    return ToolResult(
        schema_version="1.0",
        request_id="request-synthetic-failed-001",
        case_id="case-synthetic-001",
        trace_context=trace_context,
        source="synthetic-fixture-source",
        completed_at=SYNTHETIC_TIMESTAMP,
        status=ToolResultStatus.FAILED,
        warnings=(),
        data=None,
        error=StructuredError(
            schema_version="1.0",
            category="synthetic_unavailable",
            component="synthetic-fixture-adapter",
            message="Synthetic fixture source is unavailable",
            retryable=False,
            case_impact="synthetic evidence is unavailable",
        ),
    )


@pytest.fixture
def human_decision_record() -> HumanDecisionRecord:
    return HumanDecisionRecord(
        schema_version="1.0",
        decision_id="decision-synthetic-001",
        case_id="case-synthetic-001",
        decision=HumanDecisionType.APPROVE,
        selected_action="synthetic-repair-action",
        selected_option_id="option-synthetic-001",
        reviewer_id="reviewer-synthetic-001",
        reviewer_role=ReviewerRole.OPS_LEAD,
        decided_at=SYNTHETIC_TIMESTAMP,
        rationale="Synthetic approval fixture",
        recommendation_version="recommendation-synthetic-v1",
    )


@pytest.fixture
def local_adapter_factory() -> Callable[[MockResponseMode], LocalReadOnlyAdapter]:
    def make_adapter(
        response_mode: MockResponseMode = MockResponseMode.SUCCESS,
    ) -> LocalReadOnlyAdapter:
        return LocalReadOnlyAdapter(
            tool_name=ToolName.MAINTENANCE_RECORDS,
            source="synthetic-fixture-source",
            fixture_timestamp=SYNTHETIC_TIMESTAMP,
            fixture_data={"fixture_id": "synthetic-result-001"},
            response_mode=response_mode,
        )

    return make_adapter
