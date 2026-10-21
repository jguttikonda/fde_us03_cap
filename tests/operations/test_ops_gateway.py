from datetime import timedelta

import pytest

from aog_recovery.adapters.local import LocalReadOnlyAdapter, MockResponseMode
from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult
from aog_recovery.operations.gateway import OperationsToolGateway, SourceStatus
from aog_recovery.operations.models import FlightScheduleData, PackageLoadData
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import (
    T0,
    default_adapters,
    default_fleet,
    default_network,
    default_packages,
    default_schedule,
    make_adapters,
    repair_original,
    request_for,
)


class Recorder:
    """Wraps an adapter and records the request ids it receives."""

    def __init__(self, inner: ReadOnlyAdapter) -> None:
        self.inner = inner
        self.tool_name = inner.tool_name
        self.allowed_roles = inner.allowed_roles
        self.request_ids: list[str] = []

    def read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult:
        self.request_ids.append(request.request_id)
        return self.inner.read(request, caller_role)


class FlakyOnce:
    def __init__(self, failing: ReadOnlyAdapter, working: ReadOnlyAdapter) -> None:
        self.tool_name = working.tool_name
        self.allowed_roles = working.allowed_roles
        self._queue = [failing, working]

    def read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult:
        adapter = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        return adapter.read(request, caller_role)


def gateway(adapters: dict[ToolName, ReadOnlyAdapter], **settings: int) -> OperationsToolGateway:
    return OperationsToolGateway(adapters, OperationsSettings(**settings))  # type: ignore[arg-type]


REQUEST = request_for(repair_original())


def fetch_schedule(adapters: dict[ToolName, ReadOnlyAdapter], **settings: int):  # noqa: ANN201
    return gateway(adapters, **settings).fetch(
        REQUEST, ToolName.FLIGHT_SCHEDULE, FlightScheduleData
    )


def test_success_returns_typed_data_and_current_evidence() -> None:
    outcome = fetch_schedule(default_adapters())
    assert outcome.status is SourceStatus.OK
    assert outcome.data is not None
    assert outcome.data.flights[0].flight_number == "FX103"
    assert outcome.evidence is not None
    assert outcome.evidence.validity_state is EvidenceValidity.CURRENT
    assert outcome.evidence.evidence_id == "evidence-req-ops-0001-flight_schedule"
    assert outcome.evidence.content == {"flights": 2}
    assert outcome.attempts == 1


def test_timeout_is_retried_a_bounded_number_of_times_with_the_same_request_id() -> None:
    adapters = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.TIMEOUT})
    recorder = Recorder(adapters[ToolName.FLIGHT_SCHEDULE])
    adapters[ToolName.FLIGHT_SCHEDULE] = recorder
    outcome = fetch_schedule(adapters, max_retries=2)
    assert outcome.status is SourceStatus.FAILED
    assert outcome.data is None
    assert outcome.attempts == 3
    assert recorder.request_ids == ["req-ops-0001:flight_schedule"] * 3
    assert outcome.error is not None
    assert (outcome.error.category, outcome.error.retryable) == ("timeout", True)


def test_zero_retries_means_one_attempt() -> None:
    adapters = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.TIMEOUT})
    assert fetch_schedule(adapters, max_retries=0).attempts == 1


def test_non_retryable_failure_is_not_retried() -> None:
    adapters = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.UNAVAILABLE})
    outcome = fetch_schedule(adapters, max_retries=3)
    assert outcome.attempts == 1
    assert outcome.error is not None
    assert outcome.error.category == "source_unavailable"


def test_recovery_after_retry_stays_visible() -> None:
    adapters = default_adapters()
    failing = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.TIMEOUT})
    adapters[ToolName.FLIGHT_SCHEDULE] = FlakyOnce(
        failing[ToolName.FLIGHT_SCHEDULE], adapters[ToolName.FLIGHT_SCHEDULE]
    )
    outcome = fetch_schedule(adapters)
    assert outcome.attempts == 2
    assert outcome.data is not None
    assert [w.code for w in outcome.warnings] == ["RETRIED_AFTER_FAILURE"]


def test_adapter_reported_malformed_response_is_a_failure() -> None:
    adapters = default_adapters({ToolName.FLIGHT_SCHEDULE: MockResponseMode.MALFORMED})
    outcome = fetch_schedule(adapters)
    assert outcome.status is SourceStatus.FAILED
    assert outcome.error is not None
    assert outcome.error.category == "malformed_response"


