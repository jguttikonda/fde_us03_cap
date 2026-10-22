"""Controller-owned recommendation assembly and human decision recording."""

import json
from datetime import UTC, datetime
from hashlib import sha256

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.governance import HumanDecisionRecord
from aog_recovery.controller.context import ControllerAuditRecorder
from aog_recovery.controller.models import (
    CandidateHandoff,
    ExcludedRecoveryOption,
    RankedRecoveryOption,
    RecommendationStatus,
    RecommendationWeights,
    RecoveryDecisionBrief,
    UnrankedHandoff,
)
from aog_recovery.controller.ranking import rank_options
from aog_recovery.controller.scoring import score_candidates
from aog_recovery.maintenance.models import MaintenanceAssessmentPayload
from aog_recovery.validation.boundaries import validate_contract_json
from aog_recovery.validation.confidence import ConfidenceDisposition
from aog_recovery.validation.human_gate import HumanGateStatus, assess_human_gate
from aog_recovery.validation.models import ValidationFinding

SCORING_ALGORITHM_VERSION = "aog-score-v1"


def build_recommendation(
    handoff: UnrankedHandoff,
    *,
    audit_recorder: ControllerAuditRecorder | None = None,
    occurred_at: datetime | None = None,
) -> RecoveryDecisionBrief:
    """Build a deterministic decision brief without changing the human gate."""
    scoring = score_candidates(handoff.case, handoff.candidates)
    ranking = rank_options(scoring.scored_options)
    excluded = tuple(
        _excluded_option(candidate) for candidate in handoff.candidates if not candidate.eligible
    )
    status = _recommendation_status(handoff, ranking.ranked_options, scoring.unscored_options)
    required_action = _required_human_action(status, ranking.requires_human_selection)
    recommendation_version = _recommendation_version(handoff)
    human_gate = assess_human_gate(
        decisions=(),
        case_id=handoff.case.case_id,
        recommendation_version=recommendation_version,
        valid_option_ids=tuple(item.option_id for item in ranking.ranked_options),
    )
    summary = _decision_summary(
        handoff.case.case_id,
        status,
        handoff.errors,
        ranking.ranked_options,
        ranking.requires_human_selection,
    )

    brief = RecoveryDecisionBrief(
        schema_version="1.0",
        recommendation_version=recommendation_version,
        scoring_algorithm_version=SCORING_ALGORITHM_VERSION,
        case_id=handoff.case.case_id,
        trace_context=handoff.case.trace_context,
        status=status,
        summary=summary,
        ranked_options=ranking.ranked_options,
        excluded_options=excluded,
        unscored_options=scoring.unscored_options,
        weights=RecommendationWeights(),
        confidence=handoff.confidence,
        human_gate=human_gate,
        requires_human_selection=ranking.requires_human_selection,
        required_human_action=required_action,
        assumptions=_assumptions(handoff.candidates),
        risks=_risks(handoff.candidates),
        warnings=handoff.warnings,
        conflicts=handoff.conflicts,
        unknowns=handoff.unknowns,
        missing_data=handoff.missing_data,
        errors=handoff.errors,
    )
    if audit_recorder is None:
        return brief

    audit_errors = _record_recommendation_audit(
        brief,
        audit_recorder,
        occurred_at or datetime.now(UTC),
    )
    if not audit_errors:
        return brief
    return brief.model_copy(
        update={
            "status": RecommendationStatus.REQUIRES_ESCALATION,
            "required_human_action": (
                "Recommendation audit persistence failed; stop and escalate for human review."
            ),
            "errors": (*brief.errors, *audit_errors),
        }
    )


