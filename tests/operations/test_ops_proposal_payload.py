import json
from pathlib import Path

from aog_recovery.operations.models import (
    CostBreakdown,
    OperationsAssessment,
    OperationsRecommendation,
    PackageAllocation,
    PackageOutcome,
    RecoveryOptionAssessment,
    ReplacementFlight,
    RouteConflict,
)

PROPOSAL = Path(__file__).parents[2] / "docs" / "agent-proposals" / "operations-agent-proposal.md"
FENCE = "`" * 3


def documented_payload() -> dict[str, object]:
    text = PROPOSAL.read_text(encoding="utf-8")
    section = text[text.index("## 8. Expected Output Standard Format") :]
    block = section.split(FENCE + "json")[1].split(FENCE)[0]
    return json.loads(block)


def test_proposal_output_format_matches_the_implemented_payload() -> None:
    doc = documented_payload()
    option = doc["recovery_options"][0]  # type: ignore[index]
    package = option["package"]
    checks = [
        (doc, OperationsAssessment),
        (option, RecoveryOptionAssessment),
        (package, PackageOutcome),
        (option["cost"], CostBreakdown),
        (package["allocations"][0], PackageAllocation),
        (doc["available_flights"][0], ReplacementFlight),  # type: ignore[index]
        (doc["conflicts"][0], RouteConflict),  # type: ignore[index]
        (doc["recommendation"], OperationsRecommendation),
    ]
    for documented, model in checks:
        assert set(documented) == set(model.model_fields), model.__name__
