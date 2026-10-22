from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.contracts.readiness import EtaBasis, ReadinessEstimate
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.context import ControllerAuditRecorder, InMemoryControllerContextStore
from aog_recovery.controller.intake import prepare_intake
from aog_recovery.controller.models import (
    CandidateSource,
    ControllerIntake,
    RoutingOmission,
    SourceHealthRecord,
    SourceHealthStatus,
)
from aog_recovery.materials_logistics.models import SourcingMethod, SourcingOption
from aog_recovery.operations.models import OptionKind, PackageLoadData


def test_controller_intake_reuses_validated_case_and_evidence(
    valid_case_payload: dict[str, object],
) -> None:
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(
            {
                "evidence_id": "evidence-001",
                "source": "synthetic-maintenance",
                "retrieved_at": datetime(2026, 10, 21, tzinfo=UTC),
                "validity_state": EvidenceValidity.CURRENT,
                "claim_reference": "repairability",
                "content": {},
            },
        ),
    )

    assert intake.case.case_id == valid_case_payload["case_id"]
    assert intake.evidence[0].evidence_id == "evidence-001"


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": "1.0", "case": {}, "evidence": ()},
        {"schema_version": "2.0", "case": {}, "evidence": ()},
        {
            "schema_version": "1.0",
            "case": {},
            "evidence": (),
            "untrusted_extra": "must be rejected",
        },
    ],
)
def test_controller_intake_rejects_invalid_versions_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ControllerIntake.model_validate(payload)


def test_source_health_requires_reason_when_degraded() -> None:
    with pytest.raises(ValidationError, match="requires a reason"):
        SourceHealthRecord(
            source_id="maintenance-records",
            status=SourceHealthStatus.UNAVAILABLE,
            checked_at=datetime(2026, 10, 21, tzinfo=UTC),
            evidence_references=(),
        )


def test_invalid_intake_has_findings_and_no_route(valid_case_payload: dict[str, object]) -> None:
    del valid_case_payload["case_id"]
    valid_case_payload["untrusted"] = "ignored nowhere"
    payload = {"schema_version": "1.0", "case": valid_case_payload, "evidence": []}

    result = prepare_intake(payload, validated_at=datetime(2026, 10, 21, tzinfo=UTC))

    assert not result.validation.is_valid
    assert result.intake is None
    assert result.routing is None
    assert {finding.field_path for finding in result.validation.findings} == {
        "case.case_id",
        "case.untrusted",
    }


def test_valid_intake_routes_all_specialists_and_exposes_unknown_health(
    valid_case_payload: dict[str, object],
) -> None:
    result = prepare_intake(
        {"schema_version": "1.0", "case": valid_case_payload, "evidence": []},
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
    )

    assert result.validation.is_valid
    assert result.routing is not None
    assert result.routing.selected_roles == (
        AgentRole.MAINTENANCE,
        AgentRole.MATERIALS_LOGISTICS,
        AgentRole.OPERATIONS,
    )
    assert result.routing.omitted_roles == ()
    assert {item.status for item in result.routing.source_health} == {SourceHealthStatus.UNKNOWN}


def test_routing_retains_unavailable_source_and_explicit_omission(
    valid_case_payload: dict[str, object],
) -> None:
    unavailable = {
        "source_id": "materials-catalog",
        "agent_role": AgentRole.MATERIALS_LOGISTICS,
        "status": SourceHealthStatus.UNAVAILABLE,
        "checked_at": datetime(2026, 10, 21, tzinfo=UTC),
        "evidence_references": (),
        "reason": "synthetic catalog outage",
    }
    omission = RoutingOmission(
        agent_role=AgentRole.OPERATIONS,
        reason="case contains no affected flight data",
    )
    result = prepare_intake(
        {
            "schema_version": "1.0",
            "case": valid_case_payload,
            "evidence": [],
            "source_health": [unavailable],
        },
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
        omitted_specialists=(omission,),
    )

    assert result.routing is not None
    assert result.routing.selected_roles == (AgentRole.MAINTENANCE, AgentRole.MATERIALS_LOGISTICS)
    assert result.routing.omitted_roles == (omission,)
    assert any(
        item.source_id == "materials-catalog" and item.status is SourceHealthStatus.UNAVAILABLE
        for item in result.routing.source_health
    )
    assert any("case contains no affected flight data" in item for item in result.routing.rationale)


