"""Shared readiness estimate: the one ETA format Maintenance and M&L hand to Operations.

Resolves free-form ETAs (hours, windows) into an absolute, traceable timestamp so no consumer
has to guess (ARD-DAT-004/005, ARD-GOV-005). A window resolves to its end, the conservative bound.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.base import ContractModel

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EtaBasis(StrEnum):
    CONFIRMED = "confirmed"
    ESTIMATED = "estimated"


class SourcingMethod(StrEnum):
    """Materials & Logistics sourcing methods; carried on a candidate for traceability."""

    INTERNAL_TRANSFER = "internal_transfer"
    VENDOR_PURCHASE = "vendor_purchase"
    BORROW = "borrow"
    EXPEDITE = "expedite"


_ETA_SOURCES = frozenset({AgentRole.MAINTENANCE, AgentRole.MATERIALS_LOGISTICS})


def _require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class ReadinessEstimate(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    source_agent: AgentRole
    eta: datetime
    basis: EtaBasis
    window_start: datetime | None = None
    window_end: datetime | None = None
    evidence_references: tuple[NonEmptyString, ...] = Field(min_length=1)

    @field_validator("eta")
    @classmethod
    def require_timezone_aware_eta(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @field_validator("window_start", "window_end")
    @classmethod
    def require_timezone_aware_window(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_timezone(value)

    @model_validator(mode="after")
    def require_consistent_source_and_window(self) -> ReadinessEstimate:
        if self.source_agent not in _ETA_SOURCES:
            raise ValueError("only Maintenance or Materials & Logistics may supply a readiness ETA")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("window_start and window_end must be given together")
        if self.window_start and self.window_end:
            if self.window_start > self.window_end:
                raise ValueError("window_start must not be after window_end")
            if not self.window_start <= self.eta <= self.window_end:
                raise ValueError("eta must lie within the window")
        return self

    @classmethod
    def from_window(
        cls,
        start: datetime,
        end: datetime,
        source_agent: AgentRole,
        evidence_references: tuple[str, ...],
    ) -> ReadinessEstimate:
        """A stated time window: plan on its end and mark the ETA as an estimate."""
        return cls(
            source_agent=source_agent,
            eta=end,
            basis=EtaBasis.ESTIMATED,
            window_start=start,
            window_end=end,
            evidence_references=evidence_references,
        )

    @classmethod
    def from_lead_time_hours(
        cls,
        as_of: datetime,
        hours: float,
        source_agent: AgentRole,
        evidence_references: tuple[str, ...],
        basis: EtaBasis = EtaBasis.ESTIMATED,
    ) -> ReadinessEstimate:
        """A relative lead time (for example M&L `eta_hours`) anchored at an explicit time."""
        if hours < 0:
            raise ValueError("lead time hours must not be negative")
        return cls(
            source_agent=source_agent,
            eta=as_of + timedelta(hours=hours),
            basis=basis,
            evidence_references=evidence_references,
        )
