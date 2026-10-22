"""Offline Controller demo: python -m aog_recovery.controller.demo [scenario ...] [--json]."""

import json
import sys
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import AogCase
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.compliance import build_unranked_handoff
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    PerCandidateResult,
    RecoveryDecisionBrief,
    WorkflowStatus,
)
from aog_recovery.controller.recommendation import build_recommendation
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentPayload,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RepairabilityStatus,
)
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartRole,
    SourcingMethod,
    SourcingOption,
    TraceabilityStatus,
)
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import OperationsRequest, OptionKind, PackageLoadData
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import T0, default_adapters, default_case

DEMO_TIME = T0 + timedelta(minutes=5)


class DemoScenario(StrEnum):
    HAPPY_PATH = "happy_path"
    CACHE_DEGRADED = "cache_degraded"
    TIME_CONFLICT = "time_conflict"
    CLOSE_SCORE = "close_score_choice"


DEMO_SCENARIOS = tuple(DemoScenario)


class ControllerDemoResult(ContractModel):
    scenario: DemoScenario
    report: RecoveryDecisionBrief
    evidence: tuple[Evidence, ...]
    offline: bool = True
    advisory_only: bool = True
    operational_actions: tuple[str, ...] = ()


def _evidence_bundle(*, cached: bool, time_conflict: bool) -> tuple[Evidence, ...]:
    evidence = [
        Evidence(
            evidence_id="approval-evidence-001",
            source="synthetic-maintenance-records",
            retrieved_at=DEMO_TIME,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference="approval-evidence-001",
            content={"approval_recorded": True},
        ),
        Evidence(
            evidence_id="part-eligibility-001",
            source="synthetic-inventory",
            retrieved_at=DEMO_TIME,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference="part-eligibility-001",
            content={"part_number": "P-120", "authorized": True, "traceable": True},
        ),
        Evidence(
            evidence_id="eta-evidence-001",
            source="synthetic-maintenance-estimate",
            retrieved_at=DEMO_TIME,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference="eta-evidence-001",
            content={"repair_hours": 3 if time_conflict else 2},
        ),
        Evidence(
            evidence_id="load-evidence-001",
            source="synthetic-package-manifest",
            retrieved_at=DEMO_TIME,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference="load-evidence-001",
            content={"manifest": "synthetic"},
        ),
    ]
    evidence.extend(
        (
            Evidence(
                evidence_id="engineering-preference-P120",
                source="synthetic-engineering-notes",
                retrieved_at=DEMO_TIME,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="preferred-replacement-P120",
                content={"preferred_part_number": "P-120"},
            ),
            Evidence(
                evidence_id="need-by-P120",
                source="synthetic-maintenance-plan",
                retrieved_at=DEMO_TIME,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="need-by-P120",
                content={"need_by": (DEMO_TIME + timedelta(hours=8)).isoformat()},
            ),
            Evidence(
                evidence_id="parts-ready-P120",
                source="synthetic-materials-plan",
                retrieved_at=DEMO_TIME,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="parts-ready-P120",
                content={"parts_ready_at": DEMO_TIME.isoformat()},
            ),
            Evidence(
                evidence_id="quote-P120",
                source="synthetic-sourcing-quote",
                retrieved_at=DEMO_TIME,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="quote-P120",
                content={"estimated_cost_usd": "100.00", "lead_time_hours": 2},
            ),
            *tuple(
                Evidence(
                    evidence_id=f"maintenance-history-P110-{index}",
                    source="synthetic-maintenance-history",
                    retrieved_at=DEMO_TIME,
                    validity_state=EvidenceValidity.CURRENT,
                    claim_reference=f"maintenance-history-P110-{index}",
                    content={
                        "part_number": "P-110",
                        "occurred_at": (DEMO_TIME - timedelta(days=days)).isoformat(),
                    },
                )
                for index, days in enumerate((89, 45, 0), start=1)
            ),
        )
    )
    if cached:
        evidence.append(
            Evidence(
                evidence_id="inventory-cache-p120",
                source="synthetic-inventory-cache",
                retrieved_at=DEMO_TIME - timedelta(days=1),
                validity_state=EvidenceValidity.STALE,
                claim_reference="inventory-availability-p120",
                content={"available_quantity": 1},
            )
        )
    else:
        evidence.append(
            Evidence(
                evidence_id="inventory-live-p120",
                source="synthetic-inventory",
                retrieved_at=DEMO_TIME,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="inventory-availability-p120",
                content={"available_quantity": 1},
            )
        )
    if time_conflict:
        evidence.extend(
            (
                Evidence(
                    evidence_id="maintenance-time-estimate-3h",
                    source="synthetic-maintenance-estimate",
                    retrieved_at=DEMO_TIME,
                    validity_state=EvidenceValidity.CURRENT,
                    claim_reference="recovery-time-estimate",
                    content={"estimate_hours": 3},
                ),
                Evidence(
                    evidence_id="operations-disruption-estimate-7h",
                    source="synthetic-operations-disruption",
                    retrieved_at=DEMO_TIME,
                    validity_state=EvidenceValidity.CONFLICTING,
                    claim_reference="recovery-time-estimate",
                    content={"estimate_hours": 7},
                ),
            )
        )
    return tuple(evidence)