def test_intake_and_routing_events_are_correlated_and_invalid_intake_stays_unrouted(
    valid_case_payload: dict[str, object],
) -> None:
    store = InMemoryControllerContextStore()
    audit = ControllerAuditRecorder(store)
    payload = {"schema_version": "1.0", "case": valid_case_payload, "evidence": []}

    accepted = prepare_intake(
        payload,
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
        audit_recorder=audit,
    )
    rejected_case = dict(valid_case_payload)
    rejected_case.pop("aircraft_id")
    rejected = prepare_intake(
        {"schema_version": "1.0", "case": rejected_case, "evidence": []},
        validated_at=datetime(2026, 10, 21, tzinfo=UTC),
        audit_recorder=audit,
    )

    events = store.events_for(valid_case_payload["case_id"])
    assert [event.event_type for event in events] == [
        "controller_intake_validation",
        "controller_routing",
        "controller_intake_validation",
    ]
    assert {event.trace_context.correlation_id for event in events} == {"corr-synthetic-001"}
    assert events[-1].status == "rejected"
    assert accepted.audit_errors == ()
    assert rejected.routing is None
    assert not rejected.validation.is_valid
    assert rejected.audit_errors == ()


@pytest.mark.parametrize(
    "kind",
    [
        OptionKind.REPAIR_ORIGINAL,
        OptionKind.REPAIR_ALTERNATE,
        OptionKind.SWAP,
        OptionKind.DELAY,
    ],
)
def test_candidate_construction_is_stable_unranked_and_preserves_missing_inputs(
    kind: OptionKind,
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    source = CandidateSource(
        source_key=f"source-{kind.value}",
        kind=kind,
        source_evidence_references=(current_evidence.evidence_id,),
        readiness=ReadinessEstimate(
            source_agent=AgentRole.MAINTENANCE,
            eta=datetime(2026, 10, 21, 15, 0, tzinfo=UTC),
            basis=EtaBasis.ESTIMATED,
            evidence_references=(current_evidence.evidence_id,),
        ),
        package_load=PackageLoadData(groups=()),
        package_load_evidence_references=(current_evidence.evidence_id,),
    )
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(source,),
    )

    first = build_candidates(intake)[0]
    second = build_candidates(intake)[0]

    assert first.candidate.option_id == second.candidate.option_id
    assert first.candidate.kind is kind
    assert first.candidate.readiness_eta == datetime(2026, 10, 21, 15, 0, tzinfo=UTC)
    expected_missing_data = (
        ("failed_part_number", "sourcing_options")
        if kind in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
        else ()
    )
    assert first.missing_data == expected_missing_data
    assert not hasattr(first.candidate, "score")
    assert not hasattr(first.candidate, "rank")


def test_candidate_construction_does_not_invent_readiness_or_package_data(
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(
            CandidateSource(
                source_key="delay-evidence",
                kind=OptionKind.DELAY,
                source_evidence_references=(current_evidence.evidence_id,),
            ),
        ),
    )

    candidate = build_candidates(intake)[0]

    assert candidate.candidate.readiness_eta is None
    assert candidate.candidate.eta_evidence_references == ()
    assert candidate.package_load is None
    assert candidate.missing_data == ("readiness_eta", "package_load")


def test_candidate_retains_its_sourcing_and_package_load_inputs(
    valid_case_payload: dict[str, object],
    current_evidence,
) -> None:
    sourcing = SourcingOption(
        part_number="P-120",
        source="synthetic-station",
        source_location="TEST-STATION-002",
        method=SourcingMethod.INTERNAL_TRANSFER,
        shipping_provider=None,
        shipping_service=None,
        transfer_required=True,
        lead_time_hours=4,
        eta_at=datetime(2026, 10, 21, 16, 0, tzinfo=UTC),
        estimated_cost_usd=Decimal("125.00"),
        quote_unavailable_reason=None,
        evidence_references=(current_evidence.evidence_id,),
    )
    package_load = PackageLoadData(groups=())
    intake = ControllerIntake(
        schema_version="1.0",
        case=valid_case_payload,
        evidence=(current_evidence,),
        candidate_sources=(
            CandidateSource(
                source_key="alternate-part-p120",
                kind=OptionKind.REPAIR_ALTERNATE,
                source_evidence_references=(current_evidence.evidence_id,),
                sourcing_options=(sourcing,),
                package_load=package_load,
                package_load_evidence_references=(current_evidence.evidence_id,),
            ),
        ),
    )

    candidate = build_candidates(intake)[0]

    assert candidate.sourcing_options == (sourcing,)
    assert candidate.package_load == package_load
    assert candidate.package_load_evidence_references == (current_evidence.evidence_id,)
