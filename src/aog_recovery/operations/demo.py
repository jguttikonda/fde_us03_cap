"""Offline demonstration: python -m aog_recovery.operations.demo [scenario ...] [--json].

Runs the synthetic scenarios through the Operations Agent with the deterministic offline
reasoner. No model, network, or live system is used (ARD-TST-009).
"""

import json
import sys

from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import OperationsOutcome, OperationsRequest
from aog_recovery.operations.synthetic import SCENARIOS, Scenario

DEFAULT_ORDER = (
    "normal_repair",
    "swap_capacity",
    "full_options",
    "partner_reroute",
    "own_network_only",
    "conflicting_estimates",
    "package_timeout",
)


def _hhmm(value: object) -> str:
    return value.strftime("%H:%MZ") if hasattr(value, "strftime") else "n/a"


def _input_lines(request: OperationsRequest) -> list[str]:
    policy = request.reroute_policy
    lines = [
        f"Case {request.case.case_id}: {request.case.defect_summary}",
        f"Aircraft {request.case.aircraft_id} at {request.case.location}, "
        f"event {_hhmm(request.case.event_at)}",
        f"Affected flights: {', '.join(request.affected_flight_numbers)}",
        f"Reroute policy: partner flights "
        f"{'allowed' if policy.allow_partner_flights else 'NOT allowed'}, "
        f"own network {'first' if policy.prefer_own_network else 'not preferred'}",
    ]
    for candidate in request.candidates:
        eta = (
            f"ETA {_hhmm(candidate.readiness_eta)} ({candidate.eta_basis.value})"
            if candidate.readiness_eta and candidate.eta_basis
            else "no ETA required"
            if candidate.kind.value == "swap"
            else "ETA missing"
        )
        lines.append(
            f"Candidate {candidate.option_id} [{candidate.kind.value}]: "
            f"{candidate.description}; {eta}"
        )
    return lines


def _output_lines(outcome: OperationsOutcome) -> list[str]:
    result = outcome.result
    lines = [
        f"Status: {result.status.value}   Confidence: {result.confidence:.2f} "
        f"({outcome.confidence.disposition.value})   Human approval required: "
        f"{outcome.confidence.human_approval_required}",
    ]
    assessment = outcome.assessment
    if assessment is None:
        payload = result.role_payload
        lines.append(f"Reason: {payload.get('reason')}")
        lines.append(f"Missing analysis: {payload.get('missing_analysis')}")
        return lines

    level = assessment.operational_impact_level
    lines.append(f"Worst-case operational impact: {level.value if level else 'n/a'}")
    lines.append(f"Packages: {assessment.package_impact.summary}")
    if assessment.available_flights:
        lines.append("Flights found on the affected route(s), own network first:")
        for f in assessment.available_flights:
            status = (
                f"bookable{f' by {_hhmm(f.booking_deadline)}' if f.booking_deadline else ''}"
                if f.bookable
                else f"NOT usable: {f.restriction}"
            )
            lines.append(
                f"  - {f.flight_number} [{f.carrier_type.value}: {f.carrier_name}] "
                f"{f.origin}-{f.destination} dep {_hhmm(f.departure_at)}, "
                f"spare capacity {f.available_capacity}, ${f.cost_per_package_usd}/pkg; {status}"
            )
    lines.append("Options (Operations reports impact only; the Controller ranks):")
    for option in assessment.recovery_options:
        pkg = option.package
        unprotected = pkg.unprotected_count if pkg.assessed else "not assessed"
        cost = f"${option.cost.total_usd}" if option.cost else "n/a"
        impact = option.impact_level.value if option.impact_level else "n/a"
        lines.append(
            f"  - {option.option_id} [{option.kind.value}] {option.viability.value}: "
            f"impact={impact}, delay={option.schedule_delay_minutes} min, "
            f"unprotected={unprotected}, op. cost={cost}"
        )
        lines.extend(
            f"      {a.count} {a.group_id} pkgs -> {a.path.value} {a.target_id}"
            + (f" ({a.carrier_name})" if a.carrier_name else "")
            + (f", dep {_hhmm(a.departure_at)}" if a.departure_at else "")
            + (f", ${a.cost_usd}" if a.cost_usd else "")
            for a in pkg.allocations
        )
    if assessment.conflicts:
        lines.append("Conflicts:")
        lines.extend(f"  - {c.code.value}: {c.description}" for c in assessment.conflicts)
    if assessment.missing_analysis:
        lines.append(f"Missing analysis: {'; '.join(assessment.missing_analysis)}")
    if assessment.warnings:
        lines.append(f"Warnings: {'; '.join(assessment.warnings)}")
    if assessment.confidence_reasons:
        lines.append(f"Confidence reduced by: {'; '.join(assessment.confidence_reasons)}")
    lines.append(f"Recommendation: {assessment.recommendation.decision.value}")
    lines.append(f"Reasoning ({assessment.reasoner_mode}): {assessment.recommendation.reasoning}")
    lines.append("Next steps: " + " | ".join(assessment.recommendation.next_steps))
    return lines


def run_scenario(scenario: Scenario, as_json: bool = False) -> str:
    outcome = OperationsAgent(scenario.adapters).assess(scenario.request)
    header = [f"=== {scenario.title} ===", scenario.description, "", "INPUT"]
    body = ["", "OUTPUT"]
    if as_json:
        body.append(json.dumps(outcome.result.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        body.extend(_output_lines(outcome))
    footer = ["", f"Audit events recorded: {len(outcome.audit_events)}"]
    return "\n".join([*header, *_input_lines(scenario.request), *body, *footer])


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    names = [a for a in args if not a.startswith("--")] or list(DEFAULT_ORDER)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"Unknown scenario(s): {', '.join(unknown)}. Available: {', '.join(SCENARIOS)}")
        return 2
    for name in names:
        print(run_scenario(SCENARIOS[name](), as_json))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
