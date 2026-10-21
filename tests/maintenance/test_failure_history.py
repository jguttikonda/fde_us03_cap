from datetime import UTC, datetime, timedelta

import pytest

from aog_recovery.config import AogSettings
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.maintenance.failure_history import analyze_recurring_failures

AS_OF = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def failure_record(
    evidence_id: str,
    part_number: str = "P-110",
    occurred_at: datetime = AS_OF,
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
    content_overrides: dict[str, object] | None = None,
) -> Evidence:
    content: dict[str, object] = {
        "part_number": part_number,
        "occurred_at": occurred_at,
    }
    if content_overrides:
        content.update(content_overrides)
    return Evidence(
        evidence_id=evidence_id,
        source="synthetic-maintenance-history",
        retrieved_at=AS_OF,
        validity_state=validity,
        claim_reference=f"failure-claim-{evidence_id}",
        content=content,
    )


def test_three_failures_within_configured_window_are_counted_with_sources() -> None:
    records = (
        failure_record("failure-001", occurred_at=AS_OF - timedelta(days=89)),
        failure_record("failure-002", occurred_at=AS_OF - timedelta(days=45)),
        failure_record("failure-003", occurred_at=AS_OF),
    )

    result = analyze_recurring_failures(records, AS_OF, AogSettings(_env_file=None))

    assert len(result.summaries) == 1
    assert result.summaries[0].part_number == "P-110"
    assert result.summaries[0].occurrences == 3
    assert result.summaries[0].window_days == 90
    assert result.summaries[0].evidence_references == (
        "failure-001",
        "failure-002",
        "failure-003",
    )


def test_threshold_and_window_boundaries_are_deterministic() -> None:
    records = (
        failure_record("failure-in-window", occurred_at=AS_OF - timedelta(days=90)),
        failure_record("failure-too-old", occurred_at=AS_OF - timedelta(days=90, microseconds=1)),
    )
    settings = AogSettings(
        _env_file=None,
        maintenance_recurrence_threshold=1,
        maintenance_recurrence_window_days=90,
    )

    result = analyze_recurring_failures(records, AS_OF, settings)

    assert len(result.summaries) == 1
    assert result.summaries[0].evidence_references == ("failure-in-window",)
    assert analyze_recurring_failures(records, AS_OF, settings) == result


def test_below_threshold_does_not_claim_recurring_failure() -> None:
    records = (failure_record("failure-001"), failure_record("failure-002"))

    result = analyze_recurring_failures(records, AS_OF, AogSettings(_env_file=None))

    assert result.summaries == ()
    assert result.findings == ()


def test_incomplete_stale_and_future_records_remain_visible_not_counted() -> None:
    records = (
        failure_record("failure-incomplete", content_overrides={"occurred_at": None}),
        failure_record("failure-stale", validity=EvidenceValidity.STALE),
        failure_record("failure-future", occurred_at=AS_OF + timedelta(hours=1)),
    )

    result = analyze_recurring_failures(records, AS_OF, AogSettings(_env_file=None))

    assert result.summaries == ()
    assert {finding.code for finding in result.findings} == {
        "datetime_type",
        "stale_evidence",
        "future_failure_timestamp",
    }


def test_naive_assessment_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="as_of must include a timezone"):
        analyze_recurring_failures((), datetime(2026, 10, 21, 12, 0), AogSettings(_env_file=None))
