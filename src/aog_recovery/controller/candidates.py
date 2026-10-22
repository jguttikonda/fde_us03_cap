"""Deterministic unranked candidate construction from validated case evidence (ARD-CTL-018)."""

from hashlib import sha256

from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.evidence import Evidence
from aog_recovery.contracts.readiness import SourcingMethod as CandidateSourcingMethod
from aog_recovery.controller.models import CandidateSource, ControllerIntake, NonEmptyString
from aog_recovery.materials_logistics.models import SourcingMethod, SourcingOption
from aog_recovery.operations.models import CandidateOption, OptionKind, PackageLoadData


class CandidateDefinition(ContractModel):
    """Candidate and its candidate-specific sourcing/package evidence inputs."""

    candidate: CandidateOption
    source: CandidateSource
    failed_part_number: NonEmptyString | None
    source_evidence: tuple[Evidence, ...]
    sourcing_options: tuple[SourcingOption, ...]
    package_load: PackageLoadData | None
    package_load_evidence_references: tuple[NonEmptyString, ...]
    missing_data: tuple[NonEmptyString, ...]


_DESCRIPTIONS = {
    OptionKind.REPAIR_ORIGINAL: "Repair using the original part",
    OptionKind.REPAIR_ALTERNATE: "Repair using a supported replacement or alternate part",
    OptionKind.SWAP: "Aircraft swap",
    OptionKind.DELAY: "Flight delay",
}

_SOURCING_METHODS = {
    SourcingMethod.INTERNAL_TRANSFER: CandidateSourcingMethod.INTERNAL_TRANSFER,
    SourcingMethod.BORROW_POOL: CandidateSourcingMethod.BORROW,
    SourcingMethod.VENDOR_PURCHASE: CandidateSourcingMethod.VENDOR_PURCHASE,
    SourcingMethod.EXPEDITE: CandidateSourcingMethod.EXPEDITE,
}


def build_candidates(intake: ControllerIntake) -> tuple[CandidateDefinition, ...]:
    """Build stable candidates without estimating unsupported values or ranking them."""
    evidence_by_id = {item.evidence_id: item for item in intake.evidence}
    definitions = [
        _build_candidate(intake.case.case_id, source, evidence_by_id)
        for source in intake.candidate_sources
    ]
    return tuple(definitions)


def _build_candidate(
    case_id: str,
    source: CandidateSource,
    evidence_by_id: dict[str, Evidence],
) -> CandidateDefinition:
    reference_material = "|".join(
        (source.kind.value, source.source_key, *sorted(source.source_evidence_references))
    )
    identifier = sha256(reference_material.encode("utf-8")).hexdigest()[:12]
    candidate_id = f"{case_id}-{source.kind.value}-{identifier}"
    readiness = source.readiness
    candidate = CandidateOption(
        option_id=candidate_id,
        kind=source.kind,
        description=_DESCRIPTIONS[source.kind],
        readiness_eta=readiness.eta if readiness is not None else None,
        eta_basis=readiness.basis if readiness is not None else None,
        eta_evidence_references=(readiness.evidence_references if readiness is not None else ()),
        sourcing_method=(
            _SOURCING_METHODS[source.sourcing_options[0].method]
            if source.sourcing_options
            else None
        ),
    )
    missing_data: list[str] = []
    if readiness is None:
        missing_data.append("readiness_eta")
    if source.kind in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}:
        if source.failed_part_number is None:
            missing_data.append("failed_part_number")
        if not source.sourcing_options:
            missing_data.append("sourcing_options")
    if source.package_load is None:
        missing_data.append("package_load")

    return CandidateDefinition(
        candidate=candidate,
        source=source,
        failed_part_number=source.failed_part_number,
        source_evidence=tuple(
            evidence_by_id[reference] for reference in source.source_evidence_references
        ),
        sourcing_options=source.sourcing_options,
        package_load=source.package_load,
        package_load_evidence_references=source.package_load_evidence_references,
        missing_data=tuple(missing_data),
    )
