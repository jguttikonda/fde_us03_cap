"""Typed Controller intake and decision brief contracts (ARD-CTL-001..019)."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import AgentResult, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import EvidenceConflict, EvidenceWarning, Unknown
from aog_recovery.contracts.readiness import SourcingMethod
from aog_recovery.coordination.models import H3H4Exchange
from aog_recovery.coordination.recording import ExchangeRecordingResult
from aog_recovery.maintenance.models import MaintenanceRiskLevel
from aog_recovery.materials_logistics.models import (
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    SourcingOption,
)
from aog_recovery.operations.models import CandidateOption, ImpactLevel, OperationsOutcome
from aog_recovery.validation.models import ValidationFinding

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
Score = Annotated[float, Field(ge=0.0, le=100.0)]
NonNegativeUsd = Annotated[Decimal, Field(ge=Decimal("0"))]


class RecoveryOptionKind(StrEnum):
    REPAIR_ORIGINAL = "repair_original"
    REPAIR_ALTERNATE = "repair_alternate"
    SWAP = "swap"
    DELAY = "delay"


class ControllerWorkflowStatus(StrEnum):
    AWAITING_DATA = "awaiting_data"
    COMPLETE = "complete"
    PARTIAL = "partial"
    ESCALATED = "escalated"
    REJECTED = "rejected"
    FAILED = "failed"


class ConfidenceDisposition(StrEnum):
    PREFERRED = "preferred"
    PROVISIONAL = "provisional"
    ESCALATE = "escalate"


class ControllerIntake(ContractModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case: AogCase
    failed_part_number: NonEmptyString
    affected_flight_numbers: tuple[NonEmptyString, ...] = Field(min_length=1)
    evaluated_at: datetime

    @field_validator("evaluated_at")
    @classmethod
    def require_timezone_aware_evaluation_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_unique_affected_flights(self) -> ControllerIntake:
        if len(set(self.affected_flight_numbers)) != len(self.affected_flight_numbers):
            raise ValueError("affected flight numbers must be unique")
        return self


class ScoreFactors(ContractModel):
    speed: Score
    operational_package_impact: Score
    risk: Score
    cost: Score


class ScoreWeights(ContractModel):
    speed: Literal[30] = 30
    operational_package_impact: Literal[30] = 30
    risk: Literal[30] = 30
    cost: Literal[10] = 10


class CandidateScoringInput(ContractModel):
    option_id: NonEmptyString
    return_to_service_hours: float | None = Field(default=None, ge=0.0)
    impact_level: ImpactLevel | None
    total_package_count: int | None = Field(default=None, ge=0)
    priority_package_count: int | None = Field(default=None, ge=0)
    unprotected_package_count: int | None = Field(default=None, ge=0)
    unprotected_priority_package_count: int | None = Field(default=None, ge=0)
    maintenance_risk_levels: tuple[MaintenanceRiskLevel, ...]
    risk_factors: tuple[NonEmptyString, ...]
    repair_labor_cost_usd: NonNegativeUsd | None
    part_and_sourcing_cost_usd: NonNegativeUsd | None
    operations_cost_usd: NonNegativeUsd | None
    affected_flight_numbers: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def require_consistent_package_counts(self) -> CandidateScoringInput:
        counts = (
            self.total_package_count,
            self.priority_package_count,
            self.unprotected_package_count,
            self.unprotected_priority_package_count,
        )
        if any(value is not None for value in counts) and any(value is None for value in counts):
            raise ValueError("package scoring counts must be supplied together")
        if all(value is not None for value in counts):
            assert self.total_package_count is not None
            assert self.priority_package_count is not None
            assert self.unprotected_package_count is not None
            assert self.unprotected_priority_package_count is not None
            if self.priority_package_count > self.total_package_count:
                raise ValueError("priority package count cannot exceed total packages")
            if self.unprotected_package_count > self.total_package_count:
                raise ValueError("unprotected package count cannot exceed total packages")
            if self.unprotected_priority_package_count > min(
                self.priority_package_count, self.unprotected_package_count
            ):
                raise ValueError("unprotected priority count exceeds its package counts")
        return self


class CandidateAssessment(ContractModel):
    option_id: NonEmptyString
    kind: RecoveryOptionKind
    description: NonEmptyString
    sourcing_method: SourcingMethod | None
    return_to_service_hours: float | None = Field(default=None, ge=0.0)
    estimated_cost_usd: NonNegativeUsd | None
    evidence_references: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]
    risks: tuple[NonEmptyString, ...]
    compliance_eligible: bool
    exclusion_reasons: tuple[NonEmptyString, ...]
    score_factors: ScoreFactors | None
    score_weights: ScoreWeights | None = None
    aggregate_score: Score | None
    trade_off: NonEmptyString | None
    sourcing_source: NonEmptyString | None = None
    sourcing_location: NonEmptyString | None = None
    sourcing_lead_time_hours: float | None = Field(default=None, ge=0.0)
    affected_flight_numbers: tuple[NonEmptyString, ...] = ()
    affected_package_count: int | None = Field(default=None, ge=0)
    priority_package_count: int | None = Field(default=None, ge=0)
    unprotected_package_count: int | None = Field(default=None, ge=0)
    main_risk: NonEmptyString | None = None

    @model_validator(mode="after")
    def require_compliance_and_score_consistency(self) -> CandidateAssessment:
        if self.compliance_eligible and self.exclusion_reasons:
            raise ValueError("eligible candidate must not have exclusion reasons")
        if not self.compliance_eligible and not self.exclusion_reasons:
            raise ValueError("excluded candidate requires a reason")
        if self.compliance_eligible and (self.score_factors is None) != (
            self.aggregate_score is None
        ):
            raise ValueError("score factors and aggregate score must be supplied together")
        if not self.compliance_eligible and (
            self.score_factors is not None or self.aggregate_score is not None
        ):
            raise ValueError("excluded candidate must not be scored")
        return self


class CandidateBuildContext(ContractModel):
    schema_version: Literal["1.0"]
    case: AogCase
    request_id: NonEmptyString
    evaluated_at: datetime
    failed_part_number: NonEmptyString
    preferred_replacement_part: NonEmptyString | None
    estimated_repair_duration_hours: float | None = Field(default=None, ge=0.0)
    maintenance_evidence_references: tuple[NonEmptyString, ...]
    materials_assessment: MaterialsLogisticsAssessmentPayload | None

    @field_validator("evaluated_at")
    @classmethod
    def require_timezone_aware_evaluation_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class RecoveryCandidatePlan(ContractModel):
    option: CandidateOption
    part_number: NonEmptyString | None
    inventory_records: tuple[PartAvailabilityRecord, ...]
    eligibility: PartEligibilityEvidence | None
    sourcing_option: SourcingOption | None
    missing_data: tuple[NonEmptyString, ...]
    warnings: tuple[NonEmptyString, ...]


class RankedOption(ContractModel):
    rank: Annotated[int, Field(ge=1)]
    assessment: CandidateAssessment

    @model_validator(mode="after")
    def require_ranked_candidate(self) -> RankedOption:
        if not self.assessment.compliance_eligible or self.assessment.aggregate_score is None:
            raise ValueError("ranked option must be eligible and scored")
        return self


class ExcludedOption(ContractModel):
    option_id: NonEmptyString
    kind: RecoveryOptionKind
    reasons: tuple[NonEmptyString, ...] = Field(min_length=1)
    evidence_references: tuple[NonEmptyString, ...]


class ComplianceGateResult(ContractModel):
    eligible_candidates: tuple[RecoveryCandidatePlan, ...]
    excluded_options: tuple[ExcludedOption, ...]


class ScoringResult(ContractModel):
    weights: ScoreWeights
    ranked_options: tuple[RankedOption, ...]
    excluded_options: tuple[ExcludedOption, ...]
    unscored_options: tuple[UnscoredOption, ...]
    close_score_option_ids: tuple[NonEmptyString, ...]
    human_selection_required: bool


class UnscoredOption(ContractModel):
    option_id: NonEmptyString
    missing_data: tuple[NonEmptyString, ...] = Field(min_length=1)


class ControllerDecisionBrief(ContractModel):
    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    recommendation_version: NonEmptyString
    status: ControllerWorkflowStatus
    summary: NonEmptyString
    relevant_agents: tuple[NonEmptyString, ...]
    key_findings: tuple[NonEmptyString, ...]
    ranked_options: tuple[RankedOption, ...]
    excluded_options: tuple[ExcludedOption, ...]
    recommended_option_id: NonEmptyString | None
    recommendation_rationale: NonEmptyString
    confidence: Confidence
    confidence_disposition: ConfidenceDisposition
    assumptions: tuple[NonEmptyString, ...]
    risks: tuple[NonEmptyString, ...]
    warnings: tuple[NonEmptyString, ...]
    missing_data: tuple[NonEmptyString, ...]
    human_approval_required: Literal[True]
    next_action: NonEmptyString
    aircraft_id: NonEmptyString | None = None
    case_summary: str | None = None
    location: NonEmptyString | None = None

    @model_validator(mode="after")
    def require_recommendation_in_ranked_options(self) -> ControllerDecisionBrief:
        ranked_ids = {item.assessment.option_id for item in self.ranked_options}
        if self.recommended_option_id is not None and self.recommended_option_id not in ranked_ids:
            raise ValueError("recommended option must appear in ranked options")
        if self.status in {ControllerWorkflowStatus.PARTIAL, ControllerWorkflowStatus.ESCALATED}:
            if not self.warnings and not self.missing_data:
                raise ValueError("partial or escalated brief requires a warning or missing data")
        return self


class ControllerCandidateExecution(ContractModel):
    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    candidate_option_id: NonEmptyString
    status: ControllerWorkflowStatus
    maintenance_result: AgentResult | None
    materials_result: AgentResult | None
    peer_exchange: H3H4Exchange | None
    peer_recording: ExchangeRecordingResult | None
    operations_outcome: OperationsOutcome | None
    validation_findings: tuple[ValidationFinding, ...]
    missing_data: tuple[NonEmptyString, ...]
    warnings: tuple[EvidenceWarning, ...]
    specialist_conflicts: tuple[NonEmptyString, ...]
    conflicts: tuple[EvidenceConflict, ...]
    unknowns: tuple[Unknown, ...]
    errors: tuple[StructuredError, ...]

    @model_validator(mode="after")
    def require_complete_execution_components(self) -> ControllerCandidateExecution:
        if self.status is ControllerWorkflowStatus.COMPLETE and any(
            value is None
            for value in (
                self.maintenance_result,
                self.materials_result,
                self.peer_exchange,
                self.peer_recording,
                self.operations_outcome,
            )
        ):
            raise ValueError("complete candidate execution requires all specialist results")
        return self
