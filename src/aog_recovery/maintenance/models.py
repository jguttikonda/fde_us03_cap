"""Maintenance specialist payloads (ARD-MNT-003..010, ARD-DAT-004..006)."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import Evidence
from aog_recovery.validation.models import ValidationFinding

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeHours = Annotated[float, Field(ge=0.0)]
NonNegativeUsd = Annotated[Decimal, Field(ge=Decimal("0"))]


class RepairabilityStatus(StrEnum):
    FEASIBLE = "feasible"
    UNCERTAIN = "uncertain"
    NOT_FEASIBLE = "not_feasible"


class ApprovalEvidenceStatus(StrEnum):
    APPROVAL_RECORDED = "approval_recorded"
    PENDING = "pending"
    NOT_APPROVED = "not_approved"
    UNKNOWN = "unknown"


class MaintenanceRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class EngineeringApprovalEvidence(ContractModel):
    status: ApprovalEvidenceStatus
    approver_role: NonEmptyString | None
    source_reference: NonEmptyString | None
    recorded_at: datetime | None

    @field_validator("recorded_at")
    @classmethod
    def require_timezone_for_recorded_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_provenance_for_recorded_approval(self) -> EngineeringApprovalEvidence:
        if self.status is ApprovalEvidenceStatus.APPROVAL_RECORDED and (
            self.approver_role is None or self.source_reference is None or self.recorded_at is None
        ):
            raise ValueError("recorded approval requires role, source, and timestamp")
        return self


class RootCauseEvidence(ContractModel):
    category: NonEmptyString
    confidence: Confidence
    evidence_references: tuple[NonEmptyString, ...] = Field(min_length=1)


class RecurringFailureSummary(ContractModel):
    part_number: NonEmptyString
    occurrences: Annotated[int, Field(ge=0)]
    window_days: Annotated[int, Field(gt=0)]
    evidence_references: tuple[NonEmptyString, ...]

    @model_validator(mode="after")
    def require_sources_for_observed_failures(self) -> RecurringFailureSummary:
        if self.occurrences > 0 and not self.evidence_references:
            raise ValueError("observed failures require evidence references")
        return self


class MaintenanceFailureOccurrence(ContractModel):
    part_number: NonEmptyString
    occurred_at: datetime
    evidence_reference: NonEmptyString

    @field_validator("occurred_at")
    @classmethod
    def require_timezone_for_occurrence(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class RecurringFailureAnalysis(ContractModel):
    summaries: tuple[RecurringFailureSummary, ...]
    findings: tuple[ValidationFinding, ...]


class MaintenanceRiskMetrics(ContractModel):
    delay_risk: MaintenanceRiskLevel
    parts_dependency_risk: MaintenanceRiskLevel
    repair_complexity_risk: MaintenanceRiskLevel


class MaintenanceRecommendationDecision(StrEnum):
    REPAIR = "repair"
    DEFER = "defer"
    ESCALATE = "escalate"
    UNCERTAIN = "uncertain"


class MaintenanceRecommendation(ContractModel):
    decision: MaintenanceRecommendationDecision
    confidence: Confidence
    rationale: NonEmptyString
    next_steps: tuple[NonEmptyString, ...]


class MaintenanceEvidenceGrounding(ContractModel):
    schema_version: Literal["1.0"]
    evidence_references: tuple[NonEmptyString, ...]
    missing_data: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]
    confidence: Confidence


class MaintenanceFailurePayload(ContractModel):
    schema_version: Literal["1.0"]
    error_category: NonEmptyString
    message: NonEmptyString
    missing_data: tuple[NonEmptyString, ...]
    findings: tuple[ValidationFinding, ...]


class MaintenanceAssessmentPayload(ContractModel):
    schema_version: Literal["1.0"]
    repairability_status: RepairabilityStatus
    root_cause: RootCauseEvidence | None
    recurring_failure: RecurringFailureSummary | None
    preferred_replacement_part: NonEmptyString | None
    preferred_replacement_evidence_references: tuple[NonEmptyString, ...]
    required_actions: tuple[NonEmptyString, ...]
    estimated_ground_time_hours: NonNegativeHours | None
    ground_time_unavailable_reason: NonEmptyString | None
    estimated_repair_labor_cost_usd: NonNegativeUsd | None
    need_by_time: datetime | None
    parts_ready_at: datetime | None
    return_to_service_time: datetime | None
    meets_need_by_time: bool | None
    eta_confidence: Confidence
    risk_metrics: MaintenanceRiskMetrics
    technical_risks: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]
    missing_data: tuple[NonEmptyString, ...]
    warnings: tuple[NonEmptyString, ...]
    approval_evidence: EngineeringApprovalEvidence
    recommendation: MaintenanceRecommendation

    @field_validator("need_by_time", "parts_ready_at", "return_to_service_time")
    @classmethod
    def require_timezone_for_estimates(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def explain_missing_ground_time(self) -> MaintenanceAssessmentPayload:
        if self.estimated_ground_time_hours is None and self.ground_time_unavailable_reason is None:
            raise ValueError("an unsupported ground-time estimate requires a reason")
        if self.repairability_status is RepairabilityStatus.FEASIBLE and (
            self.approval_evidence.status is not ApprovalEvidenceStatus.APPROVAL_RECORDED
        ):
            raise ValueError("a feasible disposition requires recorded approval evidence")
        if (
            self.preferred_replacement_part is not None
            and not self.preferred_replacement_evidence_references
        ):
            raise ValueError("a preferred replacement requires supporting evidence")
        if self.recommendation.decision is MaintenanceRecommendationDecision.REPAIR and (
            self.repairability_status is not RepairabilityStatus.FEASIBLE
            or self.approval_evidence.status is not ApprovalEvidenceStatus.APPROVAL_RECORDED
        ):
            raise ValueError("repair recommendation requires feasible status and approval evidence")
        return self


class WorkOrderStatus(StrEnum):
    OPEN = "open"
    COMPLETE = "complete"
    UNKNOWN = "unknown"


class MaintenanceWorkOrder(ContractModel):
    work_order_id: NonEmptyString
    aircraft_id: NonEmptyString
    status: WorkOrderStatus
    required_actions: tuple[NonEmptyString, ...]
    estimated_repair_duration_hours: NonNegativeHours | None
    evidence: Evidence


class MaintenancePartDependency(ContractModel):
    part_number: NonEmptyString
    required_quantity: Annotated[int, Field(ge=1)]
    required_before_repair: bool
    evidence_references: tuple[NonEmptyString, ...]


class MaintenanceAssessmentInput(ContractModel):
    schema_version: Literal["1.0"]
    case: AogCase
    need_by_time: datetime | None = None
    need_by_evidence_reference: NonEmptyString | None = None
    parts_ready_at: datetime | None = None
    parts_readiness_evidence_reference: NonEmptyString | None = None
    aircraft_metadata: Evidence | None
    work_order: MaintenanceWorkOrder | None
    maintenance_history: tuple[Evidence, ...]
    engineering_constraints: tuple[Evidence, ...]
    safety_conditions: tuple[Evidence, ...]
    part_dependencies: tuple[MaintenancePartDependency, ...]
    missing_data: tuple[NonEmptyString, ...]

    @field_validator("need_by_time", "parts_ready_at")
    @classmethod
    def require_timezone_for_timing_inputs(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_case_consistency(self) -> MaintenanceAssessmentInput:
        if self.work_order is not None and self.work_order.aircraft_id != self.case.aircraft_id:
            raise ValueError("work-order aircraft_id must match the AOG case")
        metadata_aircraft_id = (
            self.aircraft_metadata.content.get("aircraft_id")
            if self.aircraft_metadata is not None
            else None
        )
        if metadata_aircraft_id is not None and metadata_aircraft_id != self.case.aircraft_id:
            raise ValueError("aircraft metadata aircraft_id must match the AOG case")
        if self.parts_ready_at is not None and self.parts_readiness_evidence_reference is None:
            raise ValueError("parts-ready time requires a source evidence reference")
        if self.need_by_time is not None and self.need_by_evidence_reference is None:
            raise ValueError("need-by time requires a source evidence reference")
        return self


class MaintenanceInputStatus(StrEnum):
    READY = "ready"
    PROVISIONAL = "provisional"
    REJECTED = "rejected"


class MaintenanceInputReport(ContractModel):
    status: MaintenanceInputStatus
    validated_input: MaintenanceAssessmentInput | None
    missing_data: tuple[NonEmptyString, ...]
    findings: tuple[ValidationFinding, ...]
