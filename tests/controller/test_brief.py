from datetime import datetime
from decimal import Decimal

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import EvidenceWarning
from aog_recovery.contracts.readiness import SourcingMethod
from aog_recovery.controller.brief import build_decision_brief, render_decision_brief
from aog_recovery.controller.models import (
    CandidateAssessment,
    ConfidenceDisposition,
    ControllerCandidateExecution,
    ControllerWorkflowStatus,
    RankedOption,
    RecoveryOptionKind,
    ScoreFactors,
    ScoreWeights,
    ScoringResult,
)


def specialist(role: AgentRole, confidence: float) -> AgentResult:
    return AgentResult(
        schema_version="1.0",
        agent_role=role,
        status=AgentResultStatus.COMPLETE,
        summary=f"{role.value} synthetic assessment completed.",
        confidence=confidence,
        assumptions=(),
        evidence_references=(f"EVIDENCE-{role.value.upper()}",),
        role_payload={},
    )


def execution(
    confidence: float,
    *,
    conflict: bool = False,
) -> ControllerCandidateExecution:
    warning = EvidenceWarning(
        warning_id="estimated-eta",
        claim_reference="readiness-eta",
        code="ESTIMATED_ETA",
        message="Readiness ETA is an estimate, not confirmed.",
        source_reference="synthetic-fixture",
    )
    return ControllerCandidateExecution(
        schema_version="1.0",
        case_id="AOG-BRIEF-001",
        candidate_option_id="OPT-REPAIR-P120",
        status=ControllerWorkflowStatus.ESCALATED if conflict else ControllerWorkflowStatus.PARTIAL,
        maintenance_result=specialist(AgentRole.MAINTENANCE, confidence),
        materials_result=specialist(AgentRole.MATERIALS_LOGISTICS, confidence),
        peer_exchange=None,
        peer_recording=None,
        operations_outcome=None,
        validation_findings=(),
        missing_data=(),
        warnings=(warning,),
        specialist_conflicts=("Inventory sources disagree about P-120 stock.",) if conflict else (),
        conflicts=(),
        unknowns=(),
        errors=(),
    )


def scored_option(option_id: str, score: float) -> RankedOption:
    assessment = CandidateAssessment(
        option_id=option_id,
        kind=RecoveryOptionKind.REPAIR_ALTERNATE,
        description="Repair using approved replacement part P-120",
        sourcing_method=SourcingMethod.INTERNAL_TRANSFER,
        return_to_service_hours=4.0,
        estimated_cost_usd=Decimal("1000.00"),
        evidence_references=("MNT-ETA-001",),
        assumptions=(),
        risks=("Transfer timing is uncertain.",),
        compliance_eligible=True,
        exclusion_reasons=(),
        score_factors=ScoreFactors(
            speed=80.0,
            operational_package_impact=70.0,
            risk=75.0,
            cost=60.0,
        ),
        score_weights=ScoreWeights(),
        aggregate_score=score,
        trade_off="Fastest option depends on part delivery.",
        sourcing_source="DFW station inventory",
        sourcing_location="DFW",
        sourcing_lead_time_hours=2.0,
        affected_flight_numbers=("FX412", "FX908"),
        affected_package_count=1200,
        priority_package_count=300,
        unprotected_package_count=40,
        main_risk="Delivery or repair may take longer than estimated.",
    )
    return RankedOption(rank=1, assessment=assessment)


def scoring_result(*scores: tuple[str, float]) -> ScoringResult:
    ranked = tuple(
        scored_option(option_id, score).model_copy(update={"rank": index})
        for index, (option_id, score) in enumerate(
            sorted(scores, key=lambda item: (-item[1], item[0])), start=1
        )
    )
    close_ids = tuple(
        item.assessment.option_id
        for item in ranked
        if ranked[0].assessment.aggregate_score - item.assessment.aggregate_score <= 2.0
    )
    return ScoringResult(
        weights=ScoreWeights(),
        ranked_options=ranked,
        excluded_options=(),
        unscored_options=(),
        close_score_option_ids=close_ids if len(close_ids) > 1 else (),
        human_selection_required=len(close_ids) > 1,
    )


def test_high_confidence_brief_selects_preferred_path_but_keeps_approval_gate() -> None:
    brief = build_decision_brief(
        execution(0.90),
        scoring_result(("OPT-REPAIR-P120", 82.0), ("OPT-SWAP", 70.0)),
        "AOG-BRIEF-001-v1",
    )

    assert brief.confidence_disposition is ConfidenceDisposition.PREFERRED
    assert brief.recommended_option_id == "OPT-REPAIR-P120"
    assert brief.status is ControllerWorkflowStatus.PARTIAL
    assert brief.human_approval_required is True
    assert "must review and approve" in brief.next_action


def test_provisional_confidence_is_labeled_and_keeps_rationale() -> None:
    brief = build_decision_brief(
        execution(0.62),
        scoring_result(("OPT-REPAIR-P120", 82.0)),
        "AOG-BRIEF-001-v2",
    )

    assert brief.confidence_disposition is ConfidenceDisposition.PROVISIONAL
    assert brief.status is ControllerWorkflowStatus.PARTIAL
    assert brief.recommended_option_id == "OPT-REPAIR-P120"
    assert brief.recommendation_rationale
    assert brief.human_approval_required is True


