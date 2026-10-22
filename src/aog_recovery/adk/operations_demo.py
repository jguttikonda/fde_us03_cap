"""Synthetic ADK Web scenarios for ARD-OPS-009 and ARD-TST-003/005/006."""

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.errors import APIError
from google.genai.types import Content, Part
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aog_recovery.adk.operations import AdkOperationsReasoner, OperationsReasoningError
from aog_recovery.contracts.case import TraceContext
from aog_recovery.operations.agent import OperationsAgent, OperationsAnalysisInput
from aog_recovery.operations.assessment import OptionCostRates
from aog_recovery.operations.contracts import (
    EvidenceState,
    OperationsEvidence,
    OperationsRequest,
    RecoveryCandidate,
    RecoveryOptionKind,
)
from aog_recovery.operations.packages import PackageCohort, RedistributionTarget
from aog_recovery.operations.validation import (
    AircraftAssignment,
    ConstraintState,
    CrewStationConstraint,
    ImpactThresholds,
    OperationalFlight,
    OperationalSnapshot,
    SubstituteAircraft,
)

SCENARIOS = {
    "swap": "1,200 packages, 700 priority, spare capacity 900; compare swap and delay.",
    "assignment-conflict": "The spare tail has an overlapping aircraft assignment.",
    "stale-conflict": "Explicitly stale and conflicting schedule evidence.",
    "low-confidence": "Valid fixture with confidence 0.45; escalation is required.",
}


class OperationsDemoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AOG_OPERATIONS_DEMO_", extra="ignore")

    model: str = Field(
        default="gemini-3.5-flash",
        min_length=1,
        validation_alias=AliasChoices("AOG_OPERATIONS_DEMO_MODEL", "ADK_MODEL"),
    )
    reasoning_timeout_seconds: float = Field(default=60, gt=0, le=120)


