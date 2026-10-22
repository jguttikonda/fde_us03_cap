"""Build traceable recovery candidates from validated specialist evidence (ARD-CTL-018)."""

from datetime import timedelta
from math import inf

from aog_recovery.contracts.readiness import SourcingMethod as ReadinessSourcingMethod
from aog_recovery.controller.models import CandidateBuildContext, RecoveryCandidatePlan
from aog_recovery.materials_logistics.models import (
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartRole,
    SourcingMethod,
    SourcingOption,
)
from aog_recovery.operations.models import CandidateOption, EtaBasis, OptionKind


def build_recovery_candidates(
    context: CandidateBuildContext,
) -> tuple[RecoveryCandidatePlan, ...]:
    plans: list[RecoveryCandidatePlan] = []
    repair_plans: list[RecoveryCandidatePlan] = []
    materials = context.materials_assessment
    missing: tuple[str, ...] = ()

    if materials is None:
        missing = ("materials_assessment", "part_availability")
    else:
        targets: list[tuple[str, PartRole, OptionKind]] = [
            (context.failed_part_number, PartRole.FAILED_PART, OptionKind.REPAIR_ORIGINAL)
        ]
        preferred = context.preferred_replacement_part
        if preferred is not None and preferred != context.failed_part_number:
            targets.append((preferred, PartRole.PREFERRED_REPLACEMENT, OptionKind.REPAIR_ALTERNATE))
        targets.extend(
            (record.part_number, PartRole.ALTERNATE, OptionKind.REPAIR_ALTERNATE)
            for record in materials.part_availability
            if record.role is PartRole.ALTERNATE
            and record.part_number not in {part_number for part_number, _, _ in targets}
        )

        for part_number, role, kind in targets:
            available_records = tuple(
                sorted(
                    (
                        record
                        for record in materials.part_availability
                        if record.part_number == part_number
                        and record.role is role
                        and record.available_quantity >= record.required_quantity
                    ),
                    key=lambda record: (
                        record.location or "",
                        record.source,
                        record.claim_reference,
                    ),
                )
            )
            if not available_records:
                if not any(
                    record.part_number == part_number and record.role is role
                    for record in materials.part_availability
                ):
                    missing = (*missing, f"part_availability:{part_number}")
                continue

            eligibility = next(
                (item for item in materials.part_eligibility if item.part_number == part_number),
                None,
            )
            source_options = tuple(
                sorted(
                    (
                        option
                        for option in materials.sourcing_options
                        if option.part_number == part_number
                    ),
                    key=_sourcing_order,
                )
            )
            if not source_options:
                plans.append(
                    _build_repair_plan(
                        context,
                        part_number,
                        kind,
                        available_records,
                        eligibility,
                        None,
                    )
                )
                continue
            repair_plans.extend(
                _build_repair_plan(
                    context,
                    part_number,
                    kind,
                    available_records,
                    eligibility,
                    source,
                )
                for source in source_options
            )

    plans.extend(repair_plans)
    plans.append(
        RecoveryCandidatePlan(
            option=CandidateOption(
                option_id=f"OPT-SWAP-{context.case.case_id}",
                kind=OptionKind.SWAP,
                description="Assess a serviceable substitute aircraft for affected flights.",
                readiness_eta=None,
                eta_basis=None,
                eta_evidence_references=(),
            ),
            part_number=None,
            inventory_records=(),
            eligibility=None,
            sourcing_option=None,
            missing_data=missing,
            warnings=(),
        )
    )

    ready_repairs = [plan for plan in repair_plans if plan.option.readiness_eta is not None]
    earliest_repair = min(ready_repairs, key=_candidate_eta, default=None)
    plans.append(
        RecoveryCandidatePlan(
            option=CandidateOption(
                option_id=f"OPT-DELAY-{context.case.case_id}",
                kind=OptionKind.DELAY,
                description="Delay the affected flight until a supported repair path is ready.",
                readiness_eta=(
                    earliest_repair.option.readiness_eta if earliest_repair is not None else None
                ),
                eta_basis=(
                    earliest_repair.option.eta_basis if earliest_repair is not None else None
                ),
                eta_evidence_references=(
                    earliest_repair.option.eta_evidence_references
                    if earliest_repair is not None
                    else ()
                ),
            ),
            part_number=earliest_repair.part_number if earliest_repair is not None else None,
            inventory_records=(
                earliest_repair.inventory_records if earliest_repair is not None else ()
            ),
            eligibility=earliest_repair.eligibility if earliest_repair is not None else None,
            sourcing_option=(
                earliest_repair.sourcing_option if earliest_repair is not None else None
            ),
            missing_data=missing,
            warnings=(),
        )
    )
    return tuple(plans)


