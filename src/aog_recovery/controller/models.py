"""Versioned Controller workflow contracts (ARD-DAT-001..011, ARD-CTL-001/006/010)."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import AgentResult, AgentRole, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceConflict, EvidenceWarning, Unknown
from aog_recovery.contracts.governance import HumanDecisionRecord
from aog_recovery.contracts.readiness import ReadinessEstimate
from aog_recovery.contracts.readiness import SourcingMethod as CandidateSourcingMethod
from aog_recovery.coordination.recording import ExchangeRecordingResult
from aog_recovery.maintenance.models import MaintenanceRiskMetrics
from aog_recovery.materials_logistics.models import SourcingOption
from aog_recovery.operations.models import (
    CandidateOption,
    CapacityReservation,
    ImpactLevel,
    OperationsOutcome,
    OptionKind,
    PackageLoadData,
    PackageOutcome,
    ReroutePolicy,
    RouteConflict,
)
from aog_recovery.validation.confidence import ConfidenceAssessment
from aog_recovery.validation.human_gate import HumanGateAssessment, HumanGateStatus

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ScoreValue = Annotated[Decimal, Field(ge=Decimal("0"), le=Decimal("100"))]
NonNegativeUsd = Annotated[Decimal, Field(ge=Decimal("0"))]


class WorkflowStatus(StrEnum):
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    PARTIAL = "partial"
    PROVISIONAL = "provisional"
    ESCALATION_REQUIRED = "escalation_required"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    FAILED = "failed"


class SourceHealthStatus(StrEnum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


class SourceHealthRecord(ContractModel):
    """One source's observed health and evidence (ARD-CTL-003..004, ARD-DAT-009..010)."""

    source_id: NonEmptyString
    agent_role: AgentRole | None = None
    status: SourceHealthStatus
    checked_at: datetime
    evidence_references: tuple[NonEmptyString, ...]
    reason: NonEmptyString | None = None

    @field_validator("checked_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_reason_for_degraded_source(self) -> SourceHealthRecord:
        if self.status is not SourceHealthStatus.AVAILABLE and self.reason is None:
            raise ValueError("degraded source health requires a reason")
        return self


class RoutingOmission(ContractModel):
    """A specialist omitted from routing with an explicit reason (ARD-CTL-003..004)."""

    agent_role: AgentRole
    reason: NonEmptyString

    @model_validator(mode="after")
    def reject_controller_role(self) -> RoutingOmission:
        if self.agent_role is AgentRole.CONTROLLER:
            raise ValueError("Controller cannot be an omitted specialist")
        return self


class RoutingDecision(ContractModel):
    """Deterministic selected and omitted specialist record (ARD-CTL-003..004)."""

    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    selected_roles: tuple[AgentRole, ...]
    omitted_roles: tuple[RoutingOmission, ...]
    source_health: tuple[SourceHealthRecord, ...]
    rationale: tuple[NonEmptyString, ...]

    @model_validator(mode="after")
    def require_unique_specialist_roles(self) -> RoutingDecision:
        if AgentRole.CONTROLLER in self.selected_roles:
            raise ValueError("Controller cannot be selected as a specialist")
        if len(set(self.selected_roles)) != len(self.selected_roles):
            raise ValueError("selected specialist roles must be unique")
        omitted = tuple(item.agent_role for item in self.omitted_roles)
        if len(set(omitted)) != len(omitted):
            raise ValueError("omitted specialist roles must be unique")
        if set(self.selected_roles).intersection(omitted):
            raise ValueError("a specialist cannot be both selected and omitted")
        required_roles = {
            AgentRole.MAINTENANCE,
            AgentRole.MATERIALS_LOGISTICS,
            AgentRole.OPERATIONS,
        }
        if set(self.selected_roles).union(omitted) != required_roles:
            raise ValueError("routing must account for every specialist role")
        health_keys = tuple((item.source_id, item.agent_role) for item in self.source_health)
        if len(set(health_keys)) != len(health_keys):
            raise ValueError("source-health records must be unique by source and agent role")
        return self


class CandidateSource(ContractModel):
    """Typed source inputs for one candidate (ARD-CTL-018, ARD-DAT-012)."""

    source_key: NonEmptyString
    kind: OptionKind
    failed_part_number: NonEmptyString | None = None
    source_evidence_references: tuple[NonEmptyString, ...] = Field(min_length=1)
    readiness: ReadinessEstimate | None = None
    sourcing_options: tuple[SourcingOption, ...] = ()
    package_load: PackageLoadData | None = None
    package_load_evidence_references: tuple[NonEmptyString, ...] = ()
    maintenance_assessment_input: dict[str, object] | None = None
    materials_logistics_assessment_input: dict[str, object] | None = None

    @model_validator(mode="after")
    def require_package_load_provenance(self) -> CandidateSource:
        if self.package_load is not None and not self.package_load_evidence_references:
            raise ValueError("package_load requires evidence references")
        return self


class ControllerIntake(ContractModel):
    """Validated case and source evidence input (ARD-DAT-001..003, ARD-CTL-001)."""

    schema_version: Literal["1.0"]
    case: AogCase
    evidence: tuple[Evidence, ...]
    source_health: tuple[SourceHealthRecord, ...] = ()
    candidate_sources: tuple[CandidateSource, ...] = ()
    affected_flight_numbers: tuple[NonEmptyString, ...] = ()
    reroute_policy: ReroutePolicy = Field(default_factory=ReroutePolicy)
    reserved_capacity: tuple[CapacityReservation, ...] = ()

    @model_validator(mode="after")
    def require_referenced_candidate_evidence(self) -> ControllerIntake:
        evidence_ids = {item.evidence_id for item in self.evidence}
        source_keys = tuple(item.source_key for item in self.candidate_sources)
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("candidate source keys must be unique")
        for index, source in enumerate(self.candidate_sources):
            references = set(source.source_evidence_references)
            if source.readiness is not None:
                references.update(source.readiness.evidence_references)
            for option in source.sourcing_options:
                references.update(option.evidence_references)
            references.update(source.package_load_evidence_references)
            missing = sorted(references.difference(evidence_ids))
            if missing:
                raise ValueError(
                    f"candidate_sources[{index}] references unavailable evidence: "
                    f"{', '.join(missing)}"
                )
        return self


class PerCandidateResult(ContractModel):
    """Candidate-scoped specialist outcomes and degradation (ARD-CTL-006/008/018)."""

    candidate: CandidateOption
    candidate_source: CandidateSource
    maintenance_result: AgentResult | None
    materials_logistics_result: AgentResult | None
    operations_result: OperationsOutcome | None
    peer_exchange_recording: ExchangeRecordingResult | None
    confidence: ConfidenceAssessment | None
    status: WorkflowStatus
    evidence: tuple[Evidence, ...]
    warnings: tuple[EvidenceWarning, ...]
    conflicts: tuple[EvidenceConflict, ...]
    unknowns: tuple[Unknown, ...]
    missing_data: tuple[NonEmptyString, ...]
    errors: tuple[StructuredError, ...]
    operations_conflicts: tuple[RouteConflict, ...] = ()

    @model_validator(mode="after")
    def require_role_specific_results(self) -> PerCandidateResult:
        if (
            self.maintenance_result is not None
            and self.maintenance_result.agent_role is not AgentRole.MAINTENANCE
        ):
            raise ValueError("maintenance_result must be from Maintenance")
        if (
            self.materials_logistics_result is not None
            and self.materials_logistics_result.agent_role is not AgentRole.MATERIALS_LOGISTICS
        ):
            raise ValueError("materials_logistics_result must be from Materials & Logistics")
        if (
            self.operations_result is not None
            and self.operations_result.result.agent_role is not AgentRole.OPERATIONS
        ):
            raise ValueError("operations_result must be from Operations")
        return self


class CandidateHandoff(ContractModel):
    """Candidate eligibility and exclusions without a score or rank (ARD-CTL-017..018)."""

    result: PerCandidateResult
    eligible: bool
    exclusion_reasons: tuple[NonEmptyString, ...]

    @model_validator(mode="after")
    def require_exclusion_reason(self) -> CandidateHandoff:
        if self.eligible and self.exclusion_reasons:
            raise ValueError("eligible candidate cannot have exclusion reasons")
        if not self.eligible and not self.exclusion_reasons:
            raise ValueError("ineligible candidate requires an exclusion reason")
        return self


class UnrankedHandoff(ContractModel):
    """Advisory handoff that remains pending human decision (ARD-CTL-010/017..018)."""

    schema_version: Literal["1.0"]
    case: AogCase
    status: WorkflowStatus
    candidates: tuple[CandidateHandoff, ...]
    confidence: ConfidenceAssessment
    human_gate: HumanGateAssessment
    evidence: tuple[Evidence, ...]
    warnings: tuple[EvidenceWarning, ...]
    conflicts: tuple[EvidenceConflict, ...]
    unknowns: tuple[Unknown, ...]
    missing_data: tuple[NonEmptyString, ...]
    errors: tuple[StructuredError, ...]
    operations_conflicts: tuple[RouteConflict, ...] = ()
    routing: RoutingDecision | None = None

    @model_validator(mode="after")
    def require_pending_human_gate_and_unique_candidates(self) -> UnrankedHandoff:
        if self.human_gate.status is not HumanGateStatus.PENDING:
            raise ValueError("orchestration handoff must remain pending human decision")
        if self.routing is not None and self.routing.case_id != self.case.case_id:
            raise ValueError("handoff routing case_id must match the AOG case")
        option_ids = tuple(item.result.candidate.option_id for item in self.candidates)
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("candidate option_id values must be unique")
        return self


class RecommendationStatus(StrEnum):
    RECOMMENDED = "recommended"
    PROVISIONAL = "provisional"
    REQUIRES_ESCALATION = "requires_escalation"
    REJECTED = "rejected"
    AWAITING_ADDITIONAL_DATA = "awaiting_additional_data"
    RESOLVED = "resolved"


class RecommendationWeights(ContractModel):
    speed: Decimal = Decimal("0.30")
    operational_package_impact: Decimal = Decimal("0.30")
    risk: Decimal = Decimal("0.30")
    cost: Decimal = Decimal("0.10")

    @model_validator(mode="after")
    def require_ard_baseline(self) -> RecommendationWeights:
        expected = (Decimal("0.30"), Decimal("0.30"), Decimal("0.30"), Decimal("0.10"))
        if (
            self.speed,
            self.operational_package_impact,
            self.risk,
            self.cost,
        ) != expected:
            raise ValueError("recommendation weights must use the ARD 30/30/30/10 baseline")
        return self


class RecommendationFactorScores(ContractModel):
    speed: ScoreValue
    operational_package_impact: ScoreValue
    risk: ScoreValue
    cost: ScoreValue


class RecommendationCostBreakdown(ContractModel):
    repair_labor_usd: NonNegativeUsd
    sourcing_usd: NonNegativeUsd
    operations_usd: NonNegativeUsd
    total_usd: NonNegativeUsd

    @model_validator(mode="after")
    def require_total(self) -> RecommendationCostBreakdown:
        if self.total_usd != self.repair_labor_usd + self.sourcing_usd + self.operations_usd:
            raise ValueError("total_usd must equal the sum of cost components")
        return self


class ScoredRecoveryOption(ContractModel):
    option_id: NonEmptyString
    kind: OptionKind
    description: NonEmptyString
    sourcing_method: CandidateSourcingMethod | None
    readiness_eta: datetime
    affected_routes: tuple[NonEmptyString, ...]
    impact_level: ImpactLevel
    schedule_delay_minutes: Annotated[int, Field(ge=0)] | None
    package: PackageOutcome
    maintenance_risk_metrics: MaintenanceRiskMetrics
    technical_risks: tuple[NonEmptyString, ...]
    operational_risks: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]
    factor_scores: RecommendationFactorScores
    aggregate_score: ScoreValue
    cost: RecommendationCostBreakdown
    evidence_references: tuple[NonEmptyString, ...] = Field(min_length=1)
    trade_off: NonEmptyString