def build_demo_input(scenario: str) -> OperationsAnalysisInput:
    """Build fixed mock inputs, not live schedule or dispatch evidence (ARD-TST-009)."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown demo scenario: {scenario}")
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)
    departure = now + timedelta(hours=3)
    arrival = departure + timedelta(hours=1)
    assignments = [
        AircraftAssignment(tail_id="FX123", flight_id="FX401", start_at=departure, end_at=arrival)
    ]
    if scenario == "assignment-conflict":
        assignments.append(
            AircraftAssignment(
                tail_id="FX207",
                flight_id="FX999",
                start_at=departure,
                end_at=arrival,
            )
        )
    evidence = [
        OperationsEvidence(
            evidence_id="ev-schedule-401",
            source="synthetic-schedule",
            observed_at=now,
            state=EvidenceState.CURRENT,
            subject="FX401 schedule",
            value={"route": "MEM-IND"},
        ),
        OperationsEvidence(
            evidence_id="ev-fleet-207",
            source="synthetic-fleet",
            observed_at=now,
            state=EvidenceState.CURRENT,
            subject="FX207 availability",
            value={"station": "MEM"},
        ),
    ]
    if scenario == "stale-conflict":
        evidence[0] = evidence[0].model_copy(
            update={"state": EvidenceState.STALE, "observed_at": now - timedelta(days=1)}
        )
        evidence.extend(
            OperationsEvidence(
                evidence_id=f"ev-conflict-{index}",
                source=f"synthetic-schedule-{index}",
                observed_at=now,
                state=EvidenceState.CONFLICTING,
                subject="FX401 route",
                value={"route": route},
            )
            for index, route in enumerate(("MEM-IND", "MEM-DFW"), start=1)
        )
    return OperationsAnalysisInput(
        request=OperationsRequest(
            schema_version="1.0",
            case_id=f"synthetic-review-{scenario}",
            trace_context=TraceContext(
                trace_id=f"trace-review-{scenario}", correlation_id=f"corr-review-{scenario}"
            ),
            affected_flight_ids=("FX401",),
            candidates=(
                RecoveryCandidate(
                    option_id="swap-fx207",
                    kind=RecoveryOptionKind.SWAP,
                    description="Swap to synthetic spare FX207 with a 15-minute delay",
                    substitute_tail_id="FX207",
                    delay_minutes=15,
                    evidence_references=("ev-fleet-207",),
                ),
                RecoveryCandidate(
                    option_id="delay-90",
                    kind=RecoveryOptionKind.DELAY,
                    description="Delay FX401 by 90 minutes",
                    delay_minutes=90,
                    evidence_references=("ev-schedule-401",),
                ),
            ),
            evidence_references=tuple(item.evidence_id for item in evidence),
        ),
        snapshot=OperationalSnapshot(
            flights=(
                OperationalFlight(
                    flight_id="FX401",
                    route="MEM-IND",
                    origin_station="MEM",
                    destination_station="IND",
                    aircraft_type="A320",
                    assigned_tail_id="FX123",
                    departure_at=departure,
                    arrival_at=arrival,
                ),
            ),
            assignments=tuple(assignments),
            substitute_aircraft=(
                SubstituteAircraft(
                    tail_id="FX207",
                    aircraft_type="A320",
                    station_id="MEM",
                    available_from=now,
                    available_until=arrival + timedelta(hours=2),
                ),
            ),
            crew_station_constraints=(
                CrewStationConstraint(
                    flight_id="FX401", resource_id="crew-FX401", state=ConstraintState.AVAILABLE
                ),
            ),
            disruptions=(),
            missing_evidence=(),
            impact_thresholds=ImpactThresholds(
                medium_delay_minutes=30, high_delay_minutes=120, critical_delay_minutes=300
            ),
        ),
        evidence=tuple(evidence),
        assumptions=(),
        conflicts=(),
        package_manifest=(
            PackageCohort(
                cohort_id="priority", service_level="priority", package_count=700, ready_at=now
            ),
            PackageCohort(
                cohort_id="standard", service_level="standard", package_count=500, ready_at=now
            ),
        ),
        redistribution_targets_by_option={
            option_id: (
                RedistributionTarget(
                    tail_id=tail_id,
                    remaining_capacity=capacity,
                    packages_arrive_at=now,
                    sort_window_start=now,
                    sort_window_end=arrival,
                    cutoff_at=departure,
                ),
            )
            for option_id, tail_id, capacity in (
                ("swap-fx207", "FX207", 900),
                ("delay-90", "FX955", 1200),
            )
        },
        service_level_order=("priority", "standard"),
        cost_rates=OptionCostRates(
            currency="USD",
            delay_per_minute=Decimal("1.00"),
            swap_flat_cost=Decimal("50.00"),
            unprotected_package_exposure=Decimal("2.00"),
        ),
        confidence=0.45 if scenario == "low-confidence" else 0.85,
    )


class OperationsDemoAgent(BaseAgent):
    """Allowlisted scenario runner; no free-text operational inputs (ARD-SEC-003/004)."""

    model_name: str
    reasoning_timeout_seconds: float

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event]:
        prompt = "".join(
            part.text or "" for part in (ctx.user_content.parts if ctx.user_content else []) or []
        ).strip()
        if prompt not in SCENARIOS:
            response: dict[str, object] = {
                "status": "invalid_scenario",
                "synthetic_demo": True,
                "human_approval_required": True,
                "message": "Enter exactly one of the scenario names below. No action was taken.",
                "scenarios": SCENARIOS,
            }
        else:
            agent = OperationsAgent(
                AdkOperationsReasoner(self.model_name),
                reasoning_timeout_seconds=self.reasoning_timeout_seconds,
            )
            try:
                assessment = await agent.assess(build_demo_input(prompt))
            except APIError as error:
                response = {
                    "status": "failed",
                    "synthetic_demo": True,
                    "human_approval_required": True,
                    "error": {
                        "component": "gemini",
                        "category": "provider_error",
                        "code": error.code,
                        "message": "Live model request failed; no assessment was produced.",
                    },
                }
            except OperationsReasoningError:
                response = {
                    "status": "failed",
                    "synthetic_demo": True,
                    "human_approval_required": True,
                    "error": {
                        "component": "operations-reasoner",
                        "category": "reasoning_error",
                        "message": (
                            "ADK reasoning failed; no assessment was produced. Check server logs."
                        ),
                    },
                }
            else:
                response = {
                    "synthetic_demo": True,
                    "human_approval_required": True,
                    "scenario": prompt,
                    "model": self.model_name,
                    "assessment": assessment.model_dump(mode="json"),
                }
        yield Event(
            author=self.name,
            content=Content(role="model", parts=[Part(text=json.dumps(response, indent=2))]),
        )


def create_operations_demo_agent() -> OperationsDemoAgent:
    settings = OperationsDemoSettings()
    return OperationsDemoAgent(
        name="operations_peer_review",
        description="Synthetic Operations scenarios with live Gemini reasoning; no actions.",
        model_name=settings.model,
        reasoning_timeout_seconds=settings.reasoning_timeout_seconds,
    )
