from typing import Annotated

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NonNegativeInt = Annotated[int, Field(ge=0)]
Penalty = Annotated[float, Field(ge=0.0, le=1.0)]


class OperationsSettings(BaseSettings):
    """Externalized Operations policy; cost rates and thresholds are mock capstone values."""

    model_config = SettingsConfigDict(
        env_prefix="AOG_OPS_",
        extra="forbid",
        validate_default=True,
        frozen=True,
    )

    # Disruption thresholds in minutes of schedule delay (ARD-OPS-003, ARD-NFR-006).
    delay_medium_minutes: NonNegativeInt = 60
    delay_high_minutes: NonNegativeInt = 180
    delay_critical_minutes: NonNegativeInt = 360

    # Timing buffers and windows (ARD-OPS-002).
    turnaround_buffer_minutes: NonNegativeInt = 30
    swap_window_minutes: NonNegativeInt = 480
    swap_positioning_limit_minutes: NonNegativeInt = 240
    time_conflict_threshold_minutes: NonNegativeInt = 60

    # Data freshness and bounded retry (ARD-OPS-006, ARD-RES-005, ARD-NFR-002).
    evidence_max_age_minutes: Annotated[int, Field(ge=1)] = 60
    max_retries: Annotated[int, Field(ge=0, le=3)] = 1

    # Mock USD cost rates (ARD-CTL-019, ARD-OPS-009).
    delay_cost_per_minute_usd: NonNegativeInt = 85
    swap_cost_usd: NonNegativeInt = 18000
    unprotected_priority_package_cost_usd: NonNegativeInt = 45
    unprotected_standard_package_cost_usd: NonNegativeInt = 15

    # Material trade-off limit between viable options (ARD-OPS-007).
    material_unprotected_packages_gap: NonNegativeInt = 100

    # Deterministic confidence policy (ARD-GOV-001..004, ARD-OPS-006).
    base_confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.90
    provisional_confidence_cap: Annotated[float, Field(ge=0.0, le=1.0)] = 0.69
    penalty_stale_evidence: Penalty = 0.25
    penalty_partial_evidence: Penalty = 0.15
    penalty_critical_source_unavailable: Penalty = 0.30
    penalty_optional_source_unavailable: Penalty = 0.10
    penalty_estimated_eta: Penalty = 0.10
    penalty_conflict: Penalty = 0.10
    penalty_undetermined_candidate: Penalty = 0.20

    adk_model: str = Field(default="gemini-3.5-flash", validation_alias="ADK_MODEL")

    @model_validator(mode="after")
    def require_ordered_thresholds(self) -> OperationsSettings:
        if not (self.delay_medium_minutes < self.delay_high_minutes < self.delay_critical_minutes):
            raise ValueError("delay thresholds must satisfy medium < high < critical")
        if self.provisional_confidence_cap >= 0.70:
            raise ValueError("provisional confidence cap must stay below 0.70")
        return self
