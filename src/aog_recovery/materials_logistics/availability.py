"""Deterministic availability and substitute-eligibility checks (ARD-MLG-001..004/008)."""

from collections import defaultdict
from datetime import datetime

from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsDeterministicAssessment,
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartReadinessAssessment,
    PartRole,
    SourcingOption,
    TraceabilityStatus,
)


def evaluate_materials_availability(
    payload: MaterialsLogisticsAssessmentPayload,
    target_station: str | None,
    need_by_time: datetime | None,
) -> MaterialsDeterministicAssessment:
    if need_by_time is not None and (
        need_by_time.tzinfo is None or need_by_time.utcoffset() is None
    ):
        raise ValueError("need-by timestamp must include a timezone")

    eligibility_by_part: dict[str, list[PartEligibilityEvidence]] = defaultdict(list)
    for evidence in payload.part_eligibility:
        eligibility_by_part[evidence.part_number].append(evidence)

    part_assessments = tuple(
        _assess_record(
            record,
            eligibility_by_part.get(record.part_number, []),
            payload.sourcing_options,
            target_station,
            need_by_time,
        )
        for record in payload.part_availability
    )
    statuses = {part.availability_status for part in part_assessments}
    if AvailabilityStatus.AVAILABLE in statuses:
        overall = AvailabilityStatus.AVAILABLE
    elif AvailabilityStatus.LIMITED in statuses:
        overall = AvailabilityStatus.LIMITED
    elif statuses and statuses == {AvailabilityStatus.UNAVAILABLE}:
        overall = AvailabilityStatus.UNAVAILABLE
    else:
        overall = AvailabilityStatus.UNCERTAIN
    return MaterialsDeterministicAssessment(
        availability_status=overall,
        parts=part_assessments,
    )


def _assess_record(
    record: PartAvailabilityRecord,
    eligibility_records: list[PartEligibilityEvidence],
    sourcing_options: tuple[SourcingOption, ...],
    target_station: str | None,
    need_by_time: datetime | None,
) -> PartReadinessAssessment:
    findings: list[str] = []
    eligibility_evidence_references: set[str] = set()
    for eligibility in eligibility_records:
        eligibility_evidence_references.update(eligibility.evidence_references)
    for option in sourcing_options:
        if option.part_number == record.part_number:
            eligibility_evidence_references.update(option.evidence_references)

    eligible: bool | None
    eligibility_findings: list[str]
    if record.role is PartRole.FAILED_PART:
        eligible = None
        eligibility_findings = []
    else:
        eligible, eligibility_findings = _check_eligibility(eligibility_records)
    findings.extend(eligibility_findings)

    physically_available = record.available_quantity >= record.required_quantity
    if not physically_available:
        findings.append("physical_quantity_insufficient")
        availability_status = AvailabilityStatus.UNAVAILABLE
        practical_quantity = 0
        practically_available: bool | None = False
    elif record.minimum_stock_threshold is None:
        findings.append("minimum_stock_threshold_unknown")
        availability_status = AvailabilityStatus.UNCERTAIN
        practical_quantity = None
        practically_available = None
    else:
        practical_quantity = max(0, record.available_quantity - record.minimum_stock_threshold)
        if practical_quantity < record.required_quantity:
            findings.append("below_minimum_stock_threshold")
            availability_status = AvailabilityStatus.LIMITED
            practically_available = False
        else:
            location_consistent = (
                record.location == target_station
                if record.location is not None and target_station is not None
                else None
            )
            if location_consistent is True:
                availability_status = AvailabilityStatus.AVAILABLE
                practically_available = True
            else:
                availability_status, practically_available, location_findings = (
                    _assess_remote_stock(
                        record,
                        sourcing_options,
                        target_station,
                        need_by_time,
                    )
                )
                findings.extend(location_findings)

    location_consistent = (
        record.location == target_station
        if record.location is not None and target_station is not None
        else None
    )
    if location_consistent is None:
        findings.append("location_or_target_station_unknown")

    validity_findings = {
        EvidenceValidity.PARTIAL: "inventory_evidence_partial",
        EvidenceValidity.STALE: "inventory_evidence_stale",
        EvidenceValidity.CONFLICTING: "inventory_evidence_conflicting",
    }
    if record.validity_state in validity_findings:
        findings.append(validity_findings[record.validity_state])
        availability_status = AvailabilityStatus.UNCERTAIN
        practically_available = None

    return PartReadinessAssessment(
        part_number=record.part_number,
        role=record.role,
        availability_status=availability_status,
        physically_available=physically_available,
        practical_quantity=practical_quantity,
        practically_available=practically_available,
        location_consistent=location_consistent,
        eligible=eligible,
        findings=tuple(dict.fromkeys(findings)),
        evidence_references=tuple(
            sorted({record.claim_reference, *eligibility_evidence_references})
        ),
    )


def _check_eligibility(
    evidence_records: list[PartEligibilityEvidence],
) -> tuple[bool, list[str]]:
    if not evidence_records:
        return False, ["eligibility_evidence_missing"]

    findings: list[str] = []
    if len(evidence_records) > 1:
        eligibility_states = {
            (
                evidence.compatibility,
                evidence.authorization,
                evidence.traceability,
            )
            for evidence in evidence_records
        }
        if len(eligibility_states) > 1:
            findings.append("eligibility_evidence_conflicting")

    for evidence in evidence_records:
        if evidence.compatibility is not CompatibilityStatus.COMPATIBLE:
            findings.append(f"compatibility_{evidence.compatibility.value}")
        if evidence.authorization is not AuthorizationStatus.AUTHORIZED:
            findings.append(f"authorization_{evidence.authorization.value}")
        if evidence.traceability is not TraceabilityStatus.VERIFIED:
            findings.append(f"traceability_{evidence.traceability.value}")

    return not findings, list(dict.fromkeys(findings))


def _assess_remote_stock(
    record: PartAvailabilityRecord,
    sourcing_options: tuple[SourcingOption, ...],
    target_station: str | None,
    need_by_time: datetime | None,
) -> tuple[AvailabilityStatus, bool | None, list[str]]:
    findings = ["location_mismatch"]
    if record.location is None or target_station is None:
        return AvailabilityStatus.UNCERTAIN, None, findings
    transfer_quotes = [
        option
        for option in sourcing_options
        if option.part_number == record.part_number
        and option.source_location == record.location
        and option.transfer_required
    ]
    if not transfer_quotes:
        findings.append("transfer_evidence_missing")
        return AvailabilityStatus.UNCERTAIN, None, findings
    if need_by_time is None:
        findings.append("need_by_time_unknown")
        return AvailabilityStatus.UNCERTAIN, None, findings
    known_etas = [option.eta_at for option in transfer_quotes if option.eta_at is not None]
    if not known_etas:
        findings.append("transfer_eta_unknown")
        return AvailabilityStatus.UNCERTAIN, None, findings
    if any(eta <= need_by_time for eta in known_etas):
        return AvailabilityStatus.AVAILABLE, True, findings
    findings.append("transfer_outside_need_by_window")
    return AvailabilityStatus.UNAVAILABLE, False, findings
