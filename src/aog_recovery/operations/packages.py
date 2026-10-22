from collections import defaultdict
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from aog_recovery.contracts.base import ContractModel
from aog_recovery.operations.contracts import (
    PackageRedistribution,
    PackageServiceCount,
    RejectedAllocationTarget,
    TailPackageAllocation,
)

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonNegativeCount = Annotated[int, Field(ge=0)]


class PackageCohort(ContractModel):
    cohort_id: NonEmptyString
    service_level: NonEmptyString
    package_count: NonNegativeCount
    ready_at: AwareDatetime


class RedistributionTarget(ContractModel):
    tail_id: NonEmptyString
    remaining_capacity: NonNegativeCount
    packages_arrive_at: AwareDatetime
    sort_window_start: AwareDatetime
    sort_window_end: AwareDatetime
    cutoff_at: AwareDatetime

    @model_validator(mode="after")
    def require_valid_handling_window(self) -> RedistributionTarget:
        if self.sort_window_end <= self.sort_window_start:
            raise ValueError("sort_window_end must be after sort_window_start")
        return self


def _cohort_fits_target(cohort: PackageCohort, target: RedistributionTarget) -> bool:
    ready_at = max(cohort.ready_at, target.packages_arrive_at)
    latest_handling_time = min(target.sort_window_end, target.cutoff_at)
    return (
        ready_at <= target.cutoff_at
        and max(ready_at, target.sort_window_start) <= latest_handling_time
    )


def redistribute_packages(
    manifest: tuple[PackageCohort, ...],
    targets: tuple[RedistributionTarget, ...],
    service_level_order: tuple[str, ...],
) -> PackageRedistribution:
    if len({cohort.cohort_id for cohort in manifest}) != len(manifest):
        raise ValueError("package cohort identifiers must be unique")
    if len({target.tail_id for target in targets}) != len(targets):
        raise ValueError("redistribution target tail identifiers must be unique")
    if len(set(service_level_order)) != len(service_level_order):
        raise ValueError("service-level order must not contain duplicates")

    service_levels = {cohort.service_level for cohort in manifest}
    missing_levels = service_levels - set(service_level_order)
    if missing_levels:
        raise ValueError("service-level order is missing: " + ", ".join(sorted(missing_levels)))

    service_rank = {service_level: rank for rank, service_level in enumerate(service_level_order)}
    ordered_manifest = sorted(
        enumerate(manifest),
        key=lambda entry: (service_rank[entry[1].service_level], entry[0]),
    )
    remaining = {cohort.cohort_id: cohort.package_count for _, cohort in ordered_manifest}
    protected_by_service: dict[str, int] = defaultdict(int)
    protected_by_tail: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rejected_reasons: dict[str, str] = {}
    capacities = {target.tail_id: target.remaining_capacity for target in targets}

    for _, cohort in ordered_manifest:
        for target in targets:
            if remaining[cohort.cohort_id] == 0:
                break
            if not _cohort_fits_target(cohort, target):
                rejected_reasons[target.tail_id] = (
                    f"Packages in cohort {cohort.cohort_id} miss the target sort or cut-off window."
                )
                continue
            available = capacities[target.tail_id]
            if available == 0:
                continue
            count = min(remaining[cohort.cohort_id], available)
            protected_by_tail[target.tail_id][cohort.service_level] += count
            protected_by_service[cohort.service_level] += count
            capacities[target.tail_id] -= count
            remaining[cohort.cohort_id] -= count

    total_by_service: dict[str, int] = defaultdict(int)
    unprotected_by_service: dict[str, int] = defaultdict(int)
    for _, cohort in ordered_manifest:
        total_by_service[cohort.service_level] += cohort.package_count
        unprotected_by_service[cohort.service_level] += remaining[cohort.cohort_id]

    protected_counts = tuple(
        PackageServiceCount(service_level=service_level, package_count=count)
        for service_level, count in sorted(
            protected_by_service.items(),
            key=lambda item: service_rank[item[0]],
        )
        if count
    )
    unprotected_counts = tuple(
        PackageServiceCount(service_level=service_level, package_count=count)
        for service_level, count in sorted(
            unprotected_by_service.items(),
            key=lambda item: service_rank[item[0]],
        )
        if count
    )
    allocations = tuple(
        TailPackageAllocation(
            tail_id=target.tail_id,
            capacity=target.remaining_capacity,
            package_count=sum(protected_by_tail[target.tail_id].values()),
            packages_by_service_level=tuple(
                PackageServiceCount(service_level=service_level, package_count=count)
                for service_level, count in sorted(
                    protected_by_tail[target.tail_id].items(),
                    key=lambda item: service_rank[item[0]],
                )
            ),
        )
        for target in targets
        if protected_by_tail[target.tail_id]
    )
    rejected_targets = tuple(
        RejectedAllocationTarget(tail_id=tail_id, reason=reason)
        for tail_id, reason in sorted(rejected_reasons.items())
    )

    return PackageRedistribution(
        total_package_count=sum(total_by_service.values()),
        protected_by_service_level=protected_counts,
        unprotected_by_service_level=unprotected_counts,
        allocations=allocations,
        rejected_targets=rejected_targets,
    )
