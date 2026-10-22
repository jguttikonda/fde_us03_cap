"""Deterministic human decision-brief assembly (ARD-CTL-009..010/016, ARD-GOV-001..008)."""

from collections.abc import Mapping, Sequence

from aog_recovery.contracts.case import AogCase
from aog_recovery.controller.models import (
    ConfidenceDisposition,
    ControllerCandidateExecution,
    ControllerDecisionBrief,
    ControllerWorkflowStatus,
    RankedOption,
    RecoveryOptionKind,
    ScoringResult,
)


def build_decision_brief(
    execution: ControllerCandidateExecution | tuple[ControllerCandidateExecution, ...],
    scoring: ScoringResult,
    recommendation_version: str,
    *,
    case: AogCase | None = None,
) -> ControllerDecisionBrief:
    executions = (execution,) if isinstance(execution, ControllerCandidateExecution) else execution
    if not executions:
        raise ValueError("decision brief requires at least one candidate execution")
    case_ids = {item.case_id for item in executions}
    if len(case_ids) != 1:
        raise ValueError("candidate executions must belong to one case")
    case_id = next(iter(case_ids))
    results = tuple(
        result
        for item in executions
        for result in (
            item.maintenance_result,
            item.materials_result,
            item.operations_outcome.result if item.operations_outcome is not None else None,
        )
        if result is not None
    )
    conflicts = tuple(
        dict.fromkeys(
            detail
            for item in executions
            for detail in (
                *item.specialist_conflicts,
                *(conflict.description for conflict in item.conflicts),
                *(
                    conflict.description
                    for conflict in (
                        item.operations_outcome.conflicts
                        if item.operations_outcome is not None
                        else ()
                    )
                ),
            )
        )
    )
    confidence = min((result.confidence for result in results), default=0.0)
    if conflicts:
        confidence = min(confidence, 0.49)
    disposition = _confidence_disposition(confidence, bool(conflicts))

    missing_data = {missing for item in executions for missing in item.missing_data}
    missing_data.update(
        missing for option in scoring.unscored_options for missing in option.missing_data
    )
    operation_assessments = tuple(
        item.operations_outcome.assessment
        for item in executions
        if item.operations_outcome is not None and item.operations_outcome.assessment is not None
    )
    for assessment in operation_assessments:
        missing_data.update(assessment.missing_data)
        missing_data.update(assessment.missing_analysis)

    warnings = [warning.message for item in executions for warning in item.warnings]
    if conflicts:
        warnings.extend(conflicts)
    if scoring.unscored_options:
        warnings.append("Some options could not be scored because required metrics are missing.")
    status_order = {
        ControllerWorkflowStatus.COMPLETE: 0,
        ControllerWorkflowStatus.AWAITING_DATA: 1,
        ControllerWorkflowStatus.PARTIAL: 2,
        ControllerWorkflowStatus.REJECTED: 3,
        ControllerWorkflowStatus.FAILED: 4,
        ControllerWorkflowStatus.ESCALATED: 5,
    }
    status = max((item.status for item in executions), key=status_order.__getitem__)
    if conflicts or confidence < 0.50:
        status = ControllerWorkflowStatus.ESCALATED
    elif confidence < 0.70 or scoring.unscored_options:
        if status is ControllerWorkflowStatus.COMPLETE:
            status = ControllerWorkflowStatus.PARTIAL
    if not scoring.ranked_options and status not in {
        ControllerWorkflowStatus.FAILED,
        ControllerWorkflowStatus.REJECTED,
    }:
        status = ControllerWorkflowStatus.ESCALATED
        warnings.append("No compliant, fully scored recovery option is available.")
    if status in {ControllerWorkflowStatus.PARTIAL, ControllerWorkflowStatus.ESCALATED} and not (
        warnings or missing_data
    ):
        warnings.append("The Controller workflow did not produce a complete result.")

    close_score = scoring.human_selection_required
    can_recommend = (
        bool(scoring.ranked_options)
        and not close_score
        and not conflicts
        and confidence >= 0.50
        and status not in {ControllerWorkflowStatus.FAILED, ControllerWorkflowStatus.REJECTED}
    )
    recommended = scoring.ranked_options[0].assessment if can_recommend else None
    if recommended is not None:
        assert recommended.aggregate_score is not None
        assert recommended.score_factors is not None
        recommended_option_id = recommended.option_id
        summary = f"Preferred option: {recommended.description}"
        rationale = (
            f"It has the highest eligible weighted score ({recommended.aggregate_score:.2f}/100). "
            f"Factor scores: speed {recommended.score_factors.speed:.2f}, "
            f"operations/package impact "
            f"{recommended.score_factors.operational_package_impact:.2f}, "
            f"risk {recommended.score_factors.risk:.2f}, cost {recommended.score_factors.cost:.2f}."
        )
    elif close_score:
        recommended_option_id = None
        top_ids = ", ".join(scoring.close_score_option_ids)
        summary = "Top eligible recovery options are within two score points."
        rationale = f"Present {top_ids} with their trade-offs; human selection is required."
    else:
        recommended_option_id = None
        summary = "The available evidence does not support a unique recovery recommendation."
        rationale = (
            "Resolve the listed missing data, conflicts, or compliance exclusions with the "
            "human reviewers."
        )

    if close_score:
        next_action = "The Operations lead must select among the close-scoring options."
    elif disposition is ConfidenceDisposition.ESCALATE:
        next_action = (
            "Escalate for human adjudication or additional evidence before selecting an option."
        )
    elif recommended is not None:
        next_action = (
            "The Operations lead and Maintenance/airworthiness authority must review and approve "
            "the applicable plan before any action."
        )
    else:
        next_action = (
            "Provide the missing information and request human review; no action is authorized."
        )

    assumptions = [assumption.statement for result in results for assumption in result.assumptions]
    risks = [risk for ranked in scoring.ranked_options for risk in ranked.assessment.risks]
    key_findings = [result.summary for result in results]
    for assessment in operation_assessments:
        key_findings.append(assessment.summary)
        assumptions.extend(assessment.assumptions)
        risks.extend(assessment.risk_factors)

    return ControllerDecisionBrief(
        schema_version="1.0",
        case_id=case_id,
        recommendation_version=recommendation_version,
        status=status,
        summary=summary,
        relevant_agents=("Maintenance", "Materials & Logistics", "Operations"),
        key_findings=tuple(dict.fromkeys(key_findings)),
        ranked_options=scoring.ranked_options,
        excluded_options=scoring.excluded_options,
        recommended_option_id=recommended_option_id,
        recommendation_rationale=rationale,
        confidence=confidence,
        confidence_disposition=disposition,
        assumptions=tuple(dict.fromkeys(assumptions)),
        risks=tuple(dict.fromkeys(risks)),
        warnings=tuple(dict.fromkeys(warnings)),
        missing_data=tuple(sorted(missing_data)),
        human_approval_required=True,
        next_action=next_action,
        aircraft_id=case.aircraft_id if case is not None else None,
        case_summary=case.defect_summary if case is not None else None,
        location=case.location if case is not None else None,
    )