def build_demo_intake(scenario: DemoScenario) -> ControllerIntake:
    """Build deterministic, typed Controller intake for one named synthetic scenario."""
    case = default_case()
    cached = scenario is DemoScenario.CACHE_DEGRADED
    time_conflict = scenario is DemoScenario.TIME_CONFLICT
    evidence = _evidence_bundle(cached=cached, time_conflict=time_conflict)
    evidence_references = tuple(item.evidence_id for item in evidence)
    source_keys = (
        ("demo-close-p120-a", "demo-close-p120-b")
        if scenario is DemoScenario.CLOSE_SCORE
        else (f"demo-{scenario.value}-p120",)
    )
    candidate_sources = tuple(
        CandidateSource(
            source_key=source_key,
            kind=OptionKind.REPAIR_ALTERNATE,
            failed_part_number="P-110",
            source_evidence_references=evidence_references,
            readiness=ReadinessEstimate(
                source_agent=AgentRole.MAINTENANCE,
                eta=DEMO_TIME,
                basis=EtaBasis.CONFIRMED,
                evidence_references=("eta-evidence-001",),
            ),
            sourcing_options=(
                SourcingOption(
                    part_number="P-120",
                    source="synthetic-station",
                    source_location="TEST-STATION-B",
                    method=SourcingMethod.INTERNAL_TRANSFER,
                    shipping_provider=None,
                    shipping_service=None,
                    transfer_required=True,
                    lead_time_hours=2.0,
                    eta_at=DEMO_TIME,
                    estimated_cost_usd=Decimal("100.00"),
                    quote_unavailable_reason=None,
                    evidence_references=("part-eligibility-001",),
                ),
            ),
            package_load=PackageLoadData(groups=()),
            package_load_evidence_references=("load-evidence-001",),
        )
        for source_key in source_keys
    )
    return ControllerIntake(
        schema_version="1.0",
        case=case,
        evidence=evidence,
        affected_flight_numbers=("FX103",),
        candidate_sources=candidate_sources,
    )