def apply_human_decisions(
    brief: RecoveryDecisionBrief,
    decisions: tuple[HumanDecisionRecord, ...],
    *,
    audit_recorder: ControllerAuditRecorder,
) -> RecoveryDecisionBrief:
    """Persist human decisions and update the advisory gate without executing actions."""
    known_decisions = {item.decision_id: item for item in brief.human_decisions}
    new_decisions: list[HumanDecisionRecord] = []
    decision_errors: list[StructuredError] = []
    for decision in decisions:
        existing = known_decisions.get(decision.decision_id)
        if existing is None:
            known_decisions[decision.decision_id] = decision
            new_decisions.append(decision)
        elif existing != decision:
            decision_errors.append(
                StructuredError(
                    schema_version="1.0",
                    category="human_decision_id_conflict",
                    component="controller:human_gate",
                    message="Human decision ID was reused with different record content",
                    retryable=False,
                    case_impact="Human decision could not be safely recorded",
                )
            )

    option_ids = tuple(option.option_id for option in brief.ranked_options)
    options_by_id = {option.option_id: option for option in brief.ranked_options}
    persisted: list[HumanDecisionRecord] = []
    audit_errors: list[StructuredError] = []
    for decision in new_decisions:
        option = options_by_id.get(decision.selected_option_id or "")
        error = audit_recorder.record(
            event_id=f"{brief.case_id}:human-decision:{decision.decision_id}",
            event_type="human_decision",
            case_id=brief.case_id,
            request_id=decision.decision_id,
            trace_context=brief.trace_context,
            occurred_at=decision.decided_at,
            status="recorded",
            rationale=decision.rationale,
            evidence_references=option.evidence_references if option is not None else (),
            details={
                "decision_id": decision.decision_id,
                "decision": decision.decision.value,
                "reviewer_id": decision.reviewer_id,
                "reviewer_role": decision.reviewer_role.value,
                "rationale": decision.rationale,
                "selected_action": decision.selected_action,
                "selected_option_id": decision.selected_option_id,
                "recommendation_version": decision.recommendation_version,
            },
        )
        if error is None:
            persisted.append(decision)
        else:
            audit_errors.append(error)

    gate = assess_human_gate(
        decisions=(*brief.human_decisions, *persisted),
        case_id=brief.case_id,
        recommendation_version=brief.recommendation_version,
        valid_option_ids=option_ids,
    )
    errors = (*decision_errors, *audit_errors)
    if errors:
        finding = ValidationFinding(
            field_path="human_decisions",
            code=("decision_audit_append_failed" if audit_errors else "human_decision_id_conflict"),
            message="Human decision history is incomplete or inconsistent",
        )
        gate = gate.model_copy(
            update={
                "status": HumanGateStatus.PENDING,
                "approved_roles": (),
                "findings": (*gate.findings, finding),
            }
        )
        return brief.model_copy(
            update={
                "status": RecommendationStatus.REQUIRES_ESCALATION,
                "human_gate": gate,
                "required_human_action": (
                    "Human decision history could not be fully recorded; approval remains pending."
                ),
                "errors": (*brief.errors, *errors),
                "human_decisions": (*brief.human_decisions, *persisted),
            }
        )

    status = brief.status
    if gate.status is HumanGateStatus.REJECTED:
        status = RecommendationStatus.REJECTED
        required_action = "Recommendation rejected; no operational action was executed."
    elif gate.status is HumanGateStatus.ESCALATION_REQUIRED:
        status = RecommendationStatus.REQUIRES_ESCALATION
        required_action = "Human escalation recorded; no operational action was executed."
    elif gate.status is HumanGateStatus.INFORMATION_REQUIRED:
        status = RecommendationStatus.AWAITING_ADDITIONAL_DATA
        required_action = "Additional information requested; no operational action was executed."
    elif gate.status is HumanGateStatus.APPROVED:
        status = RecommendationStatus.RESOLVED
        required_action = "Both required roles approved; no operational action was executed."
    else:
        required_action = brief.required_human_action
    return brief.model_copy(
        update={
            "status": status,
            "human_gate": gate,
            "required_human_action": required_action,
            "human_decisions": (*brief.human_decisions, *persisted),
        }
    )


