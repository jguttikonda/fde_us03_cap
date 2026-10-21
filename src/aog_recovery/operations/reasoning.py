"""Bounded reasoning boundary (ARD-PRN-003/004, ARD-SEC-005/008, ARD-GOV-008, ARD-RES-006).

Reasoning sees only deterministic facts (never tool free text) and returns explanation text. Its
output is guard-checked before use and can never change a computed value.
"""

import re
from typing import Annotated, Protocol

from pydantic import Field, StringConstraints

from aog_recovery.contracts.base import ContractModel
from aog_recovery.operations.models import ImpactLevel, OptionKind, Viability
from aog_recovery.validation.confidence import ConfidenceDisposition

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

DETERMINISTIC_MODE = "deterministic_offline"


class OptionFacts(ContractModel):
    option_id: NonEmptyString
    kind: OptionKind
    viability: Viability
    impact_level: ImpactLevel | None
    delay_minutes: int | None
    unprotected_count: int | None
    total_cost_usd: int | None
    cost_complete: bool
    conflict_codes: tuple[NonEmptyString, ...]
    missing_inputs: tuple[NonEmptyString, ...]
    rerouted_own_count: int | None = None
    rerouted_partner_count: int | None = None


class OperationsFacts(ContractModel):
    case_id: NonEmptyString
    aircraft_id: NonEmptyString
    options: tuple[OptionFacts, ...]
    missing_analysis: tuple[NonEmptyString, ...]
    warning_codes: tuple[NonEmptyString, ...]
    conflict_codes: tuple[NonEmptyString, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    disposition: ConfidenceDisposition
    requires_human_selection: bool
    viable_option_ids: tuple[NonEmptyString, ...]


class OperationsJudgment(ContractModel):
    summary: str
    reasoning: str
    next_steps: tuple[str, ...]


class OperationsReasoner(Protocol):
    mode: str

    def reason(self, facts: OperationsFacts) -> OperationsJudgment: ...


class DeterministicReasoner:
    """Offline template reasoner for tests and demonstration; not a language model."""

    mode = DETERMINISTIC_MODE

    def reason(self, facts: OperationsFacts) -> OperationsJudgment:
        viable = len(facts.viable_option_ids)
        not_viable = sum(option.viability is Viability.NOT_VIABLE for option in facts.options)
        undetermined = sum(option.viability is Viability.UNDETERMINED for option in facts.options)
        summary = (
            f"Operations assessed {len(facts.options)} recovery option(s) for aircraft "
            f"{facts.aircraft_id}: {viable} operationally viable, {not_viable} not viable, "
            f"{undetermined} undetermined. Confidence {facts.confidence:.2f} "
            f"({facts.disposition.value})."
        )

        lines: list[str] = []
        for option in facts.options:
            if option.impact_level is None:
                lines.append(
                    f"{option.option_id} ({option.kind.value}) is {option.viability.value}."
                )
                continue
            cost = f"${option.total_cost_usd}" if option.total_cost_usd is not None else "unknown"
            if not option.cost_complete:
                cost += " (excludes unassessed package cost)"
            unprotected = (
                f"{option.unprotected_count} packages unprotected"
                if option.unprotected_count is not None
                else "package impact not assessed"
            )
            reroute = (
                f", {option.rerouted_own_count} packages rerouted on own-network flights and "
                f"{option.rerouted_partner_count} on partner flights"
                if (option.rerouted_own_count or 0) + (option.rerouted_partner_count or 0) > 0
                else ""
            )
            lines.append(
                f"{option.option_id} ({option.kind.value}): {option.impact_level.value} impact, "
                f"{option.delay_minutes} minute delay, {unprotected}{reroute}, estimated "
                f"operational cost {cost}."
            )
        if facts.conflict_codes:
            lines.append(
                "Conflicts detected: " + ", ".join(sorted(set(facts.conflict_codes))) + "."
            )
        if facts.missing_analysis:
            lines.append("Analysis not performed: " + "; ".join(facts.missing_analysis) + ".")
        lines.append(
            "Operations reports impact evidence only; ranking belongs to the Controller and the "
            "decision belongs to the human approvers."
        )

        steps: list[str] = []
        if facts.conflict_codes or facts.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
            steps.append("Escalate for human adjudication before any operational action.")
        if facts.missing_analysis:
            steps.append("Restore the unavailable sources and re-run the assessment.")
        if facts.requires_human_selection:
            steps.append("Present the viable options and trade-offs for human selection.")
        if any((option.rerouted_partner_count or 0) > 0 for option in facts.options):
            steps.append(
                "Partner flights are proposals only: humans must book them before the booking "
                "deadlines; this agent books nothing."
            )
        steps.append("Hand the assessment to the Controller for ranking and human approval.")

        return OperationsJudgment(
            summary=summary, reasoning=" ".join(lines), next_steps=tuple(steps)
        )


_FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("airworthiness_claim", re.compile(r"\bairworthy\b", re.IGNORECASE)),
    (
        "safety_claim",
        re.compile(
            r"\b(?:is|are|be|deemed|declared)\s+safe\b|\bsafe\s+to\s+(?:fly|operate|dispatch|return)",
            re.IGNORECASE,
        ),
    ),
    (
        "approval_or_execution_claim",
        re.compile(
            r"\b(?:has|have|had|been|was|were|is|are)\s+(?:been\s+)?"
            r"(?:approved|executed|dispatched|rebooked|rescheduled|cancelled|canceled|authorized)\b"
            r"|\b(?:i|we)\s+(?:approve|authorize)\b",
            re.IGNORECASE,
        ),
    ),
)
_UNPROTECTED_PATTERN = re.compile(r"(\d[\d,]*)\s+(?:packages\s+)?unprotected", re.IGNORECASE)
_DOLLAR_PATTERN = re.compile(r"\$\s?(\d[\d,]*)")


def validate_judgment(judgment: OperationsJudgment, facts: OperationsFacts) -> tuple[str, ...]:
    """Return violation codes; an empty tuple means the judgment may be used."""
    text = " ".join((judgment.summary, judgment.reasoning, *judgment.next_steps))
    violations: list[str] = []
    if not judgment.summary.strip() or not judgment.reasoning.strip() or not judgment.next_steps:
        violations.append("empty_reasoning")
    violations.extend(code for code, pattern in _FORBIDDEN_PATTERNS if pattern.search(text))

    allowed_unprotected = {
        str(option.unprotected_count)
        for option in facts.options
        if option.unprotected_count is not None
    }
    if any(
        match.replace(",", "") not in allowed_unprotected
        for match in _UNPROTECTED_PATTERN.findall(text)
    ):
        violations.append("unprotected_count_mismatch")

    allowed_costs = {
        str(option.total_cost_usd) for option in facts.options if option.total_cost_usd is not None
    }
    if any(match.replace(",", "") not in allowed_costs for match in _DOLLAR_PATTERN.findall(text)):
        violations.append("cost_mismatch")
    return tuple(violations)