def _build_repair_plan(
    context: CandidateBuildContext,
    part_number: str,
    kind: OptionKind,
    inventory_records: tuple[PartAvailabilityRecord, ...],
    eligibility: PartEligibilityEvidence | None,
    source: SourcingOption | None,
) -> RecoveryCandidatePlan:
    role_suffix = "ORIGINAL" if kind is OptionKind.REPAIR_ORIGINAL else "ALTERNATE"
    location_suffix = source.source_location if source is not None else "NO-QUOTE"
    source_suffix = source.method.value if source is not None else "unknown"
    option_id = (
        f"OPT-REPAIR-{role_suffix}-{part_number}-{source_suffix}-{location_suffix or 'unknown'}"
    )
    source_eta = source.eta_at if source is not None else None
    readiness_eta = (
        source_eta + timedelta(hours=context.estimated_repair_duration_hours)
        if source_eta is not None and context.estimated_repair_duration_hours is not None
        else None
    )
    evidence_references = set(context.maintenance_evidence_references)
    evidence_references.update(record.claim_reference for record in inventory_records)
    if eligibility is not None:
        evidence_references.update(eligibility.evidence_references)
    if source is not None:
        evidence_references.update(source.evidence_references)

    missing_data: list[str] = []
    if source is None:
        missing_data.append(f"sourcing_option:{part_number}")
    elif source_eta is None:
        missing_data.append(f"sourcing_eta:{part_number}")
    if context.estimated_repair_duration_hours is None:
        missing_data.append("estimated_repair_duration_hours")

    warnings = tuple(
        f"{record.claim_reference} is {record.validity_state.value}"
        for record in inventory_records
        if record.validity_state.value != "current"
    )
    candidate = CandidateOption(
        option_id=option_id,
        kind=kind,
        description=(
            f"Repair with part {part_number} from "
            f"{source.source_location if source is not None else 'an unconfirmed source'}."
        ),
        readiness_eta=readiness_eta,
        eta_basis=EtaBasis.ESTIMATED if readiness_eta is not None else None,
        eta_evidence_references=tuple(sorted(evidence_references)) if readiness_eta else (),
        sourcing_method=(_readiness_sourcing_method(source.method) if source is not None else None),
    )
    return RecoveryCandidatePlan(
        option=candidate,
        part_number=part_number,
        inventory_records=inventory_records,
        eligibility=eligibility,
        sourcing_option=source,
        missing_data=tuple(sorted(set(missing_data))),
        warnings=warnings,
    )


def _sourcing_order(option: SourcingOption) -> tuple[bool, float, float, str, str]:
    return (
        option.eta_at is None,
        option.eta_at.timestamp() if option.eta_at is not None else float("inf"),
        option.lead_time_hours if option.lead_time_hours is not None else float("inf"),
        option.source,
        option.method.value,
    )


def _candidate_eta(plan: RecoveryCandidatePlan) -> float:
    eta = plan.option.readiness_eta
    return eta.timestamp() if eta is not None else inf


def _readiness_sourcing_method(method: SourcingMethod) -> ReadinessSourcingMethod:
    if method.value == "borrow_pool":
        return ReadinessSourcingMethod.BORROW
    return ReadinessSourcingMethod(method.value)