def test_conflicting_evidence_forces_escalation_without_unique_recommendation() -> None:
    brief = build_decision_brief(
        execution(0.95, conflict=True),
        scoring_result(("OPT-REPAIR-P120", 90.0)),
        "AOG-BRIEF-001-v3",
    )

    assert brief.status is ControllerWorkflowStatus.ESCALATED
    assert brief.confidence == 0.49
    assert brief.confidence_disposition is ConfidenceDisposition.ESCALATE
    assert brief.recommended_option_id is None
    assert any("sources disagree" in item for item in brief.warnings)
    assert brief.human_approval_required is True


def test_close_scores_are_both_shown_for_human_selection() -> None:
    brief = build_decision_brief(
        execution(0.88),
        scoring_result(("OPT-REPAIR-P120", 82.0), ("OPT-SWAP", 80.0)),
        "AOG-BRIEF-001-v4",
    )

    assert brief.recommended_option_id is None
    assert tuple(item.assessment.option_id for item in brief.ranked_options) == (
        "OPT-REPAIR-P120",
        "OPT-SWAP",
    )
    assert "human selection is required" in brief.recommendation_rationale
    assert brief.human_approval_required is True


def test_chat_renderer_preserves_scores_exclusions_evidence_and_human_gate() -> None:
    brief = build_decision_brief(
        execution(0.88),
        scoring_result(("OPT-REPAIR-P120", 82.0)),
        "AOG-BRIEF-001-v5",
    )

    response = render_decision_brief(brief)

    assert "**Score:** 82/100" in response
    assert "speed 80.00" in response
    assert "MNT-ETA-001" in response
    assert "human approval is required before any action" in response.casefold()


def test_chat_renderer_lists_compliance_exclusions_and_close_score_notice() -> None:
    brief = build_decision_brief(
        execution(0.88),
        scoring_result(("OPT-REPAIR-P120", 82.0), ("OPT-SWAP", 80.0)),
        "AOG-BRIEF-001-v6",
    )

    response = render_decision_brief(brief)

    assert "human selection is required" in response
    assert "Advisory only" in response


def test_report_summarises_fastest_and_lowest_cost_options() -> None:
    scoring = scoring_result(("OPT-A", 84.0), ("OPT-B", 72.0))
    first, second = scoring.ranked_options
    fast = first.model_copy(
        update={
            "assessment": first.assessment.model_copy(
                update={"return_to_service_hours": 3.0, "estimated_cost_usd": Decimal("9000.00")}
            )
        }
    )
    cheap = second.model_copy(
        update={
            "assessment": second.assessment.model_copy(
                update={"return_to_service_hours": 6.0, "estimated_cost_usd": Decimal("2000.00")}
            )
        }
    )
    brief = build_decision_brief(
        execution(0.88),
        scoring.model_copy(update={"ranked_options": (fast, cheap)}),
        "AOG-BRIEF-001-v7",
    )

    report = render_decision_brief(brief)

    expected = "Option 1 has the fastest return to service; Option 2 has the lowest cost."
    assert expected in report
    assert "- **Trade-off:** Fastest return to service, highest cost." in report
    assert "- **Trade-off:** Slowest return to service, lowest cost." in report


def test_final_controller_output_matches_sponsor_report_layout() -> None:
    case = AogCase(
        case_id="AOG-BRIEF-001",
        aircraft_id="FX-321",
        event_type="hydraulic_pump_failure",
        defect_summary="Hydraulic pump issue",
        location="Memphis",
        event_at=datetime.fromisoformat("2026-10-22T10:00:00+00:00"),
        created_at=datetime.fromisoformat("2026-10-22T10:05:00+00:00"),
        schema_version="1.0",
        trace_context=TraceContext(trace_id="trace-brief-001", correlation_id="corr-brief-001"),
    )
    brief = build_decision_brief(
        execution(0.62),
        scoring_result(("OPT-REPAIR-P120", 84.0), ("OPT-SWAP", 72.0)),
        "AOG-BRIEF-001-demo-v1",
        case=case,
    )

    report = render_decision_brief(brief)

    assert "## AOG Recovery Options for Aircraft FX-321" in report
    assert "### Executive summary" in report
    assert "**Case:** Hydraulic pump issue (Station: Memphis)" in report
    assert "#### 1. Repair using approved replacement part P-120 [RECOMMENDED]" in report
    assert "- **Back in service:** About 4 hours" in report
    assert "Transfer from DFW; estimated arrival in 2 hours" in report
    assert "- **Affected flights:** FX412, FX908" in report
    assert (
        "- **Packages after redistribution:** 1,200 affected; 300 priority; 40 still at risk"
        in report
    )
    assert "- **Main risk:** Delivery or repair may take longer than estimated." in report
    assert "- **Score:** 84/100" in report
    assert "- **Confidence:** Medium (0.62)" in report
    assert "- **Status:** Provisional" in report
    assert "### Excluded options (compliance check)" in report
    assert "### Next step" in report
    assert "Human approval is required before any action." in report