def _candidate_result(
    case: AogCase,
    *,
    source_key: str,
    cached: bool = False,
    time_conflict: bool = False,
) -> PerCandidateResult:
    evidence = _evidence_bundle(cached=cached, time_conflict=time_conflict)
    evidence_ids = tuple(item.evidence_id for item in evidence)
    sourcing = SourcingOption(
        part_number="P-120",
        source="synthetic-station",
        source_location="TEST-STATION-B",
        method=SourcingMethod.INTERNAL_TRANSFER,
        shipping_provider=None,
        shipping_service=None,
        transfer_required=True,
        lead_time_hours=2.0,
        eta_at=DEMO_TIME,
        estimated_cost_usd=Decimal("100.00"),
        quote_unavailable_reason=None,
        evidence_references=(
            ("part-eligibility-001", "inventory-cache-p120")
            if cached
            else ("part-eligibility-001",)
        ),
    )
    source = CandidateSource(
        source_key=source_key,
        kind=OptionKind.REPAIR_ALTERNATE,
        failed_part_number="P-110",
        source_evidence_references=evidence_ids,
        readiness=ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=DEMO_TIME,
            basis=EtaBasis.CONFIRMED,
            evidence_references=("eta-evidence-001",),
        ),
        sourcing_options=(sourcing,),
        package_load=PackageLoadData(groups=()),
        package_load_evidence_references=("load-evidence-001",),
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=case,
        evidence=evidence,
        affected_flight_numbers=("FX103",),
        candidate_sources=(source,),
    )
    candidate = build_candidates(intake)[0]

    warning = EvidenceWarning(
        warning_id=f"{source_key}-cached-warning",
        claim_reference="part-eligibility-001",
        code="CACHED_EVIDENCE",
        message="Live inventory is unavailable; cached P-120 evidence may be stale.",
        source_reference="synthetic-inventory-cache",
    )
    source_error = StructuredError(
        schema_version="1.0",
        category="source_unavailable",
        component="materials-adapter:part_inventory",
        message="Synthetic live inventory source is unavailable.",
        retryable=False,
        case_impact="Sourcing is based on explicitly degraded cached evidence.",
    )
    maintenance_payload = MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.FEASIBLE,
        root_cause=None,
        recurring_failure=None,
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("part-eligibility-001",),
        required_actions=("replace_pump",),
        estimated_ground_time_hours=3.0 if time_conflict else 2.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("125.00"),
        need_by_time=None,
        parts_ready_at=DEMO_TIME,
        return_to_service_time=DEMO_TIME + timedelta(hours=3 if time_conflict else 2),
        meets_need_by_time=None,
        eta_confidence=0.95,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.LOW,
            parts_dependency_risk=MaintenanceRiskLevel.LOW,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.APPROVAL_RECORDED,
            approver_role="maintenance_airworthiness_authority",
            source_reference="approval-evidence-001",
            recorded_at=DEMO_TIME,
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.REPAIR,
            confidence=0.95,
            rationale="Synthetic source-backed repair path.",
            next_steps=("Human review is required before action.",),
        ),
    )
    evidence_summary = MaterialsEvidenceSummary(
        status=ToolResultStatus.PARTIAL if cached else ToolResultStatus.SUCCESS,
        confidence=0.72 if cached else 0.95,
        evidence_references=("part-eligibility-001",),
        warnings=(warning,) if cached else (),
        errors=(source_error,) if cached else (),
    )
    materials_payload = MaterialsLogisticsAgentPayload(
        schema_version="1.0",
        assessment=MaterialsLogisticsAssessmentPayload(
            schema_version="1.0",
            availability_status=AvailabilityStatus.AVAILABLE,
            part_availability=(
                PartAvailabilityRecord(
                    part_number="P-120",
                    role=PartRole.PREFERRED_REPLACEMENT,
                    required_quantity=1,
                    available_quantity=1,
                    minimum_stock_threshold=1,
                    location="TEST-STATION-B",
                    source="synthetic-inventory-cache" if cached else "synthetic-inventory",
                    retrieved_at=DEMO_TIME - timedelta(days=1) if cached else DEMO_TIME,
                    validity_state=EvidenceValidity.STALE if cached else EvidenceValidity.CURRENT,
                    claim_reference="inventory-availability-p120",
                ),
            ),
            part_eligibility=(
                PartEligibilityEvidence(
                    part_number="P-120",
                    compatibility=CompatibilityStatus.COMPATIBLE,
                    authorization=AuthorizationStatus.AUTHORIZED,
                    traceability=TraceabilityStatus.VERIFIED,
                    checked_by_role="materials_inventory_specialist",
                    evidence_references=("part-eligibility-001",),
                ),
            ),
            sourcing_options=(sourcing,),
            confidence=0.72 if cached else 0.95,
            risk_factors=(),
            assumptions=(),
            missing_data=(),
        ),
        evidence_summary=evidence_summary,
    )
    maintenance_evidence_references = ["approval-evidence-001", "eta-evidence-001"]
    if time_conflict:
        maintenance_evidence_references.append("maintenance-time-estimate-3h")
    maintenance_result = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MAINTENANCE,
        status=AgentResultStatus.COMPLETE,
        summary="Synthetic source-backed Maintenance assessment.",
        confidence=0.95,
        assumptions=(),
        evidence_references=tuple(maintenance_evidence_references),
        role_payload=maintenance_payload.model_dump(mode="json"),
    )
    materials_result = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.MATERIALS_LOGISTICS,
        status=AgentResultStatus.PARTIAL if cached else AgentResultStatus.COMPLETE,
        summary=(
            "Materials assessment uses degraded cached inventory."
            if cached
            else "Synthetic authorized P-120 sourcing assessment."
        ),
        confidence=0.72 if cached else 0.95,
        assumptions=(),
        evidence_references=("part-eligibility-001",),
        role_payload=materials_payload.model_dump(mode="json"),
    )
    operations_request = OperationsRequest(
        schema_version="1.0",
        request_id=f"{candidate.candidate.option_id}:operations",
        case=case,
        affected_flight_numbers=("FX103",),
        candidates=(candidate.candidate,),
        evaluated_at=DEMO_TIME,
    )
    operations_outcome = OperationsAgent(
        default_adapters(),
        settings=OperationsSettings.model_validate({}),
    ).assess(operations_request)
    return PerCandidateResult(
        candidate=candidate.candidate,
        candidate_source=candidate.source,
        maintenance_result=maintenance_result,
        materials_logistics_result=materials_result,
        operations_result=operations_outcome,
        peer_exchange_recording=None,
        confidence=None,
        status=WorkflowStatus.IN_PROGRESS,
        evidence=evidence,
        warnings=(),
        conflicts=(),
        unknowns=(),
        missing_data=(),
        errors=(),
    )


