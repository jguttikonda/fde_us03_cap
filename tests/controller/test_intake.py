from aog_recovery.controller.intake import IntakeStatus, validate_controller_intake


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": "req-controller-001",
        "case": {
            "case_id": "AOG-CONTROLLER-001",
            "aircraft_id": "N123AB",
            "event_type": "hydraulic_pump_failure",
            "defect_summary": "Hydraulic pump P-110 failure",
            "location": "MIA",
            "event_at": "2026-10-22T10:00:00Z",
            "created_at": "2026-10-22T10:05:00Z",
            "schema_version": "1.0",
            "trace_context": {
                "trace_id": "trace-controller-001",
                "correlation_id": "corr-controller-001",
            },
        },
        "failed_part_number": "P-110",
        "affected_flight_numbers": ["FX103"],
        "evaluated_at": "2026-10-22T10:10:00Z",
    }


def test_valid_intake_is_ready_for_routing() -> None:
    result = validate_controller_intake(valid_payload())

    assert result.status is IntakeStatus.READY
    assert result.intake is not None
    assert result.intake.case.case_id == "AOG-CONTROLLER-001"
    assert result.findings == ()


def test_incomplete_or_unknown_intake_is_rejected_with_field_findings() -> None:
    incomplete = valid_payload()
    incomplete.pop("affected_flight_numbers")
    result = validate_controller_intake(incomplete)

    assert result.status is IntakeStatus.REJECTED
    assert result.intake is None
    assert any(finding.field_path == "affected_flight_numbers" for finding in result.findings)

    unknown = valid_payload()
    unknown["perform_repair"] = True
    unknown_result = validate_controller_intake(unknown)
    assert unknown_result.status is IntakeStatus.REJECTED
    assert any(finding.code == "extra_forbidden" for finding in unknown_result.findings)


def test_duplicate_flights_are_rejected() -> None:
    payload = valid_payload()
    payload["affected_flight_numbers"] = ["FX103", "FX103"]

    result = validate_controller_intake(payload)

    assert result.status is IntakeStatus.REJECTED
    assert any("unique" in finding.message for finding in result.findings)
