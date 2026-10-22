from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import CandidateOption, OptionKind
from aog_recovery.operations.synthetic import at, default_adapters, request_for

REFS = ("evidence-ml-001",)


def test_window_resolves_to_its_end_as_an_estimate() -> None:
    estimate = ReadinessEstimate.from_window(at(14), at(16), AgentRole.MATERIALS_LOGISTICS, REFS)
    assert estimate.eta == at(16)
    assert estimate.basis is EtaBasis.ESTIMATED
    assert (estimate.window_start, estimate.window_end) == (at(14), at(16))


def test_lead_time_hours_are_anchored_at_an_explicit_time() -> None:
    estimate = ReadinessEstimate.from_lead_time_hours(
        at(12), 3.5, AgentRole.MATERIALS_LOGISTICS, REFS
    )
    assert estimate.eta == datetime(2026, 10, 21, 15, 30, tzinfo=UTC)
    confirmed = ReadinessEstimate.from_lead_time_hours(
        at(12), 3, AgentRole.MAINTENANCE, REFS, basis=EtaBasis.CONFIRMED
    )
    assert confirmed.basis is EtaBasis.CONFIRMED


@pytest.mark.parametrize(
    "build",
    [
        lambda: ReadinessEstimate.from_lead_time_hours(at(12), -1, AgentRole.MAINTENANCE, REFS),
        lambda: ReadinessEstimate.from_window(at(16), at(14), AgentRole.MAINTENANCE, REFS),
        lambda: ReadinessEstimate.from_window(at(14), at(16), AgentRole.MAINTENANCE, ()),
        lambda: ReadinessEstimate.from_window(at(14), at(16), AgentRole.OPERATIONS, REFS),
        lambda: ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=datetime(2026, 10, 21, 15),
            basis=EtaBasis.CONFIRMED,
            evidence_references=REFS,
        ),
        lambda: ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=at(15),
            basis=EtaBasis.ESTIMATED,
            window_start=at(16),
            evidence_references=REFS,
        ),
        lambda: ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=at(18),
            basis=EtaBasis.ESTIMATED,
            window_start=at(14),
            window_end=at(16),
            evidence_references=REFS,
        ),
    ],
)
def test_invalid_estimates_are_rejected(build) -> None:  # noqa: ANN001
    with pytest.raises(ValueError):  # noqa: PT011  (ValidationError is a ValueError)
        build()


def test_unknown_fields_are_rejected() -> None:
    data = ReadinessEstimate.from_window(at(14), at(16), AgentRole.MAINTENANCE, REFS).model_dump()
    with pytest.raises(ValidationError):
        ReadinessEstimate.model_validate({**data, "eta_hours": 3})


def test_operations_candidate_is_built_from_the_shared_estimate() -> None:
    estimate = ReadinessEstimate.from_window(at(14), at(15), AgentRole.MATERIALS_LOGISTICS, REFS)
    candidate = CandidateOption.with_readiness(
        "OPT-REPAIR-P120", OptionKind.REPAIR_ALTERNATE, "Repair with P-120", estimate
    )
    assert candidate.readiness_eta == at(15)
    assert candidate.eta_basis is EtaBasis.ESTIMATED
    assert candidate.eta_evidence_references == REFS
    outcome = OperationsAgent(default_adapters()).assess(request_for(candidate))
    assert outcome.result.status.value == "partial"  # an estimated ETA keeps it provisional
    assert "evidence-ml-001" in outcome.result.evidence_references
