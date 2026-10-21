import pytest

from aog_recovery.contracts.evidence import EvidenceConflict, Unknown
from aog_recovery.validation.confidence import (
    ConfidenceDisposition,
    assess_confidence,
)


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.49, ConfidenceDisposition.ESCALATION_REQUIRED),
        (0.50, ConfidenceDisposition.PROVISIONAL),
        (0.69, ConfidenceDisposition.PROVISIONAL),
        (0.70, ConfidenceDisposition.PREFERRED),
    ],
)
def test_confidence_threshold_boundaries(
    confidence: float, expected: ConfidenceDisposition
) -> None:
    assessment = assess_confidence(confidence, conflicts=(), unknowns=())

    assert assessment.disposition is expected
    assert assessment.human_approval_required


def test_conflict_forces_escalation_even_at_high_confidence() -> None:
    conflict = EvidenceConflict(
        conflict_id="conflict-001",
        claim_reference="claim-001",
        evidence_references=("ev-001", "ev-002"),
        description="Synthetic sources conflict",
    )

    assessment = assess_confidence(0.99, conflicts=(conflict,), unknowns=())

    assert assessment.disposition is ConfidenceDisposition.ESCALATION_REQUIRED
    assert assessment.conflict_references == ("conflict-001",)


def test_unknown_evidence_remains_explicit_and_is_not_inferred() -> None:
    unknown = Unknown(
        claim_reference="claim-unknown",
        description="Synthetic part authorization not supplied",
        required_evidence=("approved-part-record",),
    )

    assessment = assess_confidence(0.75, conflicts=(), unknowns=(unknown,))

    assert assessment.unknown_claim_references == ("claim-unknown",)
    assert assessment.disposition is ConfidenceDisposition.PREFERRED
    assert assessment.human_approval_required
