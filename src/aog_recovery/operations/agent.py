import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import IntEnum
from typing import Annotated, Literal, Protocol

from pydantic import Field, StringConstraints, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.evidence import Assumption, EvidenceConflict, Unknown
from aog_recovery.observability.structured import emit_event
from aog_recovery.operations.assessment import (
    OptionCostRates,
    assess_candidate_impact,
    estimate_option_cost,
)
from aog_recovery.operations.contracts import (
    AssessmentStatus,
    CustomerServiceImpact,
    EvidenceState,
    ImpactLevel,
    OperationsAssessment,
    OperationsEvidence,
    OperationsRecommendation,
    OperationsRequest,
    OptionAssessment,
    PackageRedistribution,
)
from aog_recovery.operations.packages import (
    PackageCohort,
    RedistributionTarget,
    redistribute_packages,
)
from aog_recovery.operations.validation import (
    OperationalSnapshot,
    validate_candidate,
)
from aog_recovery.validation.confidence import ConfidenceDisposition, assess_confidence

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OperationsAnalysisInput(ContractModel):
    request: OperationsRequest
    snapshot: OperationalSnapshot
    evidence: tuple[OperationsEvidence, ...]
    assumptions: tuple[Assumption, ...]
    conflicts: tuple[EvidenceConflict, ...]
    package_manifest: tuple[PackageCohort, ...] | None
    redistribution_targets_by_option: dict[str, tuple[RedistributionTarget, ...]]
    service_level_order: tuple[NonEmptyString, ...]
    cost_rates: OptionCostRates
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    confidence_degradation_per_issue: Annotated[float, Field(ge=0.0, le=1.0)] = 0.10
    adapter_failures: tuple[StructuredError, ...] = ()

    @model_validator(mode="after")
    def require_target_maps_for_known_candidates(self) -> OperationsAnalysisInput:
        candidate_ids = {candidate.option_id for candidate in self.request.candidates}
        unknown_option_ids = set(self.redistribution_targets_by_option) - candidate_ids
        if unknown_option_ids:
            raise ValueError(
                "redistribution targets refer to unknown options: "
                + ", ".join(sorted(unknown_option_ids))
            )
        return self


def _emit_assessment_event(
    input_data: OperationsAnalysisInput,
    event_type: str,
    status: str,
    rationale: str,
    details: dict[str, object],
    evidence_references: tuple[str, ...] = (),
) -> None:
    emit_event(
        AuditEvent(
            schema_version=input_data.request.schema_version,
            occurred_at=datetime.now(UTC),
            event_type=event_type,
            case_id=input_data.request.case_id,
            request_id=None,
            trace_context=input_data.request.trace_context,
            component="operations-agent",
            status=status,
            evidence_references=evidence_references,
            rationale=rationale,
            details=details,
        )
    )


class OperationsReasoningInput(ContractModel):
    case_id: NonEmptyString
    option_assessments: tuple[OptionAssessment, ...]
    evidence: tuple[OperationsEvidence, ...]
    assumptions: tuple[Assumption, ...]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    missing_evidence: tuple[NonEmptyString, ...]
    conflicts: tuple[NonEmptyString, ...]


class OperationsReasoningOutput(ContractModel):
    preferred_option_id: NonEmptyString | None
    rationale: NonEmptyString
    next_steps: tuple[NonEmptyString, ...]
    tradeoff_notes: tuple[NonEmptyString, ...]
    summary: NonEmptyString


class OperationsReasoner(Protocol):
    async def reason(self, input_data: OperationsReasoningInput) -> OperationsReasoningOutput: ...


