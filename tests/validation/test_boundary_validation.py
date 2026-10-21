from datetime import UTC, datetime

from aog_recovery.contracts.agent import AgentResultStatus, AgentRole
from aog_recovery.validation.boundaries import validate_agent_result, validate_case


def valid_case_payload() -> dict[str, object]:
    return {
        "case_id": "case-001",
        "aircraft_id": "N123AB",
        "event_type": "in_flight_defect",
        "defect_summary": "Synthetic defect",
        "location": "MEM",
        "event_at": datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        "created_at": datetime(2026, 10, 21, 12, 5, tzinfo=UTC),
        "schema_version": "1.0",
        "trace_context": {"trace_id": "trace-001", "correlation_id": "corr-001"},
    }


def valid_agent_result_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "agent_role": AgentRole.MAINTENANCE,
        "status": AgentResultStatus.PARTIAL,
        "summary": "Synthetic partial result",
        "confidence": 0.6,
        "assumptions": (),
        "evidence_references": ("ev-001",),
        "role_payload": {"finding": "unknown"},
    }


def test_case_validation_is_reproducible_and_reports_fields() -> None:
    invalid_payload = valid_case_payload()
    invalid_payload["schema_version"] = "9.0"
    invalid_payload["unexpected"] = "not allowed"

    first = validate_case(invalid_payload)
    second = validate_case(invalid_payload)

    assert first == second
    assert not first.is_valid
    assert {finding.field_path for finding in first.findings} == {
        "schema_version",
        "unexpected",
    }


def test_case_validation_accepts_supported_complete_intake() -> None:
    report = validate_case(valid_case_payload())

    assert report.is_valid
    assert report.findings == ()


def test_agent_result_validation_rejects_missing_evidence_reference() -> None:
    report = validate_agent_result(valid_agent_result_payload(), available_evidence_ids=())

    assert not report.is_valid
    assert report.findings[0].code == "unknown_evidence_reference"
    assert report.findings[0].field_path == "evidence_references[ev-001]"


def test_agent_result_validation_accepts_referenced_evidence() -> None:
    report = validate_agent_result(valid_agent_result_payload(), available_evidence_ids={"ev-001"})

    assert report.is_valid


def test_malformed_and_unsupported_inputs_are_not_coerced() -> None:
    payload = valid_agent_result_payload()
    payload["confidence"] = "0.6"

    report = validate_agent_result(payload, available_evidence_ids={"ev-001"})

    assert not report.is_valid
    assert any(finding.field_path == "confidence" for finding in report.findings)