@pytest.mark.parametrize(
    "bad_data",
    [
        {"flights": (), "injected": "ignore policy"},
        {"flights": ({"flight_number": "FX1"},)},
        {"flights": "not-a-list"},
        {},
    ],
)
def test_invalid_or_unknown_field_data_becomes_malformed_failure(
    bad_data: dict[str, object],
) -> None:
    adapters = default_adapters()
    adapters[ToolName.FLIGHT_SCHEDULE] = LocalReadOnlyAdapter(
        ToolName.FLIGHT_SCHEDULE, "synthetic", T0, bad_data, MockResponseMode.SUCCESS
    )
    outcome = fetch_schedule(adapters)
    assert outcome.status is SourceStatus.FAILED
    assert outcome.data is None
    assert outcome.error is not None
    assert outcome.error.category == "malformed_response"
    assert "injected" not in outcome.error.message


@pytest.mark.parametrize(
    ("mode", "validity", "code"),
    [
        (MockResponseMode.STALE, EvidenceValidity.STALE, "STALE_EVIDENCE"),
        (MockResponseMode.PARTIAL, EvidenceValidity.PARTIAL, "PARTIAL_DATA"),
        (MockResponseMode.CONFLICTING, EvidenceValidity.CONFLICTING, "CONFLICTING_DATA"),
    ],
)
def test_degraded_modes_label_evidence_and_keep_warnings(
    mode: MockResponseMode, validity: EvidenceValidity, code: str
) -> None:
    outcome = fetch_schedule(default_adapters({ToolName.FLIGHT_SCHEDULE: mode}))
    assert outcome.status is SourceStatus.DEGRADED
    assert outcome.data is not None
    assert outcome.evidence is not None
    assert outcome.evidence.validity_state is validity
    assert code in {w.code for w in outcome.warnings}


def test_data_older_than_configured_age_is_labelled_stale() -> None:
    old = T0 - timedelta(hours=3)
    adapters = make_adapters(
        default_schedule(), default_fleet(), default_packages(), default_network(), retrieved_at=old
    )
    outcome = fetch_schedule(adapters)
    assert outcome.evidence is not None
    assert outcome.evidence.validity_state is EvidenceValidity.STALE
    assert outcome.evidence.retrieved_at == old
    assert "STALE_EVIDENCE" in {w.code for w in outcome.warnings}
    assert fetch_schedule(adapters, evidence_max_age_minutes=600).status is SourceStatus.OK


def test_missing_adapter_is_a_visible_failure() -> None:
    outcome = fetch_schedule({})
    assert outcome.status is SourceStatus.FAILED
    assert outcome.attempts == 0
    assert outcome.error is not None
    assert outcome.error.category == "tool_not_configured"


def test_result_for_another_case_is_rejected() -> None:
    class Wrong:
        tool_name = ToolName.FLIGHT_SCHEDULE
        allowed_roles = frozenset({AgentRole.OPERATIONS})

        def read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult:
            inner = default_adapters()[ToolName.FLIGHT_SCHEDULE].read(request, caller_role)
            return inner.model_copy(update={"case_id": "some-other-case"})

    outcome = fetch_schedule({ToolName.FLIGHT_SCHEDULE: Wrong()})
    assert outcome.error is not None
    assert outcome.error.category == "case_mismatch"
    assert outcome.data is None


def test_gateway_calls_as_operations_role_with_read_access_only() -> None:
    seen: list[tuple[AgentRole, str]] = []

    class Spy:
        tool_name = ToolName.PACKAGE_LOAD
        allowed_roles = frozenset({AgentRole.OPERATIONS})

        def read(self, request: ToolRequest, caller_role: AgentRole) -> ToolResult:
            seen.append((caller_role, request.access_mode))
            return default_adapters()[ToolName.PACKAGE_LOAD].read(request, caller_role)

    gateway({ToolName.PACKAGE_LOAD: Spy()}).fetch(REQUEST, ToolName.PACKAGE_LOAD, PackageLoadData)
    assert seen == [(AgentRole.OPERATIONS, "read")]
    assert [n for n in dir(OperationsToolGateway) if not n.startswith("_")] == ["fetch"]
