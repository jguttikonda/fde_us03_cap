import re
from pathlib import Path

import pytest

from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import ImpactLevel, OptionKind, Viability
from aog_recovery.operations.prompts import (
    OPERATIONS_INSTRUCTION,
    PROMPT_A,
    PROMPT_B,
    PROMPT_C,
    STAGE_OUTPUT_FIELDS,
)
from aog_recovery.operations.reasoning import (
    OperationsFacts,
    OperationsJudgment,
    OptionFacts,
    validate_judgment,
)
from aog_recovery.operations.synthetic import SCENARIOS
from aog_recovery.validation.confidence import ConfidenceDisposition

PROPOSAL = Path(__file__).parents[2] / "docs" / "agent-proposals" / "operations-agent-proposal.md"


def facts(unprotected: int | None = 300, cost: int | None = 27600) -> OperationsFacts:
    return OperationsFacts(
        case_id="c",
        aircraft_id="N123AB",
        options=(
            OptionFacts(
                option_id="OPT-SWAP",
                kind=OptionKind.SWAP,
                viability=Viability.VIABLE_WITH_RISK,
                impact_level=ImpactLevel.MEDIUM,
                delay_minutes=60,
                unprotected_count=unprotected,
                total_cost_usd=cost,
                cost_complete=True,
                conflict_codes=(),
                missing_inputs=(),
            ),
        ),
        missing_analysis=(),
        warning_codes=(),
        conflict_codes=(),
        confidence=0.9,
        disposition=ConfidenceDisposition.PREFERRED,
        requires_human_selection=False,
        viable_option_ids=("OPT-SWAP",),
    )


def judgment(text: str = "Swap has medium impact.") -> OperationsJudgment:
    return OperationsJudgment(
        summary=text, reasoning=text, next_steps=("Review with the Ops lead.",)
    )


def test_consistent_judgment_is_accepted() -> None:
    ok = judgment("300 packages unprotected; estimated operational cost $27,600.")
    assert validate_judgment(ok, facts()) == ()


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        ("The aircraft is airworthy.", "airworthiness_claim"),
        ("It is safe to fly after the swap.", "safety_claim"),
        ("The plan was approved by operations.", "approval_or_execution_claim"),
        ("The swap has been executed.", "approval_or_execution_claim"),
        ("We approve the swap.", "approval_or_execution_claim"),
        ("There are 120 packages unprotected.", "unprotected_count_mismatch"),
        ("Estimated cost is $5,000.", "cost_mismatch"),
    ],
)
def test_guardrail_rejects_claims_and_mismatches(text: str, violation: str) -> None:
    assert violation in validate_judgment(judgment(text), facts())


def test_guardrail_rejects_empty_output() -> None:
    empty = OperationsJudgment(summary=" ", reasoning="", next_steps=())
    assert "empty_reasoning" in validate_judgment(empty, facts())


def test_human_approval_language_is_not_a_false_positive() -> None:
    text = "Human approval is required; ranking belongs to the Controller."
    assert validate_judgment(judgment(text), facts()) == ()


def test_unassessed_package_count_cannot_be_stated() -> None:
    assert "unprotected_count_mismatch" in validate_judgment(
        judgment("10 packages unprotected."), facts(unprotected=None, cost=None)
    )


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_deterministic_reasoner_always_passes_its_own_guardrail(name: str) -> None:
    scenario = SCENARIOS[name]()
    outcome = OperationsAgent(scenario.adapters).assess(scenario.request)
    assessment = outcome.assessment
    assert assessment is not None
    # A guardrail rejection would relabel the mode and add a REASONING_REJECTED warning.
    assert assessment.reasoner_mode == "deterministic_offline"
    assert "REASONING_REJECTED" not in {w.code for w in outcome.warnings}


@pytest.mark.parametrize(("stage", "prompt"), [("A", PROMPT_A), ("B", PROMPT_B), ("C", PROMPT_C)])
def test_prompt_stage_outputs_match_the_agent_proposal(stage: str, prompt: str) -> None:
    document = PROPOSAL.read_text(encoding="utf-8")
    for field in STAGE_OUTPUT_FIELDS[stage]:
        assert re.search(rf"\b{field}\b", document), f"{field} missing from proposal"
        assert field in prompt
    assert prompt in OPERATIONS_INSTRUCTION


def test_prompts_forbid_ranking_airworthiness_and_approval() -> None:
    assert "do not rank" in PROMPT_B.lower()
    assert "airworthy" in PROMPT_C
    assert "approved or executed" in PROMPT_C
    assert "untrusted" in OPERATIONS_INSTRUCTION
