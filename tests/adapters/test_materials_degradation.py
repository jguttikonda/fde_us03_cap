from datetime import UTC, datetime, timedelta

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
    read_inventory_with_cache_fallback,
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


def inventory_request() -> MaterialsReadRequest:
    return MaterialsReadRequest(
        schema_version="1.0",
        request_id="request-cache-001",
        case_id="case-cache-001",
        trace_context=TraceContext(trace_id="trace-cache-001", correlation_id="corr-cache-001"),
        tool_name=MaterialsToolName.PART_INVENTORY,
        requested_at=TIMESTAMP,
        part_number="P-110",
        station="TEST-STATION-A",
        quantity=1,
        access_mode="read",
    )


def inventory_adapter(
    source: str,
    response_mode: MockResponseMode = MockResponseMode.SUCCESS,
    retrieved_at: datetime = TIMESTAMP,
) -> LocalMaterialsReadOnlyAdapter:
    return LocalMaterialsReadOnlyAdapter(
        tool_name=MaterialsToolName.PART_INVENTORY,
        source=source,
        fixture_timestamp=TIMESTAMP,
        fixture_evidence=(
            Evidence(
                evidence_id=f"{source}-evidence",
                source=source,
                retrieved_at=retrieved_at,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="inventory-claim-cache-001",
                content={"quantity": 3},
            ),
        ),
        response_mode=response_mode,
    )


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


def test_current_inventory_does_not_query_cache() -> None:
    results = read_inventory_with_cache_fallback(
        inventory_adapter("live-inventory"),
        inventory_adapter("inventory-cache"),
        inventory_request(),
        AgentRole.MATERIALS_LOGISTICS,
    )

    assert len(results) == 1
    assert results[0].status is ToolResultStatus.SUCCESS
    assert results[0].source == "live-inventory"


def test_unavailable_inventory_preserves_failure_and_labels_cached_evidence() -> None:
    retrieval_time = TIMESTAMP - timedelta(days=1)
    results = read_inventory_with_cache_fallback(
        inventory_adapter("live-inventory", MockResponseMode.UNAVAILABLE),
        inventory_adapter("inventory-cache", retrieved_at=retrieval_time),
        inventory_request(),
        AgentRole.MATERIALS_LOGISTICS,
    )
    summary = summarize_materials_evidence(results, 0.82, AogSettings())
    source_result, cached_result = results

    assert source_result.status is ToolResultStatus.FAILED
    assert source_result.error is not None
    assert source_result.error.category == "source_unavailable"
    assert cached_result.status is ToolResultStatus.PARTIAL
    assert cached_result.error is None
    assert cached_result.evidence is not None
    assert cached_result.evidence[0].source == "inventory-cache"
    assert cached_result.evidence[0].retrieved_at == retrieval_time
    assert cached_result.evidence[0].validity_state is EvidenceValidity.STALE
    assert cached_result.warnings[0].code == "CACHED_EVIDENCE"
    assert summary.status is ToolResultStatus.PARTIAL
    assert summary.confidence == 0.72
    assert summary.errors == (source_result.error,)
    assert summary.evidence_references == ("inventory-cache-evidence",)


def test_unavailable_inventory_without_cache_remains_failed() -> None:
    results = read_inventory_with_cache_fallback(
        inventory_adapter("live-inventory", MockResponseMode.UNAVAILABLE),
        None,
        inventory_request(),
        AgentRole.MATERIALS_LOGISTICS,
    )

    assert len(results) == 1
    assert results[0].status is ToolResultStatus.FAILED
    assert results[0].error is not None
    assert results[0].error.category == "source_unavailable"


def test_timeout_can_use_cache_while_preserving_timeout_error() -> None:
    results = read_inventory_with_cache_fallback(
        inventory_adapter("live-inventory", MockResponseMode.TIMEOUT),
        inventory_adapter("inventory-cache"),
        inventory_request(),
        AgentRole.MATERIALS_LOGISTICS,
    )

    assert len(results) == 2
    assert results[0].error is not None
    assert results[0].error.category == "timeout"
    assert results[1].status is ToolResultStatus.PARTIAL
    assert results[1].warnings[0].code == "CACHED_EVIDENCE"


def test_malformed_inventory_does_not_use_cache() -> None:
    results = read_inventory_with_cache_fallback(
        inventory_adapter("live-inventory", MockResponseMode.MALFORMED),
        inventory_adapter("inventory-cache"),
        inventory_request(),
        AgentRole.MATERIALS_LOGISTICS,
    )

    assert len(results) == 1
    assert results[0].error is not None
    assert results[0].error.category == "malformed_response"


def test_denied_inventory_role_does_not_use_cache() -> None:
    results = read_inventory_with_cache_fallback(
        inventory_adapter("live-inventory"),
        inventory_adapter("inventory-cache"),
        inventory_request(),
        AgentRole.OPERATIONS,
    )

    assert len(results) == 1
    assert results[0].error is not None
    assert results[0].error.category == "role_not_allowlisted"