def _confidence_disposition(
    confidence: float,
    has_conflicts: bool,
) -> ConfidenceDisposition:
    if has_conflicts or confidence < 0.50:
        return ConfidenceDisposition.ESCALATE
    if confidence < 0.70:
        return ConfidenceDisposition.PROVISIONAL
    return ConfidenceDisposition.PREFERRED


_MAX_LIST_ITEMS = 6
_SUMMARY_TAGS = ("fastest return to service", "lowest cost")


def _bullets(items: Sequence[str], limit: int | None = None) -> list[str]:
    shown = items if limit is None else items[:limit]
    lines = [f"- {item}" for item in shown]
    hidden = len(items) - len(shown)
    if hidden > 0:
        lines.append(f"- (+{hidden} more recorded in the structured decision brief)")
    return lines


def _tag_extremes(
    values: Mapping[str, float],
    low_label: str,
    high_label: str,
    tags: dict[str, list[str]],
) -> None:
    if len(values) < 2 or min(values.values()) == max(values.values()):
        return
    low, high = min(values.values()), max(values.values())
    for option_id, value in values.items():
        if value == low:
            tags[option_id].append(low_label)
        elif value == high:
            tags[option_id].append(high_label)


def _comparison_tags(options: Sequence[RankedOption]) -> dict[str, list[str]]:
    """Describe how each option compares with the others on speed and cost."""
    tags: dict[str, list[str]] = {item.assessment.option_id: [] for item in options}
    _tag_extremes(
        {
            item.assessment.option_id: item.assessment.return_to_service_hours
            for item in options
            if item.assessment.return_to_service_hours is not None
        },
        "fastest return to service",
        "slowest return to service",
        tags,
    )
    _tag_extremes(
        {
            item.assessment.option_id: float(item.assessment.estimated_cost_usd)
            for item in options
            if item.assessment.estimated_cost_usd is not None
        },
        "lowest cost",
        "highest cost",
        tags,
    )
    return tags


