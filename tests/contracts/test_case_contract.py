from datetime import datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.case import AogCase


def test_case_preserves_required_fields(valid_case_payload: dict[str, object]) -> None:
    case = AogCase.model_validate(valid_case_payload)

    assert case.case_id == "case-synthetic-001"
    assert case.event_at == valid_case_payload["event_at"]
    assert case.trace_context.trace_id == "trace-synthetic-001"


@pytest.mark.parametrize(
    "missing_field",
    [
        "case_id",
        "aircraft_id",
        "event_type",
        "defect_summary",
        "location",
        "event_at",
        "created_at",
        "schema_version",
        "trace_context",
    ],
)
def test_case_rejects_missing_fields(
    valid_case_payload: dict[str, object], missing_field: str
) -> None:
    del valid_case_payload[missing_field]

    with pytest.raises(ValidationError, match=missing_field):
        AogCase.model_validate(valid_case_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", "  "),
        ("schema_version", "2.0"),
        ("event_at", datetime(2026, 10, 21, 12, 0)),
        ("unexpected", "not accepted"),
    ],
)
def test_case_rejects_invalid_fields(
    valid_case_payload: dict[str, object], field: str, value: object
) -> None:
    valid_case_payload[field] = value

    with pytest.raises(ValidationError):
        AogCase.model_validate(valid_case_payload)
