"""Materials & Logistics specialist payloads (ARD-MLG-001..009)."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.evidence import EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeUsd = Annotated[Decimal, Field(ge=Decimal("0"))]
NonNegativeHours = Annotated[float, Field(ge=0.0)]


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"
    UNCERTAIN = "uncertain"


class PartRole(StrEnum):
    FAILED_PART = "failed_part"
    PREFERRED_REPLACEMENT = "preferred_replacement"
    ALTERNATE = "alternate"
    SUBSTITUTE = "substitute"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class AuthorizationStatus(StrEnum):
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class TraceabilityStatus(StrEnum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    UNKNOWN = "unknown"


class SourcingMethod(StrEnum):
    INTERNAL_TRANSFER = "internal_transfer"
    BORROW_POOL = "borrow_pool"
    VENDOR_PURCHASE = "vendor_purchase"
    EXPEDITE = "expedite"


class ShippingProvider(StrEnum):
    FEDEX_NETWORK = "fedex_network"
    COMMERCIAL_CARRIER = "commercial_carrier"


class PartAvailabilityRecord(ContractModel):
    part_number: NonEmptyString
    role: PartRole
    required_quantity: Annotated[int, Field(ge=1)]
    available_quantity: Annotated[int, Field(ge=0)]
    minimum_stock_threshold: Annotated[int, Field(ge=0)] | None = None
    location: NonEmptyString | None
    source: NonEmptyString
    retrieved_at: datetime
    validity_state: EvidenceValidity
    claim_reference: NonEmptyString

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone_for_retrieval(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class PartEligibilityEvidence(ContractModel):
    part_number: NonEmptyString
    compatibility: CompatibilityStatus
    authorization: AuthorizationStatus
    traceability: TraceabilityStatus
    checked_by_role: NonEmptyString | None
    evidence_references: tuple[NonEmptyString, ...]

    @model_validator(mode="after")
    def require_sources_for_known_eligibility(self) -> PartEligibilityEvidence:
        has_known_status = any(
            status is not unknown
            for status, unknown in (
                (self.compatibility, CompatibilityStatus.UNKNOWN),
                (self.authorization, AuthorizationStatus.UNKNOWN),
                (self.traceability, TraceabilityStatus.UNKNOWN),
            )
        )
        if has_known_status and not self.evidence_references:
            raise ValueError("known eligibility states require evidence references")
        return self


class SourcingOption(ContractModel):
    part_number: NonEmptyString
    source: NonEmptyString
    source_location: NonEmptyString | None
    method: SourcingMethod
    shipping_provider: ShippingProvider | None
    shipping_service: NonEmptyString | None
    transfer_required: bool
    lead_time_hours: NonNegativeHours | None
    eta_at: datetime | None
    estimated_cost_usd: NonNegativeUsd | None
    quote_unavailable_reason: NonEmptyString | None
    evidence_references: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...] = ()

    @field_validator("eta_at")
    @classmethod
    def require_timezone_for_eta(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def explain_incomplete_quote(self) -> SourcingOption:
        if (
            any(
                value is None
                for value in (self.lead_time_hours, self.eta_at, self.estimated_cost_usd)
            )
            and self.quote_unavailable_reason is None
        ):
            raise ValueError("missing quote values require an explicit reason")
        if self.shipping_provider is None and self.shipping_service is not None:
            raise ValueError("a shipping service requires a provider")
        return self


class SourcingQuoteInput(ContractModel):
    part_number: NonEmptyString
    source: NonEmptyString
    source_location: NonEmptyString | None
    method: SourcingMethod
    shipping_provider: ShippingProvider | None
    shipping_service: NonEmptyString | None
    transfer_required: bool
    requested_at: datetime
    quantity: Annotated[int, Field(ge=1)]
    unit_cost_usd: NonNegativeUsd | None
    transport_cost_usd: NonNegativeUsd | None
    handling_cost_usd: NonNegativeUsd | None
    lead_time_hours: NonNegativeHours | None
    evidence_references: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]

    @field_validator("requested_at")
    @classmethod
    def require_timezone_for_request_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_provider_for_shipping_service(self) -> SourcingQuoteInput:
        if self.shipping_provider is None and self.shipping_service is not None:
            raise ValueError("a shipping service requires a provider")
        return self


class MaterialsLogisticsAssessmentPayload(ContractModel):
    schema_version: Literal["1.0"]
    availability_status: AvailabilityStatus
    part_availability: tuple[PartAvailabilityRecord, ...]
    part_eligibility: tuple[PartEligibilityEvidence, ...]
    sourcing_options: tuple[SourcingOption, ...]
    confidence: Confidence
    risk_factors: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]
    missing_data: tuple[NonEmptyString, ...]


class PartReadinessAssessment(ContractModel):
    part_number: NonEmptyString
    role: PartRole
    availability_status: AvailabilityStatus
    physically_available: bool
    practical_quantity: Annotated[int, Field(ge=0)] | None
    practically_available: bool | None
    location_consistent: bool | None
    eligible: bool | None
    findings: tuple[NonEmptyString, ...]
    evidence_references: tuple[NonEmptyString, ...]


class MaterialsDeterministicAssessment(ContractModel):
    availability_status: AvailabilityStatus
    parts: tuple[PartReadinessAssessment, ...]


class MaterialsEvidenceSummary(ContractModel):
    status: ToolResultStatus
    confidence: Confidence
    evidence_references: tuple[NonEmptyString, ...]
    warnings: tuple[EvidenceWarning, ...]
    errors: tuple[StructuredError, ...]


class RequestedPartComparison(ContractModel):
    failed_part_number: NonEmptyString
    failed_part_assessments: tuple[PartReadinessAssessment, ...]
    preferred_part_number: NonEmptyString | None
    preferred_part_assessments: tuple[PartReadinessAssessment, ...]
    missing_part_numbers: tuple[NonEmptyString, ...]
