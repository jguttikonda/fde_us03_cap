import json
from datetime import UTC, datetime

import pytest

from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.case import TraceContext
from aog_recovery.observability.structured import append_event, serialize_event


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[str] = []

    def append(self, record: str) -> None:
        self.records.append(record)


def audit_event(details: dict[str, object], event_type: str = "human_decision") -> AuditEvent:
    return AuditEvent(
        schema_version="1.0",
        occurred_at=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        event_type=event_type,
        case_id="case-001",
        request_id="req-001",
        trace_context=TraceContext(trace_id="trace-001", correlation_id="corr-001"),
        component="human-gate",
        status="approved",
        evidence_references=("ev-001",),
        rationale="Rule check passed; evidence reference ev-001",
        details=details,
    )


def test_sensitive_nested_values_are_redacted_before_serialization() -> None:
    serialized = serialize_event(
        audit_event(
            {
                "source": "synthetic-source",
                "provider_api_key": "synthetic-secret-value",
                "nested": {
                    "authorization": "Bearer synthetic-token",
                    "private_chain_of_thought": "private reasoning text",
                },
            }
        )
    )
    parsed = json.loads(serialized)

    assert "synthetic-secret-value" not in serialized
    assert "Bearer synthetic-token" not in serialized
    assert "private reasoning text" not in serialized
    assert parsed["details"]["provider_api_key"] == "[REDACTED]"
    assert parsed["details"]["nested"]["private_chain_of_thought"] == "[REDACTED]"
    assert parsed["rationale"] == "Rule check passed; evidence reference ev-001"
    assert parsed["evidence_references"] == ["ev-001"]


def test_audit_serialization_appends_records_without_overwriting() -> None:
    sink = MemoryAuditSink()

    append_event(sink, audit_event({"event": "first"}))
    append_event(sink, audit_event({"event": "second"}))

    assert len(sink.records) == 2
    assert json.loads(sink.records[0])["details"]["event"] == "first"
    assert json.loads(sink.records[1])["details"]["event"] == "second"


@pytest.mark.parametrize(
    "event_type",
    ["tool_failure", "evidence_conflict", "confidence_escalation", "human_decision"],
)
def test_audit_serializes_failures_conflicts_escalations_and_decisions(
    event_type: str,
) -> None:
    parsed = json.loads(serialize_event(audit_event({"evidence_reference": "ev-001"}, event_type)))

    assert parsed["event_type"] == event_type
    assert parsed["evidence_references"] == ["ev-001"]
    assert parsed["rationale"] == "Rule check passed; evidence reference ev-001"