class RankedRecoveryOption(ScoredRecoveryOption):
    rank: Annotated[int, Field(gt=0)]
    selection_group: Annotated[int, Field(gt=0)] | None = None


class ExcludedRecoveryOption(ContractModel):
    option_id: NonEmptyString
    kind: OptionKind
    description: NonEmptyString
    exclusion_reasons: tuple[NonEmptyString, ...] = Field(min_length=1)
    evidence_references: tuple[NonEmptyString, ...] = ()


class UnscoredRecoveryOption(ContractModel):
    option_id: NonEmptyString
    kind: OptionKind
    description: NonEmptyString
    reasons: tuple[NonEmptyString, ...] = Field(min_length=1)
    evidence_references: tuple[NonEmptyString, ...] = ()


class RecoveryDecisionBrief(ContractModel):
    """Versioned, advisory Controller report for human recovery selection."""

    schema_version: Literal["1.0"]
    recommendation_version: NonEmptyString
    scoring_algorithm_version: NonEmptyString
    case_id: NonEmptyString
    trace_context: TraceContext
    status: RecommendationStatus
    summary: NonEmptyString
    ranked_options: tuple[RankedRecoveryOption, ...]
    excluded_options: tuple[ExcludedRecoveryOption, ...]
    unscored_options: tuple[UnscoredRecoveryOption, ...]
    weights: RecommendationWeights
    confidence: ConfidenceAssessment
    human_gate: HumanGateAssessment
    requires_human_selection: bool
    required_human_action: NonEmptyString
    assumptions: tuple[NonEmptyString, ...]
    risks: tuple[NonEmptyString, ...]
    warnings: tuple[EvidenceWarning, ...]
    conflicts: tuple[EvidenceConflict, ...]
    unknowns: tuple[Unknown, ...]
    missing_data: tuple[NonEmptyString, ...]
    errors: tuple[StructuredError, ...]
    human_decisions: tuple[HumanDecisionRecord, ...] = ()

    @model_validator(mode="after")
    def require_unique_option_ids_and_ranks(self) -> RecoveryDecisionBrief:
        option_ids = (
            *(item.option_id for item in self.ranked_options),
            *(item.option_id for item in self.excluded_options),
            *(item.option_id for item in self.unscored_options),
        )
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("recommendation option IDs must be unique")
        ranks = tuple(item.rank for item in self.ranked_options)
        if len(set(ranks)) != len(ranks):
            raise ValueError("ranked option ranks must be unique")
        decision_ids = tuple(item.decision_id for item in self.human_decisions)
        if len(set(decision_ids)) != len(decision_ids):
            raise ValueError("human decision IDs must be unique")
        return self