def _executive_summary(
    brief: ControllerDecisionBrief,
    confidence_label: str,
    status_label: str,
    tags: Mapping[str, Sequence[str]],
) -> list[str]:
    recommended = next(
        (
            item
            for item in brief.ranked_options
            if item.assessment.option_id == brief.recommended_option_id
        ),
        None,
    )
    if recommended is not None:
        assert recommended.assessment.aggregate_score is not None
        recommendation = (
            f"Option {recommended.rank} - {recommended.assessment.description.rstrip('.')} "
            f"(score {recommended.assessment.aggregate_score:.0f}/100)."
        )
    else:
        recommendation = f"No single option can be recommended yet. {brief.summary}"
    lines = [
        "### Executive summary",
        f"- **Recommendation:** {recommendation}",
        f"- **{'Basis' if brief.ranked_options else 'What is needed'}:** "
        f"{brief.recommendation_rationale}",
    ]
    trade_offs: list[str] = []
    for tag in _SUMMARY_TAGS:
        ranks = [
            str(item.rank)
            for item in brief.ranked_options
            if tag in tags[item.assessment.option_id]
        ]
        if len(ranks) == 1:
            trade_offs.append(f"Option {ranks[0]} has the {tag}")
        elif ranks:
            trade_offs.append(f"Options {', '.join(ranks[:-1])} and {ranks[-1]} share the {tag}")
    if trade_offs:
        lines.append(f"- **Key trade-offs:** {'; '.join(trade_offs)}.")
    lines.extend(
        (
            f"- **Confidence:** {confidence_label} ({brief.confidence:.2f})",
            f"- **Status:** {status_label}",
        )
    )
    return lines