class _ImpactRank(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


def _combine_impact(first: ImpactLevel, second: ImpactLevel) -> ImpactLevel:
    return first if _ImpactRank[first.name] >= _ImpactRank[second.name] else second


def _conflict_reference(option_id: str, code: str) -> str:
    return f"{option_id}:{code}"


def _route_disruption_delay(
    input_data: OperationsAnalysisInput,
    flight_ids: tuple[str, ...],
) -> int:
    flights = {flight.flight_id: flight for flight in input_data.snapshot.flights}
    delays = (
        disruption.delay_minutes
        for disruption in input_data.snapshot.disruptions
        for flight_id in flight_ids
        if flight_id in flights
        and disruption.route == flights[flight_id].route
        and disruption.starts_at < flights[flight_id].arrival_at
        and flights[flight_id].departure_at < disruption.ends_at
    )
    return max(delays, default=0)


def _customer_impacts(
    allocation: PackageRedistribution,
    evidence_references: tuple[str, ...],
) -> tuple[CustomerServiceImpact, ...]:
    return tuple(
        CustomerServiceImpact(
            service_level=item.service_level,
            packages_at_risk=item.package_count,
            explanation=(f"{item.package_count} {item.service_level} packages remain unprotected."),
            evidence_references=evidence_references,
        )
        for item in allocation.unprotected_by_service_level
    )


class OperationsAgent:
    def __init__(
        self,
        reasoner: OperationsReasoner,
        reasoning_timeout_seconds: float = 30.0,
    ) -> None:
        if reasoning_timeout_seconds <= 0:
            raise ValueError("reasoning_timeout_seconds must be positive")
        self._reasoner = reasoner
        self._reasoning_timeout_seconds = reasoning_timeout_seconds

    async def assess(self, input_data: OperationsAnalysisInput) -> OperationsAssessment:
        _emit_assessment_event(
            input_data,
            event_type="input_validation",
            status="validated",
            rationale="Operations request and snapshot passed typed validation.",
            details={
                "candidate_count": len(input_data.request.candidates),
                "evidence_count": len(input_data.evidence),
            },
        )
        option_results: list[OptionAssessment] = []
        all_missing: set[str] = set(input_data.snapshot.missing_evidence)
        all_conflicts = {conflict.conflict_id for conflict in input_data.conflicts}
        unknowns: dict[str, Unknown] = {}
        errors = list(input_data.adapter_failures)
        evidence_conflicts = list(input_data.conflicts)

        evidence_by_subject: dict[str, list[OperationsEvidence]] = {}
        for evidence_item in input_data.evidence:
            if evidence_item.state in {
                EvidenceState.PARTIAL,
                EvidenceState.STALE,
                EvidenceState.UNAVAILABLE,
            }:
                all_missing.add(f"evidence:{evidence_item.evidence_id}:{evidence_item.state.value}")
            if evidence_item.state is EvidenceState.CONFLICTING:
                evidence_by_subject.setdefault(evidence_item.subject, []).append(evidence_item)
        for subject, evidence_items in evidence_by_subject.items():
            if len(evidence_items) >= 2 and not any(
                set(conflict.evidence_references) >= {item.evidence_id for item in evidence_items}
                for conflict in evidence_conflicts
            ):
                evidence_conflicts.append(
                    EvidenceConflict(
                        conflict_id=f"operations-conflict:{subject}",
                        claim_reference=subject,
                        evidence_references=tuple(item.evidence_id for item in evidence_items),
                        description=f"Conflicting source-backed values for {subject}.",
                    )
                )
            elif len(evidence_items) < 2:
                all_missing.add(f"conflicting-evidence-sources:{subject}")

        all_conflicts.update(conflict.conflict_id for conflict in evidence_conflicts)
        for error in errors:
            all_missing.add(f"adapter:{error.component}:{error.category}")

        for candidate in input_data.request.candidates:
            validation = validate_candidate(
                candidate,
                input_data.request.affected_flight_ids,
                input_data.snapshot,
            )
            affected_flights = tuple(
                flight
                for flight in input_data.snapshot.flights
                if flight.flight_id in input_data.request.affected_flight_ids
            )
            candidate_impact = assess_candidate_impact(
                candidate,
                affected_flights,
                input_data.snapshot.impact_thresholds,
                route_disruption_delay_minutes=_route_disruption_delay(
                    input_data,
                    input_data.request.affected_flight_ids,
                ),
            )
            impact_level = _combine_impact(validation.impact_level, candidate_impact.impact_level)

            package_redistribution = None
            option_missing = list(validation.missing_evidence)
            unprotected_count: int | None = None
            if input_data.package_manifest is None:
                option_missing.append(f"package-manifest:{candidate.option_id}")
            elif (
                candidate.option_id not in input_data.redistribution_targets_by_option
                and input_data.package_manifest
            ):
                option_missing.append(f"redistribution-targets:{candidate.option_id}")
            else:
                targets = input_data.redistribution_targets_by_option.get(
                    candidate.option_id,
                    (),
                )
                package_redistribution = redistribute_packages(
                    input_data.package_manifest,
                    targets,
                    input_data.service_level_order,
                )
                unprotected_count = sum(
                    item.package_count
                    for item in package_redistribution.unprotected_by_service_level
                )

            option_missing_tuple = tuple(sorted(set(option_missing)))
            all_missing.update(option_missing_tuple)
            for missing in option_missing_tuple:
                unknowns[missing] = Unknown(
                    claim_reference=missing,
                    description=f"Required Operations evidence is unavailable: {missing}.",
                    required_evidence=(missing,),
                )
            option_conflicts = tuple(
                _conflict_reference(candidate.option_id, finding.code)
                for finding in validation.findings
                if finding.blocks_feasibility
            )
            all_conflicts.update(option_conflicts)
            evidence_references = candidate.evidence_references
            customer_impacts = (
                _customer_impacts(package_redistribution, evidence_references)
                if package_redistribution is not None
                else ()
            )
            risks = tuple(finding.description for finding in validation.findings)
            risks += tuple(impact.explanation for impact in customer_impacts)
            option_results.append(
                OptionAssessment(
                    option_id=candidate.option_id,
                    kind=candidate.kind,
                    feasible=validation.feasible,
                    impact_level=impact_level,
                    affected_flight_ids=validation.affected_flight_ids,
                    affected_routes=validation.affected_routes,
                    delay_minutes=candidate_impact.delay_minutes,
                    package_redistribution=package_redistribution,
                    customer_impacts=customer_impacts,
                    cost_estimate=estimate_option_cost(
                        candidate,
                        candidate_impact.delay_minutes,
                        unprotected_count,
                        input_data.cost_rates,
                    ),
                    risks=risks,
                    evidence_references=evidence_references,
                    assumptions=candidate.assumptions,
                    missing_evidence=option_missing_tuple,
                    conflict_references=option_conflicts,
                )
            )

        if all_conflicts:
            _emit_assessment_event(
                input_data,
                event_type="conflict_detected",
                status="conflict",
                rationale="Deterministic Operations checks identified conflicts.",
                details={"conflict_count": len(all_conflicts)},
                evidence_references=tuple(
                    sorted(
                        {
                            evidence_reference
                            for conflict in evidence_conflicts
                            for evidence_reference in conflict.evidence_references
                        }
                    )
                ),
            )

        missing_evidence = tuple(sorted(all_missing))
        conflicts = tuple(sorted(all_conflicts))
        pre_reasoning_confidence = max(
            0.0,
            input_data.confidence
            - input_data.confidence_degradation_per_issue
            * (len(all_missing) + len(evidence_conflicts)),
        )
        reasoning_input = OperationsReasoningInput(
            case_id=input_data.request.case_id,
            option_assessments=tuple(option_results),
            evidence=input_data.evidence,
            assumptions=input_data.assumptions,
            confidence=pre_reasoning_confidence,
            missing_evidence=missing_evidence,
            conflicts=conflicts,
        )
        try:
            reasoning = await asyncio.wait_for(
                self._reasoner.reason(reasoning_input),
                timeout=self._reasoning_timeout_seconds,
            )
        except TimeoutError:
            _emit_assessment_event(
                input_data,
                event_type="reasoning_timeout",
                status="unavailable",
                rationale="Operations trade-off reasoning exceeded its configured timeout.",
                details={"error_category": "timeout"},
            )
            errors.append(
                StructuredError(
                    schema_version="1.0",
                    category="timeout",
                    component="operations-reasoner",
                    message="Operations trade-off reasoning exceeded its configured timeout.",
                    retryable=False,
                    case_impact=(
                        "Deterministic option findings remain available, but no preferred "
                        "option was established."
                    ),
                )
            )
            all_missing.add("operations-reasoning:timeout")
            missing_evidence = tuple(sorted(all_missing))
            reasoning = OperationsReasoningOutput(
                preferred_option_id=None,
                rationale=(
                    "Model reasoning timed out; deterministic option findings are retained "
                    "without selecting a preferred option."
                ),
                next_steps=("Review the deterministic findings and retry reasoning.",),
                tradeoff_notes=(),
                summary="Partial Operations assessment; reasoning timed out.",
            )
        option_by_id: Mapping[str, OptionAssessment] = {
            option.option_id: option for option in option_results
        }
        if reasoning.preferred_option_id is not None:
            chosen = option_by_id.get(reasoning.preferred_option_id)
            if chosen is None:
                raise ValueError(
                    "reasoner selected an option that was not supplied by the Controller"
                )
            if chosen.feasible is not True:
                raise ValueError(
                    "reasoner selected an option not deterministically marked feasible"
                )

        degraded_issue_count = len(all_missing) + len(evidence_conflicts)
        effective_confidence = max(
            0.0,
            input_data.confidence
            - input_data.confidence_degradation_per_issue * degraded_issue_count,
        )
        confidence_assessment = assess_confidence(
            effective_confidence,
            tuple(evidence_conflicts),
            tuple(unknowns.values()),
        )
        recommendation_status: Literal["preferred", "provisional", "escalate", "no_preference"]
        if confidence_assessment.disposition is ConfidenceDisposition.ESCALATION_REQUIRED:
            status = AssessmentStatus.ESCALATION_REQUIRED
            recommendation_status = "escalate"
        elif confidence_assessment.disposition is ConfidenceDisposition.PROVISIONAL:
            status = AssessmentStatus.PROVISIONAL
            recommendation_status = "provisional"
        elif missing_evidence:
            status = AssessmentStatus.PARTIAL
            recommendation_status = "provisional"
        else:
            status = AssessmentStatus.COMPLETE
            recommendation_status = (
                "preferred" if reasoning.preferred_option_id is not None else "no_preference"
            )

        recommendation = OperationsRecommendation(
            preferred_option_id=reasoning.preferred_option_id,
            status=recommendation_status,
            confidence=effective_confidence,
            rationale=reasoning.rationale,
            next_steps=reasoning.next_steps,
        )
        aggregate_impact_level = max(
            (option.impact_level for option in option_results if option.impact_level is not None),
            key=lambda item: _ImpactRank[item.name],
            default=None,
        )
        assessment = OperationsAssessment(
            schema_version="1.0",
            case_id=input_data.request.case_id,
            trace_context=input_data.request.trace_context,
            status=status,
            confidence=effective_confidence,
            impact_level=aggregate_impact_level,
            option_assessments=tuple(option_results),
            evidence=input_data.evidence,
            assumptions=input_data.assumptions,
            missing_evidence=missing_evidence,
            conflicts=conflicts,
            errors=tuple(errors),
            recommendation=recommendation,
            summary=reasoning.summary,
            tradeoff_notes=reasoning.tradeoff_notes,
        )
        if assessment.status is not AssessmentStatus.COMPLETE or assessment.errors:
            _emit_assessment_event(
                input_data,
                event_type="degraded_result",
                status=assessment.status.value,
                rationale="Operations assessment contains missing or degraded evidence.",
                details={
                    "error_count": len(assessment.errors),
                    "missing_evidence_count": len(assessment.missing_evidence),
                    "conflict_count": len(assessment.conflicts),
                },
                evidence_references=input_data.request.evidence_references,
            )
        _emit_assessment_event(
            input_data,
            event_type="assessment_completed",
            status=assessment.status.value,
            rationale="Operations domain assessment completed for Controller aggregation.",
            details={
                "option_count": len(assessment.option_assessments),
                "confidence": assessment.confidence,
            },
            evidence_references=input_data.request.evidence_references,
        )
        return assessment
