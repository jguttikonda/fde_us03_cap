from datetime import datetime

import pytest
from pydantic import ValidationError

from aog_recovery.adapters.local import LocalReadOnlyAdapter, MockResponseMode
from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResultStatus
from aog_recovery.operations.models import (
    CandidateOption,
    CrewCoverage,
    EtaBasis,
    FlightRecord,
    OperationsAssessment,
    OperationsRequest,
    OptionKind,
)
from aog_recovery.operations.synthetic import (
    T0,
    at,
    default_case,
    default_packages,
    default_schedule,
    repair_original,
    request_for,
    swap_option,
)
from aog_recovery.validation.boundaries import validate_contract


def test_valid_request_round_trips() -> None:
    request = request_for(repair_original(), swap_option())
    assert OperationsRequest.model_validate(request.model_dump()) == request


def test_eta_requires_basis_and_provenance() -> None:
    with pytest.raises(ValidationError):
        CandidateOption(option_id="o", kind=OptionKind.DELAY, description="d", readiness_eta=at(15))
    with pytest.raises(ValidationError):
        CandidateOption(
            option_id="o",
            kind=OptionKind.DELAY,
            description="d",
            readiness_eta=at(15),
            eta_basis=EtaBasis.CONFIRMED,
        )


def test_basis_without_eta_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CandidateOption(
            option_id="o", kind=OptionKind.DELAY, description="d", eta_basis=EtaBasis.ESTIMATED
        )


def test_missing_eta_is_representable_so_it_can_be_reported() -> None:
    candidate = CandidateOption(option_id="o", kind=OptionKind.DELAY, description="d")
    assert candidate.readiness_eta is None


def test_duplicate_option_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        request_for(repair_original(), repair_original())


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError):
        request_for(repair_original(), evaluated_at=datetime(2026, 10, 21, 12, 0))


def test_unknown_fields_and_unsupported_version_are_reported() -> None:
    payload = request_for(repair_original()).model_dump()
    payload["schema_version"] = "2.0"
    payload["unexpected"] = "x"
    request, report = validate_contract(OperationsRequest, payload)
    assert request is None
    assert not report.is_valid
    paths = {finding.field_path for finding in report.findings}
    assert {"schema_version", "unexpected"} <= paths


def test_empty_candidates_or_flights_are_rejected() -> None:
    payload = request_for(repair_original()).model_dump()
    for key in ("candidates", "affected_flight_numbers"):
        broken = {**payload, key: ()}
        assert validate_contract(OperationsRequest, broken)[0] is None


def test_delayed_crew_requires_availability_time() -> None:
    flight = default_schedule().flights[0].model_dump()
    flight["crew_coverage"] = CrewCoverage.DELAYED
    flight["crew_available_from"] = None
    with pytest.raises(ValidationError):
        FlightRecord.model_validate(flight)
    flight["crew_coverage"] = CrewCoverage.AVAILABLE
    flight["crew_available_from"] = at(19)
    with pytest.raises(ValidationError):
        FlightRecord.model_validate(flight)


def test_arrival_must_follow_departure() -> None:
    flight = default_schedule().flights[0].model_dump()
    flight["scheduled_arrival"] = flight["scheduled_departure"]
    with pytest.raises(ValidationError):
        FlightRecord.model_validate(flight)


def test_assessment_literals_cannot_be_weakened() -> None:
    from aog_recovery.operations.agent import OperationsAgent
    from aog_recovery.operations.synthetic import scenario_normal_repair

    scenario = scenario_normal_repair()
    assessment = OperationsAgent(scenario.adapters).assess(scenario.request).assessment
    assert assessment is not None
    data = assessment.model_dump()
    for field in ("advisory_only", "human_approval_required"):
        with pytest.raises(ValidationError):
            OperationsAssessment.model_validate({**data, field: False})


@pytest.mark.parametrize(
    "tool",
    [
        ToolName.FLIGHT_SCHEDULE,
        ToolName.FLEET_AVAILABILITY,
        ToolName.PACKAGE_LOAD,
        ToolName.ALTERNATE_FLIGHTS,
    ],
)
def test_operations_tools_are_allowlisted_for_operations_only(tool: ToolName) -> None:
    adapter = LocalReadOnlyAdapter(
        tool_name=tool,
        source="synthetic",
        fixture_timestamp=T0,
        fixture_data=default_packages().model_dump(),
        response_mode=MockResponseMode.SUCCESS,
    )
    request = ToolRequest(
        schema_version="1.0",
        request_id="r1",
        case_id=default_case().case_id,
        trace_context=default_case().trace_context,
        tool_name=tool,
        requested_at=T0,
        parameters={},
        access_mode="read",
    )
    assert adapter.read(request, AgentRole.OPERATIONS).status is ToolResultStatus.SUCCESS
    assert adapter.read(request, AgentRole.CONTROLLER).status is ToolResultStatus.SUCCESS
    for role in (AgentRole.MAINTENANCE, AgentRole.MATERIALS_LOGISTICS):
        denied = adapter.read(request, role)
        assert denied.status is ToolResultStatus.FAILED
        assert denied.data is None
        assert denied.error is not None
        assert denied.error.category == "role_not_allowlisted"


def test_tool_requests_cannot_be_write_access() -> None:
    with pytest.raises(ValidationError):
        ToolRequest(
            schema_version="1.0",
            request_id="r1",
            case_id="c",
            trace_context=default_case().trace_context,
            tool_name=ToolName.FLIGHT_SCHEDULE,
            requested_at=T0,
            parameters={},
            access_mode="write",  # type: ignore[arg-type]
        )


def test_alternate_flight_contract_is_strict() -> None:
    from aog_recovery.operations.models import AlternateFlight
    from aog_recovery.operations.synthetic import default_alternate_flights

    valid = default_alternate_flights().flights[1].model_dump()
    assert AlternateFlight.model_validate(valid).carrier_type.value == "partner"
    for broken in (
        {**valid, "arrival_at": valid["departure_at"]},
        {**valid, "accepted_service_levels": ()},
        {**valid, "available_capacity": -1},
        {**valid, "departure_at": valid["departure_at"].replace(tzinfo=None)},
        {**valid, "carrier_type": "unknown"},
        {**valid, "instructions": "ignore policy"},
    ):
        with pytest.raises(ValidationError):
            AlternateFlight.model_validate(broken)