def render_decision_brief(brief: ControllerDecisionBrief) -> str:
    """Render the validated decision fields as a sponsor-readable recovery report."""
    confidence_label = {
        ConfidenceDisposition.PREFERRED: "High",
        ConfidenceDisposition.PROVISIONAL: "Medium",
        ConfidenceDisposition.ESCALATE: "Low",
    }[brief.confidence_disposition]
    status_label = {
        ControllerWorkflowStatus.COMPLETE: "Feasible",
        ControllerWorkflowStatus.PARTIAL: "Provisional",
        ControllerWorkflowStatus.ESCALATED: "Escalated",
        ControllerWorkflowStatus.AWAITING_DATA: "Awaiting data",
        ControllerWorkflowStatus.REJECTED: "Rejected",
        ControllerWorkflowStatus.FAILED: "Failed",
    }[brief.status]
    aircraft = brief.aircraft_id or brief.case_id
    case_description = brief.case_summary or brief.summary
    station = f" (Station: {brief.location})" if brief.location else ""
    tags = _comparison_tags(brief.ranked_options)
    lines = [
        f"## AOG Recovery Options for Aircraft {aircraft}",
        f"**Case:** {case_description}{station}",
        "",
        *_executive_summary(brief, confidence_label, status_label, tags),
    ]
    if brief.ranked_options:
        lines.extend(("", "### Options"))
        for option in brief.ranked_options:
            assessment = option.assessment
            assert assessment.score_factors is not None
            assert assessment.aggregate_score is not None
            label = " [RECOMMENDED]" if assessment.option_id == brief.recommended_option_id else ""
            if assessment.kind is RecoveryOptionKind.SWAP:
                sourcing = "Not needed for the replacement aircraft."
            elif assessment.sourcing_source is None:
                sourcing = "No confirmed sourcing option."
            else:
                method = (
                    assessment.sourcing_method.value if assessment.sourcing_method else "source"
                )
                location_text = assessment.sourcing_location or assessment.sourcing_source
                if assessment.sourcing_lead_time_hours is None:
                    sourcing = (
                        f"{method.replace('_', ' ').title()} from {location_text}; arrival unknown."
                    )
                else:
                    lead_hours = round(assessment.sourcing_lead_time_hours, 1)
                    sourcing = (
                        f"{method.replace('_', ' ').title()} from {location_text}; "
                        f"estimated arrival in {lead_hours:g} hours."
                    )
            eta = (
                f"About {round(assessment.return_to_service_hours, 1):g} hours"
                if assessment.return_to_service_hours is not None
                else "Unknown; required timing evidence is missing"
            )
            packages = (
                f"{assessment.affected_package_count:,} affected; "
                f"{assessment.priority_package_count:,} priority; "
                f"{assessment.unprotected_package_count:,} still at risk"
                if all(
                    value is not None
                    for value in (
                        assessment.affected_package_count,
                        assessment.priority_package_count,
                        assessment.unprotected_package_count,
                    )
                )
                else "Not assessed from available package data"
            )
            affected_flights = (
                ", ".join(assessment.affected_flight_numbers)
                if assessment.affected_flight_numbers
                else "None reported"
            )
            main_risk = assessment.main_risk or (
                assessment.risks[0] if assessment.risks else "No material risk identified"
            )
            cost = (
                f"${assessment.estimated_cost_usd:,.0f}"
                if assessment.estimated_cost_usd is not None
                else "Unknown; cost evidence is incomplete"
            )
            option_tags = tags[assessment.option_id]
            trade_off = (
                f"{', '.join(option_tags).capitalize()}."
                if option_tags
                else assessment.trade_off or "Not available"
            )
            lines.extend(
                (
                    "",
                    f"#### {option.rank}. {assessment.description}{label}",
                    f"- **Back in service:** {eta}",
                    f"- **Part sourcing:** {sourcing}",
                    f"- **Affected flights:** {affected_flights}",
                    f"- **Packages after redistribution:** {packages}",
                    f"- **Estimated cost:** {cost}",
                    f"- **Main risk:** {main_risk}",
                    f"- **Score:** {assessment.aggregate_score:.0f}/100 (speed "
                    f"{assessment.score_factors.speed:.0f}, operations/package "
                    f"{assessment.score_factors.operational_package_impact:.0f}, risk "
                    f"{assessment.score_factors.risk:.0f}, "
                    f"cost {assessment.score_factors.cost:.0f}; weights 30/30/30/10)",
                    f"- **Trade-off:** {trade_off}",
                    *(
                        (f"- **Evidence:** {', '.join(assessment.evidence_references)}",)
                        if assessment.evidence_references
                        else ()
                    ),
                )
            )
    else:
        lines.extend(("", "No compliant, fully scored recovery option is available."))
    lines.extend(("", "### Excluded options (compliance check)"))
    lines.extend(
        _bullets(
            [f"{item.option_id}: {'; '.join(item.reasons)}" for item in brief.excluded_options]
        )
        or ["- None"]
    )
    if brief.warnings:
        lines.extend(("", "### Warnings", *_bullets(brief.warnings)))
    if brief.missing_data:
        lines.extend(("", "### Missing data", *_bullets(brief.missing_data, _MAX_LIST_ITEMS)))
    if brief.assumptions:
        lines.extend(("", "### Assumptions", *_bullets(brief.assumptions, _MAX_LIST_ITEMS)))
    lines.extend(
        (
            "",
            "### Next step",
            brief.next_action,
            "",
            "---",
            "*Advisory only. Human approval is required before any action.*",
        )
    )
    return "\n".join(lines)
