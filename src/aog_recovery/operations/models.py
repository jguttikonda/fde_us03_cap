"""Operations Agent contracts (ARD-OPS-001, ARD-OPS-005, ARD-DAT-001, ARD-DAT-010)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import AgentResult, AgentRole, StructuredError
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import (
    Evidence,
    EvidenceConflict,
    EvidenceWarning,
    Unknown,
)
from aog_recovery.contracts.readiness import EtaBasis as EtaBasis
from aog_recovery.contracts.readiness import ReadinessEstimate, SourcingMethod
from aog_recovery.validation.confidence import ConfidenceAssessment, ConfidenceDisposition

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,39}$")]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


# --- Request ---------------------------------------------------------------------------------


class OptionKind(StrEnum):
    REPAIR_ORIGINAL = "repair_original"
    REPAIR_ALTERNATE = "repair_alternate"
    SWAP = "swap"
    DELAY = "delay"


class CandidateOption(ContractModel):
    option_id: NonEmptyString
    kind: OptionKind
    description: NonEmptyString
    readiness_eta: datetime | None = None
    eta_basis: EtaBasis | None = None
    eta_evidence_references: tuple[NonEmptyString, ...] = ()
    # Pass-through from Materials & Logistics (ARD-CTL-018); Operations does not act on it.
    sourcing_method: SourcingMethod | None = None

    @classmethod
    def with_readiness(
        cls,
        option_id: str,
        kind: OptionKind,
        description: str,
        estimate: ReadinessEstimate,
        sourcing_method: SourcingMethod | None = None,
    ) -> CandidateOption:
        """Build a candidate from the shared estimate Maintenance or M&L supplies."""
        return cls(
            option_id=option_id,
            kind=kind,
            description=description,
            readiness_eta=estimate.eta,
            eta_basis=estimate.basis,
            eta_evidence_references=estimate.evidence_references,
            sourcing_method=sourcing_method,
        )

    @field_validator("readiness_eta")
    @classmethod
    def require_timezone_aware_eta(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_timezone(value)

    @model_validator(mode="after")
    def require_eta_provenance(self) -> CandidateOption:
        if self.readiness_eta is None:
            if self.eta_basis is not None or self.eta_evidence_references:
                raise ValueError("eta basis and references require a readiness_eta")
        elif self.eta_basis is None or not self.eta_evidence_references:
            raise ValueError("readiness_eta requires an eta_basis and eta_evidence_references")
        return self


class ReroutePolicy(ContractModel):
    """Human-set limits on where packages may be rerouted; the agent never books anything."""

    allow_partner_flights: bool = True
    prefer_own_network: bool = True
    max_partner_cost_per_package_usd: NonNegativeInt | None = None


class CapacityReservation(ContractModel):
    """Package capacity on an alternate flight already claimed by another recovery action."""

    flight_number: Identifier
    packages: PositiveInt
    reserved_by: AgentRole
    reference: NonEmptyString


class OperationsRequest(ContractModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    case: AogCase
    affected_flight_numbers: tuple[NonEmptyString, ...] = Field(min_length=1)
    candidates: tuple[CandidateOption, ...] = Field(min_length=1)
    evaluated_at: datetime
    reroute_policy: ReroutePolicy = Field(default_factory=ReroutePolicy)
    reserved_capacity: tuple[CapacityReservation, ...] = ()

    @field_validator("evaluated_at")
    @classmethod
    def require_timezone_aware_evaluation_time(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @model_validator(mode="after")
    def require_unique_identifiers(self) -> OperationsRequest:
        option_ids = [candidate.option_id for candidate in self.candidates]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("candidate option_id values must be unique")
        if len(set(self.affected_flight_numbers)) != len(self.affected_flight_numbers):
            raise ValueError("affected_flight_numbers must be unique")
        return self


# --- Source data (untrusted tool output, validated before use: ARD-SEC-004) -------------------


class CrewCoverage(StrEnum):
    AVAILABLE = "available"
    DELAYED = "delayed"
    GAP = "gap"


class FlightRecord(ContractModel):
    flight_number: Identifier
    route: Identifier
    origin: Identifier
    destination: Identifier
    required_aircraft_type: Identifier
    scheduled_departure: datetime
    scheduled_arrival: datetime
    assigned_aircraft_id: Identifier
    service_critical: bool
    crew_coverage: CrewCoverage
    crew_available_from: datetime | None = None

    @field_validator("scheduled_departure", "scheduled_arrival")
    @classmethod
    def require_timezone_aware_times(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @field_validator("crew_available_from")
    @classmethod
    def require_timezone_aware_crew_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_timezone(value)

    @model_validator(mode="after")
    def require_consistent_times_and_crew(self) -> FlightRecord:
        if self.scheduled_arrival <= self.scheduled_departure:
            raise ValueError("scheduled_arrival must be after scheduled_departure")
        if (self.crew_coverage is CrewCoverage.DELAYED) != (self.crew_available_from is not None):
            raise ValueError("crew_available_from is required for, and only for, delayed crew")
        return self


class FlightScheduleData(ContractModel):
    flights: tuple[FlightRecord, ...]


class AircraftStatus(StrEnum):
    SERVICEABLE = "serviceable"
    AOG = "aog"
    IN_MAINTENANCE = "in_maintenance"


class AircraftRecord(ContractModel):
    aircraft_id: Identifier
    aircraft_type: Identifier
    station: Identifier
    status: AircraftStatus
    available_from: datetime
    positioning_minutes: NonNegativeInt
    package_capacity: NonNegativeInt

    @field_validator("available_from")
    @classmethod
    def require_timezone_aware_availability(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class FleetAvailabilityData(ContractModel):
    aircraft: tuple[AircraftRecord, ...]


class PackageServiceLevel(StrEnum):
    PRIORITY = "priority"
    STANDARD = "standard"


class PackageGroup(ContractModel):
    group_id: Identifier
    flight_number: Identifier
    service_level: PackageServiceLevel
    time_critical: bool
    count: PositiveInt
    cutoff_at: datetime

    @field_validator("cutoff_at")
    @classmethod
    def require_timezone_aware_cutoff(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class CarrierType(StrEnum):
    OWN = "own"
    PARTNER = "partner"


class AlternateFlight(ContractModel):
    """A scheduled flight with spare package capacity, from the own network or a partner."""

    flight_number: Identifier
    carrier_type: CarrierType
    carrier_name: NonEmptyString
    origin: Identifier
    destination: Identifier
    departure_at: datetime
    arrival_at: datetime
    available_capacity: NonNegativeInt
    cost_per_package_usd: NonNegativeInt
    accepted_service_levels: tuple[PackageServiceLevel, ...] = Field(min_length=1)
    booking_deadline: datetime | None = None

    @field_validator("departure_at", "arrival_at")
    @classmethod
    def require_timezone_aware_times(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @field_validator("booking_deadline")
    @classmethod
    def require_timezone_aware_deadline(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_timezone(value)

    @model_validator(mode="after")
    def require_arrival_after_departure(self) -> AlternateFlight:
        if self.arrival_at <= self.departure_at:
            raise ValueError("arrival_at must be after departure_at")
        return self


class AlternateFlightData(ContractModel):
    flights: tuple[AlternateFlight, ...]


class ReplacementFlight(ContractModel):
    """An alternate flight on an affected route, with whether it may be used and why not."""

    flight_number: NonEmptyString
    carrier_type: CarrierType
    carrier_name: NonEmptyString
    origin: NonEmptyString
    destination: NonEmptyString
    departure_at: datetime
    arrival_at: datetime
    available_capacity: NonNegativeInt
    cost_per_package_usd: NonNegativeInt
    accepted_service_levels: tuple[PackageServiceLevel, ...]
    booking_deadline: datetime | None
    bookable: bool
    restriction: NonEmptyString | None


class PackageLoadData(ContractModel):
    groups: tuple[PackageGroup, ...]


class DisruptionKind(StrEnum):
    WEATHER = "weather"
    OUTAGE = "outage"
    CONGESTION = "congestion"
    OTHER = "other"


class DisruptionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DisruptionRecord(ContractModel):
    disruption_id: Identifier
    kind: DisruptionKind
    station: Identifier
    severity: DisruptionSeverity
    # Free text is untrusted and never reaches reasoning or output (ARD-SEC-005).
    description: str


class NetworkStatusData(ContractModel):
    disruptions: tuple[DisruptionRecord, ...]


# --- Result ----------------------------------------------------------------------------------


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


IMPACT_ORDER: tuple[ImpactLevel, ...] = (
    ImpactLevel.LOW,
    ImpactLevel.MEDIUM,
    ImpactLevel.HIGH,
    ImpactLevel.CRITICAL,
)


class Viability(StrEnum):
    VIABLE = "viable"
    VIABLE_WITH_RISK = "viable_with_risk"
    NOT_VIABLE = "not_viable"
    UNDETERMINED = "undetermined"


class ConflictCode(StrEnum):
    CREW_COVERAGE_GAP = "crew_coverage_gap"
    AIRCRAFT_DOUBLE_BOOKED = "aircraft_double_booked"
    TIME_ESTIMATE_CONFLICT = "time_estimate_conflict"


class RouteConflict(ContractModel):
    conflict_id: NonEmptyString
    code: ConflictCode
    option_id: NonEmptyString
    resource_ids: tuple[NonEmptyString, ...] = Field(min_length=1)
    description: NonEmptyString


class AllocationPath(StrEnum):
    HELD = "held_on_original_aircraft"
    SUBSTITUTE_AIRCRAFT = "substitute_aircraft"
    OWN_FLIGHT = "own_network_flight"
    PARTNER_FLIGHT = "partner_flight"


class PackageAllocation(ContractModel):
    group_id: NonEmptyString
    path: AllocationPath
    target_id: NonEmptyString
    carrier_name: NonEmptyString | None
    departure_at: datetime | None
    count: PositiveInt
    cost_usd: NonNegativeInt


class PackageOutcome(ContractModel):
    assessed: bool
    # False when alternate-flight data was unavailable: unprotected counts are then upper bounds.
    reroute_assessed: bool
    affected_package_count: NonNegativeInt | None
    time_critical_package_count: NonNegativeInt | None
    held_in_place_count: NonNegativeInt | None
    redistributed_count: NonNegativeInt | None
    own_flight_count: NonNegativeInt | None
    partner_flight_count: NonNegativeInt | None
    unprotected_count: NonNegativeInt | None
    unprotected_time_critical_count: NonNegativeInt | None
    allocations: tuple[PackageAllocation, ...]
    capacity_constraints: tuple[NonEmptyString, ...]
    service_commitments_at_risk: tuple[NonEmptyString, ...]


class CostBreakdown(ContractModel):
    delay_usd: NonNegativeInt
    swap_usd: NonNegativeInt
    rerouting_usd: NonNegativeInt
    unprotected_packages_usd: NonNegativeInt
    total_usd: NonNegativeInt
    complete: bool


class RecoveryOptionAssessment(ContractModel):
    option_id: NonEmptyString
    kind: OptionKind
    viability: Viability
    impact_level: ImpactLevel | None
    threshold_rule: NonEmptyString | None
    schedule_delay_minutes: NonNegativeInt | None
    earliest_feasible_departure: datetime | None
    substitute_aircraft_id: NonEmptyString | None
    package: PackageOutcome
    cost: CostBreakdown | None
    conflict_ids: tuple[NonEmptyString, ...]
    missing_inputs: tuple[NonEmptyString, ...]
    rationale: NonEmptyString


class PackageImpactSummary(ContractModel):
    assessed: bool
    affected_package_count: NonNegativeInt | None
    time_critical_package_count: NonNegativeInt | None
    summary: NonEmptyString


class RecommendationDecision(StrEnum):
    REPAIR_ORIGINAL = "repair_original"
    REPAIR_ALTERNATE = "repair_alternate"
    SWAP = "swap"
    DELAY = "delay"
    # Ranking belongs to the Controller (ARD-SYS-005); several viable options defer to it.
    DEFER_TO_CONTROLLER = "defer_to_controller"
    ESCALATE = "escalate"


class OperationsRecommendation(ContractModel):
    decision: RecommendationDecision
    viable_option_ids: tuple[NonEmptyString, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: NonEmptyString
    next_steps: tuple[NonEmptyString, ...]


class OperationsAssessment(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    agent_name: Literal["Operations Agent"] = "Operations Agent"
    operational_impact_level: ImpactLevel | None
    summary: NonEmptyString
    affected_routes: tuple[NonEmptyString, ...]
    package_impact: PackageImpactSummary
    # Own-network and partner flights found on the affected routes, with bookability.
    available_flights: tuple[ReplacementFlight, ...]
    recovery_options: tuple[RecoveryOptionAssessment, ...]
    risk_factors: tuple[NonEmptyString, ...]
    assumptions: tuple[NonEmptyString, ...]
    missing_data: tuple[NonEmptyString, ...]
    missing_analysis: tuple[NonEmptyString, ...]
    conflicts: tuple[RouteConflict, ...]
    warnings: tuple[NonEmptyString, ...]
    trade_offs: tuple[NonEmptyString, ...]
    requires_human_selection: bool
    recommendation: OperationsRecommendation
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_disposition: ConfidenceDisposition
    confidence_reasons: tuple[NonEmptyString, ...]
    reasoner_mode: NonEmptyString
    advisory_only: Literal[True] = True
    human_approval_required: Literal[True] = True


class OperationsOutcome(ContractModel):
    result: AgentResult
    assessment: OperationsAssessment | None
    evidence: tuple[Evidence, ...]
    warnings: tuple[EvidenceWarning, ...]
    conflicts: tuple[EvidenceConflict, ...]
    unknowns: tuple[Unknown, ...]
    errors: tuple[StructuredError, ...]
    audit_events: tuple[AuditEvent, ...]
    confidence: ConfidenceAssessment