def _record_recommendation_audit(
    brief: RecoveryDecisionBrief,
    audit_recorder: ControllerAuditRecorder,
    occurred_at: datetime,
) -> tuple[StructuredError, ...]:
    timestamp_key = occurred_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    request_id = f"{brief.case_id}:recommendation:{brief.recommendation_version}"
    prefix = f"{request_id}:{timestamp_key}"
    errors: list[StructuredError] = []

    def record(
        event_type: str,
        suffix: str,
        status: str,
        rationale: str,
        evidence_references: tuple[str, ...],
        details: dict[str, object],
    ) -> None:
        error = audit_recorder.record(
            event_id=f"{prefix}:{event_type}:{suffix}",
            event_type=event_type,
            case_id=brief.case_id,
            request_id=request_id,
            trace_context=brief.trace_context,
            occurred_at=occurred_at,
            status=status,
            rationale=rationale,
            evidence_references=evidence_references,
            details={"recommendation_version": brief.recommendation_version, **details},
        )
        if error is not None:
            errors.append(error)

    for ranked_option in brief.ranked_options:
        record(
            "controller_option_scored",
            ranked_option.option_id,
            "ranked",
            ranked_option.trade_off,
            ranked_option.evidence_references,
            {
                "option_id": ranked_option.option_id,
                "rank": ranked_option.rank,
                "aggregate_score": str(ranked_option.aggregate_score),
                "factor_scores": ranked_option.factor_scores.model_dump(mode="json"),
                "estimated_cost_usd": str(ranked_option.cost.total_usd),
            },
        )
    for excluded_option in brief.excluded_options:
        record(
            "controller_option_excluded",
            excluded_option.option_id,
            "excluded",
            "; ".join(excluded_option.exclusion_reasons),
            excluded_option.evidence_references,
            {
                "option_id": excluded_option.option_id,
                "exclusion_reasons": excluded_option.exclusion_reasons,
            },
        )
    for unscored_option in brief.unscored_options:
        record(
            "controller_option_unscored",
            unscored_option.option_id,
            "unscored",
            "; ".join(unscored_option.reasons),
            unscored_option.evidence_references,
            {"option_id": unscored_option.option_id, "reasons": unscored_option.reasons},
        )
    if brief.status is RecommendationStatus.REQUIRES_ESCALATION:
        record(
            "controller_escalation",
            "recommendation",
            brief.status.value,
            brief.required_human_action,
            tuple(
                reference
                for conflict in brief.conflicts
                for reference in conflict.evidence_references
            ),
            {"conflict_count": len(brief.conflicts), "missing_data_count": len(brief.missing_data)},
        )
    record(
        "controller_recommendation",
        "generated",
        brief.status.value,
        brief.required_human_action,
        tuple(
            reference for option in brief.ranked_options for reference in option.evidence_references
        ),
        {
            "ranked_count": len(brief.ranked_options),
            "excluded_count": len(brief.excluded_options),
            "unscored_count": len(brief.unscored_options),
            "confidence": brief.confidence.confidence,
        },
    )
    return tuple(errors)


def _recommendation_status(
    handoff: UnrankedHandoff,
    ranked_options: tuple[object, ...],
    unscored_options: tuple[object, ...],
) -> RecommendationStatus:
    if ranked_options:
        if handoff.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
            return RecommendationStatus.REQUIRES_ESCALATION
        if handoff.confidence.disposition is ConfidenceDisposition.PROVISIONAL:
            return RecommendationStatus.PROVISIONAL
        return RecommendationStatus.RECOMMENDED
    if handoff.candidates and all(not item.eligible for item in handoff.candidates):
        return RecommendationStatus.REQUIRES_ESCALATION
    if unscored_options:
        if handoff.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
            return RecommendationStatus.REQUIRES_ESCALATION
        return RecommendationStatus.AWAITING_ADDITIONAL_DATA
    if handoff.confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
        return RecommendationStatus.REQUIRES_ESCALATION
    if handoff.confidence.disposition is ConfidenceDisposition.PROVISIONAL:
        return RecommendationStatus.PROVISIONAL
    return RecommendationStatus.REQUIRES_ESCALATION


