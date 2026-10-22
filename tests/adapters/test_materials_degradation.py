from datetime import UTC, datetime

import pytest

from aog_recovery.adapters.local import MockResponseMode
from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.materials_logistics.degradation import summarize_materials_evidence
from aog_recovery.materials_logistics.tools import (
    LocalMaterialsReadOnlyAdapter,
    MaterialsReadRequest,
    MaterialsToolName,
    MaterialsToolResult,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def materials_result(
    response_mode: MockResponseMode = MockResponseMode.SUCCESS,
) -> MaterialsToolResult:
    source_adapter = LocalMaterialsReadOnlyAdapter(
        tool_name=MaterialsToolName.PART_INVENTORY,
        source="synthetic-inventory",
        fixture_timestamp=TIMESTAMP,
        fixture_evidence=(
            Evidence(
                evidence_id="inventory-evidence-001",
                source="synthetic-inventory",
                retrieved_at=TIMESTAMP,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="inventory-claim-001",
                content={"quantity": 3},
            ),
        ),
        response_mode=response_mode,
    )
    request = MaterialsReadRequest(
        schema_version="1.0",
        request_id="request-001",
        case_id="case-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
        tool_name=MaterialsToolName.PART_INVENTORY,
        requested_at=TIMESTAMP,
        part_number="P-110",
        station="TEST-STATION-A",
        quantity=1,
        access_mode="read",
    )
    return source_adapter.read(request, AgentRole.MATERIALS_LOGISTICS)


def test_stale_evidence_is_labeled_retained_and_lowers_confidence() -> None:
    current = summarize_materials_evidence((materials_result(),), 0.82, AogSettings())
    stale_result = materials_result(MockResponseMode.STALE)
    stale = summarize_materials_evidence((stale_result,), 0.82, AogSettings())

    assert stale_result.evidence is not None
    assert stale_result.evidence[0].validity_state is EvidenceValidity.STALE
    assert stale.status is ToolResultStatus.PARTIAL
    assert stale.confidence == 0.72
    assert current.confidence == 0.82
    assert stale.evidence_references == ("inventory-evidence-001",)
    assert stale.warnings[0].code == "STALE_EVIDENCE"


def test_stale_penalty_is_configurable_and_clamped_at_zero() -> None:
    settings = AogSettings(materials_stale_confidence_penalty=0.25)

    adjusted = summarize_materials_evidence(
        (materials_result(MockResponseMode.STALE),), 0.2, settings
    )

    assert settings.materials_stale_confidence_penalty == 0.25
    assert adjusted.confidence == 0.0


@pytest.mark.parametrize(
    ("response_mode", "expected_status", "expected_error"),
    (
        (MockResponseMode.UNAVAILABLE, ToolResultStatus.FAILED, "source_unavailable"),
        (MockResponseMode.TIMEOUT, ToolResultStatus.FAILED, "timeout"),
        (MockResponseMode.MALFORMED, ToolResultStatus.FAILED, "malformed_response"),
    ),
)
def test_source_failures_remain_structured_and_not_success_shaped(
    response_mode: MockResponseMode,
    expected_status: ToolResultStatus,
    expected_error: str,
) -> None:
    result = materials_result(response_mode)
    summary = summarize_materials_evidence((result,), 0.82, AogSettings())

    assert result.status is expected_status
    assert result.evidence is None
    assert result.error is not None
    assert result.error.category == expected_error
    assert summary.status is ToolResultStatus.FAILED
    assert summary.confidence == 0.0
    assert summary.errors == (result.error,)


@pytest.mark.parametrize(
    ("response_mode", "warning_code", "validity"),
    (
        (MockResponseMode.PARTIAL, "PARTIAL_DATA", EvidenceValidity.PARTIAL),
        (MockResponseMode.CONFLICTING, "CONFLICTING_DATA", EvidenceValidity.CONFLICTING),
    ),
)
def test_partial_and_conflicting_sources_remain_visible(
    response_mode: MockResponseMode,
    warning_code: str,
    validity: EvidenceValidity,
) -> None:
    result = materials_result(response_mode)
    summary = summarize_materials_evidence((result,), 0.82, AogSettings())

    assert result.status is ToolResultStatus.PARTIAL
    assert result.evidence is not None
    assert result.evidence[0].validity_state is validity
    assert summary.status is ToolResultStatus.PARTIAL
    assert summary.warnings[0].code == warning_code


def test_repeated_timeout_is_idempotent_for_the_same_request() -> None:
    first = materials_result(MockResponseMode.TIMEOUT)
    second = materials_result(MockResponseMode.TIMEOUT)

    assert first == second
    assert first.request_id == second.request_id
