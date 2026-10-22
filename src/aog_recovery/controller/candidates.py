"""Deterministic unranked candidate construction from validated case evidence (ARD-CTL-018)."""

import json
from hashlib import sha256

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.evidence import Evidence
from aog_recovery.contracts.readiness import (
    EtaBasis,
    ReadinessEstimate,
)
from aog_recovery.contracts.readiness import (
    SourcingMethod as CandidateSourcingMethod,
)
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
    definitions: list[CandidateDefinition] = []
    for source in intake.candidate_sources:
        variants = (
            tuple(
                source.model_copy(update={"sourcing_options": (option,)})
                for option in source.sourcing_options
            )
            if source.sourcing_options
            else (source,)
        )
        definitions.extend(
            _build_candidate(intake.case.case_id, variant, evidence_by_id) for variant in variants
        )
    return tuple(definitions)


def _build_candidate(
    case_id: str,
    source: CandidateSource,
    evidence_by_id: dict[str, Evidence],
) -> CandidateDefinition:
    sourcing_option = source.sourcing_options[0] if source.sourcing_options else None
    readiness = _candidate_readiness(source, sourcing_option)
    identity = {
        "kind": source.kind.value,
        "source_key": source.source_key,
        "failed_part_number": source.failed_part_number,
        "source_evidence_references": sorted(source.source_evidence_references),
        "readiness": source.readiness.model_dump(mode="json") if source.readiness else None,
        "sourcing_option": (
            sourcing_option.model_dump(mode="json") if sourcing_option is not None else None
        ),
        "package_load": source.package_load.model_dump(mode="json")
        if source.package_load
        else None,
        "package_load_evidence_references": sorted(source.package_load_evidence_references),
    }
    reference_material = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    identifier = sha256(reference_material.encode("utf-8")).hexdigest()[:12]
    candidate_id = f"{case_id}-{source.kind.value}-{identifier}"
    description = _DESCRIPTIONS[source.kind]
    if sourcing_option is not None:
        description = (
            f"{description} using {sourcing_option.part_number} via "
            f"{sourcing_option.method.value} from {sourcing_option.source}"
        )
    candidate = CandidateOption(
        option_id=candidate_id,
        kind=source.kind,
        description=description,
        readiness_eta=readiness.eta if readiness is not None else None,
        eta_basis=readiness.basis if readiness is not None else None,
        eta_evidence_references=(readiness.evidence_references if readiness is not None else ()),
        sourcing_method=(
            _SOURCING_METHODS[sourcing_option.method] if sourcing_option is not None else None
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
            missing_data.append("sourcing_eta")
        elif sourcing_option is None or sourcing_option.eta_at is None:
            missing_data.append("sourcing_eta")
    if source.package_load is None:
        missing_data.append("package_load")

    evidence_references = set(source.source_evidence_references)
    if source.readiness is not None:
        evidence_references.update(source.readiness.evidence_references)
    if sourcing_option is not None:
        evidence_references.update(sourcing_option.evidence_references)
    evidence_references.update(source.package_load_evidence_references)

    return CandidateDefinition(
        candidate=candidate,
        source=source,
        failed_part_number=source.failed_part_number,
        source_evidence=tuple(
            evidence_by_id[reference] for reference in sorted(evidence_references)
        ),
        sourcing_options=(sourcing_option,) if sourcing_option is not None else (),
        package_load=source.package_load,
        package_load_evidence_references=source.package_load_evidence_references,
        missing_data=tuple(missing_data),
    )


def _candidate_readiness(
    source: CandidateSource,
    sourcing_option: SourcingOption | None,
) -> ReadinessEstimate | None:
    if source.kind not in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}:
        return source.readiness
    if source.readiness is None or sourcing_option is None or sourcing_option.eta_at is None:
        return None

    eta = max(source.readiness.eta, sourcing_option.eta_at)
    eta_source = (
        AgentRole.MATERIALS_LOGISTICS
        if sourcing_option.eta_at >= source.readiness.eta
        else source.readiness.source_agent
    )
    return ReadinessEstimate(
        source_agent=eta_source,
        eta=eta,
        basis=EtaBasis.ESTIMATED,
        evidence_references=tuple(
            sorted(set(source.readiness.evidence_references + sourcing_option.evidence_references))
        ),
    )