def _required_human_action(status: RecommendationStatus, requires_selection: bool) -> str:
    if status is RecommendationStatus.REQUIRES_ESCALATION:
        return "Escalate the case for human adjudication; no operational action has been taken."
    if status is RecommendationStatus.AWAITING_ADDITIONAL_DATA:
        return "Provide the listed missing evidence before selecting a recovery option."
    if requires_selection:
        return "Select one close-scored option; both required approvers must approve it."
    if status is RecommendationStatus.PROVISIONAL:
        return (
            "Review the provisional recommendation; both required approvers must approve "
            "before action."
        )
    return "Review the recommendation; both required approvers must approve before action."


def _decision_summary(
    case_id: str,
    status: RecommendationStatus,
    errors: tuple[StructuredError, ...],
    ranked_options: tuple[RankedRecoveryOption, ...],
    requires_human_selection: bool,
) -> str:
    if not ranked_options:
        return f"No compliant, scoreable recovery option is available for case {case_id}."

    prefix = "Partial findings. " if errors else ""
    if requires_human_selection:
        close_group = tuple(option for option in ranked_options if option.selection_group == 1)
        options = "; ".join(
            f"{option.option_id} ({option.description}): {option.trade_off}"
            for option in close_group
        )
        return (
            f"{prefix}Top options are within 2.0 score points; human selection is required: "
            f"{options}."
        )

    leading = ranked_options[0]
    if status is RecommendationStatus.RECOMMENDED:
        label = "Recommended option"
    elif status is RecommendationStatus.PROVISIONAL:
        label = "Provisional leading option"
    else:
        label = "Top-ranked option; escalation is required"
    return (
        f"{prefix}{label}: {leading.option_id} ({leading.description}), "
        f"score {leading.aggregate_score:.2f}. Trade-off: {leading.trade_off}."
    )


def _recommendation_version(handoff: UnrankedHandoff) -> str:
    material = {
        "algorithm": SCORING_ALGORITHM_VERSION,
        "handoff": handoff.model_dump(mode="json"),
    }
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    fingerprint = sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"recovery-v1-{fingerprint}"


def _excluded_option(candidate: CandidateHandoff) -> ExcludedRecoveryOption:
    result = candidate.result
    references = {item.evidence_id for item in result.evidence}
    if result.operations_result is not None:
        references.update(item.evidence_id for item in result.operations_result.evidence)
    return ExcludedRecoveryOption(
        option_id=result.candidate.option_id,
        kind=result.candidate.kind,
        description=result.candidate.description,
        exclusion_reasons=candidate.exclusion_reasons,
        evidence_references=tuple(sorted(references)),
    )


def _assumptions(candidates: tuple[CandidateHandoff, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for candidate in candidates:
        result = candidate.result
        if result.maintenance_result is not None:
            values.extend(
                assumption.statement for assumption in result.maintenance_result.assumptions
            )
            maintenance, _ = validate_contract_json(
                MaintenanceAssessmentPayload,
                result.maintenance_result.role_payload,
            )
            if maintenance is not None:
                values.extend(maintenance.assumptions)
        if result.materials_logistics_result is not None:
            values.extend(
                assumption.statement for assumption in result.materials_logistics_result.assumptions
            )
        if result.operations_result is not None and result.operations_result.assessment is not None:
            values.extend(result.operations_result.assessment.assumptions)
    return tuple(dict.fromkeys(values))


def _risks(candidates: tuple[CandidateHandoff, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for candidate in candidates:
        result = candidate.result
        if result.maintenance_result is not None:
            maintenance, _ = validate_contract_json(
                MaintenanceAssessmentPayload,
                result.maintenance_result.role_payload,
            )
            if maintenance is not None:
                values.extend(maintenance.technical_risks)
        if result.operations_result is not None and result.operations_result.assessment is not None:
            values.extend(result.operations_result.assessment.risk_factors)
    return tuple(dict.fromkeys(values))
