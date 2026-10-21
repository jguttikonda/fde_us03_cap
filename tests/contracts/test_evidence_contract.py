from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.evidence import (
    Assumption,
    Evidence,
    EvidenceConflict,
    EvidenceValidity,
    EvidenceWarning,
    Unknown,
)


def test_evidence_preserves_source_retrieval_validity_and_claim() -> None:
    evidence = Evidence.model_validate(
        {
            "evidence_id": "ev-001",
            "source": "synthetic-maintenance-record",
            "retrieved_at": datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
            "validity_state": EvidenceValidity.STALE,
            "claim_reference": "claim-001",
            "content": {"finding": "Synthetic inspection pending"},
        }
    )

    assert evidence.source == "synthetic-maintenance-record"
    assert evidence.retrieved_at == datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
    assert evidence.validity_state is EvidenceValidity.STALE
    assert evidence.claim_reference == "claim-001"


@pytest.mark.parametrize(
    "validity_state",
    [EvidenceValidity.PARTIAL, EvidenceValidity.STALE, EvidenceValidity.CONFLICTING],
)
def test_evidence_retains_degraded_validity(validity_state: EvidenceValidity) -> None:
    evidence = Evidence(
        evidence_id="ev-002",
        source="synthetic-source",
        retrieved_at=datetime(2026, 10, 21, 12, 0, tzinfo=UTC),
        validity_state=validity_state,
        claim_reference="claim-002",
        content={"state": validity_state.value},
    )

    assert evidence.validity_state is validity_state


def test_assumption_unknown_warning_and_conflict_remain_separate() -> None:
    assumption = Assumption(
        assumption_id="assumption-001",
        claim_reference="claim-003",
        statement="Synthetic assumption for testing",
        evidence_references=("ev-003",),
    )
    unknown = Unknown(
        claim_reference="claim-004",
        description="Part traceability is unavailable",
        required_evidence=("authorized-part-record",),
    )
    warning = EvidenceWarning(
        warning_id="warning-001",
        claim_reference="claim-005",
        code="SOURCE_PARTIAL",
        message="The synthetic source returned partial data",
        source_reference="synthetic-inventory",
    )
    conflict = EvidenceConflict(
        conflict_id="conflict-001",
        claim_reference="claim-006",
        evidence_references=("ev-004", "ev-005"),
        description="Synthetic sources disagree",
    )

    assert assumption.statement != unknown.description
    assert warning.source_reference == "synthetic-inventory"
    assert len(conflict.evidence_references) == 2


def test_conflict_requires_two_evidence_references() -> None:
    with pytest.raises(ValidationError):
        EvidenceConflict(
            conflict_id="conflict-002",
            claim_reference="claim-007",
            evidence_references=("ev-006",),
            description="One source is insufficient to represent a conflict",
        )