def _scenario_results(scenario: DemoScenario) -> tuple[AogCase, tuple[PerCandidateResult, ...]]:
    case = default_case()
    if scenario is DemoScenario.CACHE_DEGRADED:
        return case, (_candidate_result(case, source_key="demo-cached-p120", cached=True),)
    if scenario is DemoScenario.TIME_CONFLICT:
        return case, (_candidate_result(case, source_key="demo-conflict-p120", time_conflict=True),)
    if scenario is DemoScenario.CLOSE_SCORE:
        return case, (
            _candidate_result(case, source_key="demo-close-p120-a"),
            _candidate_result(case, source_key="demo-close-p120-b"),
        )
    return case, (_candidate_result(case, source_key="demo-happy-p120"),)


def run_demo_scenario(name: str) -> ControllerDemoResult:
    """Run one deterministic Controller report scenario using local synthetic adapters."""
    try:
        scenario = DemoScenario(name)
    except ValueError as error:
        raise ValueError(f"unknown Controller demo scenario: {name}") from error

    case, candidate_results = _scenario_results(scenario)
    handoff = build_unranked_handoff(case, candidate_results, occurred_at=DEMO_TIME)
    report = build_recommendation(handoff, occurred_at=DEMO_TIME)
    evidence_by_id = {
        item.evidence_id: item for result in candidate_results for item in result.evidence
    }
    evidence = tuple(evidence_by_id[key] for key in sorted(evidence_by_id))
    return ControllerDemoResult(scenario=scenario, report=report, evidence=evidence)


def _render(result: ControllerDemoResult) -> str:
    report = result.report
    lines = [
        f"=== Controller demo: {result.scenario.value} ===",
        f"Case: {report.case_id}",
        f"Status: {report.status.value}; confidence: {report.confidence.confidence:.2f}",
        f"Human gate: {report.human_gate.status.value}",
        f"Human selection required: {report.requires_human_selection}",
        report.summary,
        "Options:",
    ]
    for ranked_option in report.ranked_options:
        lines.append(
            f"  rank {ranked_option.rank}: {ranked_option.option_id} "
            f"score={ranked_option.aggregate_score} "
            f"selection_group={ranked_option.selection_group}"
        )
        lines.append(f"    {ranked_option.trade_off}")
    for excluded_option in report.excluded_options:
        reasons = "; ".join(excluded_option.exclusion_reasons)
        lines.append(f"  excluded: {excluded_option.option_id}: {reasons}")
    for unscored_option in report.unscored_options:
        lines.append(
            f"  unscored: {unscored_option.option_id}: {'; '.join(unscored_option.reasons)}"
        )
    if report.warnings:
        lines.append("Warnings: " + "; ".join(item.code for item in report.warnings))
    if report.errors:
        lines.append("Errors: " + "; ".join(item.category for item in report.errors))
    if report.conflicts:
        lines.append("Conflicts: " + "; ".join(item.description for item in report.conflicts))
    if result.scenario is DemoScenario.TIME_CONFLICT:
        lines.extend(
            f"Time evidence: {item.source} reports {item.content['estimate_hours']} hours"
            for item in result.evidence
            if item.claim_reference == "recovery-time-estimate"
        )
    lines.append("Evidence references: " + ", ".join(item.evidence_id for item in result.evidence))
    lines.append("Operational actions executed: none")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in args
    names = [item for item in args if item != "--json"] or [item.value for item in DEMO_SCENARIOS]
    unknown = sorted(set(names).difference(item.value for item in DEMO_SCENARIOS))
    if unknown:
        print(
            f"Unknown scenario(s): {', '.join(unknown)}. Available: "
            f"{', '.join(item.value for item in DEMO_SCENARIOS)}"
        )
        return 2

    results = [run_demo_scenario(name) for name in names]
    if as_json:
        print(
            json.dumps([item.model_dump(mode="json") for item in results], indent=2, sort_keys=True)
        )
    else:
        print("\n\n".join(_render(item) for item in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
