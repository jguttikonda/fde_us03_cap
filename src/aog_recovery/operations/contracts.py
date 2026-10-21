from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import Assumption

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
NonNegativeCount = Annotated[int, Field(ge=0)]


class RecoveryOptionKind(StrEnum):
    REPAIR = "repair"
    SWAP = "swap"
    DELAY = "delay"


class EvidenceState(StrEnum):
    CURRENT = "current"
    PARTIAL = "partial"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


class OperationsToolName(StrEnum):
    VALIDATE_FLIGHT_SCHEDULE = "validate_flight_schedule"
    DETECT_ROUTE_CONFLICTS = "detect_route_conflicts"
    CHECK_FLEET_AVAILABILITY = "check_fleet_availability"
    APPLY_DISRUPTION_THRESHOLDS = "apply_disruption_thresholds"
    CHECK_LOAD_REDISTRIBUTION = "check_load_redistribution"


class AssessmentStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    PROVISIONAL = "provisional"
    ESCALATION_REQUIRED = "escalation_required"
    FAILED = "failed"


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OperationsEvidence(ContractModel):
    evidence_id: NonEmptyString
    source: NonEmptyString
    observed_at: datetime | None
    state: EvidenceState
    subject: NonEmptyString
    value: dict[str, object] | None

    @field_validator("observed_at")
    @classmethod
    def require_timezone_aware_observation(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def require_value_for_usable_evidence(self) -> OperationsEvidence:
        if self.state in {EvidenceState.CURRENT, EvidenceState.PARTIAL} and self.value is None:
            raise ValueError("current or partial evidence requires a value")
        if self.state is EvidenceState.CONFLICTING and self.value is None:
            raise ValueError("conflicting evidence requires its observed value")
        return self


class RecoveryCandidate(ContractModel):
    option_id: NonEmptyString
    kind: RecoveryOptionKind
    description: NonEmptyString
    repair_eta: datetime | None = None
    substitute_tail_id: NonEmptyString | None = None
    delay_minutes: Annotated[int, Field(gt=0)] | None = None
    evidence_references: tuple[NonEmptyString, ...] = ()
    assumptions: tuple[Assumption, ...] = ()

    @field_validator("repair_eta")
    @classmethod
    def require_timezone_aware_eta(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("repair_eta must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_candidate_fields(self) -> RecoveryCandidate:
        if self.kind is RecoveryOptionKind.REPAIR and self.repair_eta is None:
            raise ValueError("repair candidates require repair_eta")
        if self.kind is not RecoveryOptionKind.REPAIR and self.repair_eta is not None:
            raise ValueError("repair_eta is only valid for repair candidates")
        if self.kind is RecoveryOptionKind.SWAP and self.substitute_tail_id is None:
            raise ValueError("swap candidates require substitute_tail_id")
        if self.kind is not RecoveryOptionKind.SWAP and self.substitute_tail_id is not None:
            raise ValueError("substitute_tail_id is only valid for swap candidates")
        if self.kind is RecoveryOptionKind.DELAY and self.delay_minutes is None:
            raise ValueError("delay candidates require delay_minutes")
        if self.kind is RecoveryOptionKind.REPAIR and self.delay_minutes is not None:
            raise ValueError("delay_minutes is not valid for repair candidates")
        return self


class OperationsAdapterRequest(ContractModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case_id: NonEmptyString
    trace_context: TraceContext
    tool_name: OperationsToolName
    requested_at: datetime
    parameters: dict[str, object]
    access_mode: Literal["read"]

    @field_validator("requested_at")
    @classmethod
    def require_timezone_aware_request(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must include a timezone")
        return value


class OperationsRequest(ContractModel):
    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    trace_context: TraceContext
    affected_flight_ids: tuple[NonEmptyString, ...] = Field(min_length=1)
    candidates: tuple[RecoveryCandidate, ...] = Field(min_length=1)
    evidence_references: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def require_unique_identifiers(self) -> OperationsRequest:
        if len(set(self.affected_flight_ids)) != len(self.affected_flight_ids):
            raise ValueError("affected_flight_ids must be unique")
        option_ids = tuple(candidate.option_id for candidate in self.candidates)
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("candidate option_id values must be unique")
        return self


class AdapterReadResult(ContractModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case_id: NonEmptyString
    trace_context: TraceContext
    tool_name: OperationsToolName
    source: NonEmptyString
    observed_at: datetime | None
    state: EvidenceState
    data: dict[str, object] | None
    error: StructuredError | None

    @field_validator("observed_at")
    @classmethod
    def require_timezone_aware_observation(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_result_shape(self) -> AdapterReadResult:
        if self.state in {EvidenceState.CURRENT, EvidenceState.PARTIAL} and self.data is None:
            raise ValueError("current or partial adapter results require data")
        if self.state is EvidenceState.UNAVAILABLE and self.error is None:
            raise ValueError("unavailable adapter results require a structured error")
        if self.error is not None and self.state is not EvidenceState.UNAVAILABLE:
            raise ValueError("adapter errors must have unavailable state")
        return self


class PackageServiceCount(ContractModel):
    service_level: NonEmptyString
    package_count: NonNegativeCount


class TailPackageAllocation(ContractModel):
    tail_id: NonEmptyString
    capacity: NonNegativeCount
    package_count: NonNegativeCount
    packages_by_service_level: tuple[PackageServiceCount, ...]

    @model_validator(mode="after")
    def allocation_within_capacity(self) -> TailPackageAllocation:
        if self.package_count > self.capacity:
            raise ValueError("package allocation exceeds tail capacity")
        if sum(item.package_count for item in self.packages_by_service_level) != self.package_count:
            raise ValueError("service-level allocations must equal package_count")
        return self


class RejectedAllocationTarget(ContractModel):
    tail_id: NonEmptyString
    reason: NonEmptyString


class PackageRedistribution(ContractModel):
    total_package_count: NonNegativeCount
    protected_by_service_level: tuple[PackageServiceCount, ...]
    unprotected_by_service_level: tuple[PackageServiceCount, ...]
    allocations: tuple[TailPackageAllocation, ...]
    rejected_targets: tuple[RejectedAllocationTarget, ...] = ()

    @model_validator(mode="after")
    def preserve_manifest_counts(self) -> PackageRedistribution:
        protected = sum(item.package_count for item in self.protected_by_service_level)
        unprotected = sum(item.package_count for item in self.unprotected_by_service_level)
        allocated = sum(item.package_count for item in self.allocations)
        if protected + unprotected != self.total_package_count:
            raise ValueError("protected and unprotected counts must equal total_package_count")
        if allocated != protected:
            raise ValueError("tail allocations must equal protected package count")
        allocation_counts: dict[str, int] = {}
        for allocation in self.allocations:
            for item in allocation.packages_by_service_level:
                allocation_counts[item.service_level] = (
                    allocation_counts.get(item.service_level, 0) + item.package_count
                )
        protected_counts = {
            item.service_level: item.package_count for item in self.protected_by_service_level
        }
        if allocation_counts != protected_counts:
            raise ValueError("tail service-level totals must match protected counts")
        protected_levels = tuple(item.service_level for item in self.protected_by_service_level)
        unprotected_levels = tuple(item.service_level for item in self.unprotected_by_service_level)
        if len(set(protected_levels)) != len(protected_levels):
            raise ValueError("protected service levels must be unique")
        if len(set(unprotected_levels)) != len(unprotected_levels):
            raise ValueError("unprotected service levels must be unique")
        if len({item.tail_id for item in self.allocations}) != len(self.allocations):
            raise ValueError("tail allocation entries must have unique tail_id values")
        if len({item.tail_id for item in self.rejected_targets}) != len(self.rejected_targets):
            raise ValueError("rejected target tail_id values must be unique")
        return self


class CostLineItem(ContractModel):
    description: NonEmptyString
    amount: Annotated[Decimal, Field(ge=Decimal("0"))]
    currency: CurrencyCode
    evidence_references: tuple[NonEmptyString, ...] = ()


class CostEstimate(ContractModel):
    total: Annotated[Decimal, Field(ge=Decimal("0"))] | None
    currency: CurrencyCode
    line_items: tuple[CostLineItem, ...]
    unavailable_reason: NonEmptyString | None = None
    missing_evidence: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def validate_cost_availability(self) -> CostEstimate:
        if self.total is None:
            if self.unavailable_reason is None:
                raise ValueError("unavailable cost requires unavailable_reason")
            if not self.missing_evidence:
                raise ValueError("unavailable cost requires missing_evidence")
            if any(item.currency != self.currency for item in self.line_items):
                raise ValueError("all cost line items must use the estimate currency")
        else:
            if self.unavailable_reason is not None or self.missing_evidence:
                raise ValueError("available cost cannot include unavailable markers")
            if any(item.currency != self.currency for item in self.line_items):
                raise ValueError("all cost line items must use the estimate currency")
            if sum((item.amount for item in self.line_items), Decimal("0")) != self.total:
                raise ValueError("cost total must equal the sum of its line items")
        return self


class CustomerServiceImpact(ContractModel):
    service_level: NonEmptyString
    packages_at_risk: NonNegativeCount
    explanation: NonEmptyString
    evidence_references: tuple[NonEmptyString, ...]


class OptionAssessment(ContractModel):
    option_id: NonEmptyString
    kind: RecoveryOptionKind
    feasible: bool | None
    impact_level: ImpactLevel | None
    affected_flight_ids: tuple[NonEmptyString, ...]
    affected_routes: tuple[NonEmptyString, ...]
    delay_minutes: NonNegativeCount | None
    package_redistribution: PackageRedistribution | None
    customer_impacts: tuple[CustomerServiceImpact, ...]
    cost_estimate: CostEstimate
    risks: tuple[NonEmptyString, ...]
    evidence_references: tuple[NonEmptyString, ...]
    assumptions: tuple[Assumption, ...]
    missing_evidence: tuple[NonEmptyString, ...]
    conflict_references: tuple[NonEmptyString, ...]


class OperationsRecommendation(ContractModel):
    preferred_option_id: NonEmptyString | None
    status: Literal["preferred", "provisional", "escalate", "no_preference"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    rationale: NonEmptyString
    next_steps: tuple[NonEmptyString, ...]
    human_approval_required: Literal[True] = True


class OperationsAssessment(ContractModel):
    schema_version: Literal["1.0"]
    case_id: NonEmptyString
    trace_context: TraceContext
    status: AssessmentStatus
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    impact_level: ImpactLevel | None
    option_assessments: tuple[OptionAssessment, ...]
    evidence: tuple[OperationsEvidence, ...]
    assumptions: tuple[Assumption, ...]
    missing_evidence: tuple[NonEmptyString, ...]
    conflicts: tuple[NonEmptyString, ...]
    errors: tuple[StructuredError, ...]
    recommendation: OperationsRecommendation
    summary: NonEmptyString
    tradeoff_notes: tuple[NonEmptyString, ...]
    final_report: Literal[None] = None
    system_ranked_option_ids: Literal[None] = None
