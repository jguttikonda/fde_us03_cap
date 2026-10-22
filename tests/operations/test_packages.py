from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from aog_recovery.operations.assessment import OptionCostRates, estimate_option_cost
from aog_recovery.operations.contracts import RecoveryCandidate, RecoveryOptionKind
from aog_recovery.operations.packages import (
    PackageCohort,
    RedistributionTarget,
    redistribute_packages,
)

READY = datetime(2026, 10, 21, 14, 0, tzinfo=UTC)
SORT_START = datetime(2026, 10, 21, 14, 0, tzinfo=UTC)
SORT_END = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)
CUTOFF = datetime(2026, 10, 21, 17, 30, tzinfo=UTC)
REQUIREMENT_TO_TEST = {
    "ARD-OPS-009": (
        "test_priority_packages_are_protected_within_tail_capacity",
        "test_cutoff_rejection_preserves_unprotected_packages",
        "test_operations_proposal_scenario_three_counts_follow_priority_and_cutoff",
    ),
    "ARD-TST-006": (
        "test_priority_packages_are_protected_within_tail_capacity",
        "test_operations_proposal_scenario_three_counts_follow_priority_and_cutoff",
    ),
}


def target(
    tail_id: str,
    capacity: int,
    *,
    arrival: datetime = READY,
    sort_start: datetime = SORT_START,
    sort_end: datetime = SORT_END,
    cutoff: datetime = CUTOFF,
) -> RedistributionTarget:
    return RedistributionTarget(
        tail_id=tail_id,
        remaining_capacity=capacity,
        packages_arrive_at=arrival,
        sort_window_start=sort_start,
        sort_window_end=sort_end,
        cutoff_at=cutoff,
    )


def test_requirement_to_test_map_covers_package_requirements() -> None:
    assert set(REQUIREMENT_TO_TEST) == {"ARD-OPS-009", "ARD-TST-006"}
    assert all(test_names for test_names in REQUIREMENT_TO_TEST.values())


def test_priority_packages_are_protected_within_tail_capacity() -> None:
    manifest = (
        PackageCohort(
            cohort_id="priority-packages",
            service_level="priority",
            package_count=700,
            ready_at=READY,
        ),
        PackageCohort(
            cohort_id="standard-packages",
            service_level="standard",
            package_count=500,
            ready_at=READY,
        ),
    )

    allocation = redistribute_packages(
        manifest,
        (target("FX207", 900),),
        ("priority", "standard"),
    )

    assert allocation.total_package_count == 1200
    assert tuple(
        (item.service_level, item.package_count) for item in allocation.protected_by_service_level
    ) == (
        ("priority", 700),
        ("standard", 200),
    )
    assert tuple(
        (item.service_level, item.package_count) for item in allocation.unprotected_by_service_level
    ) == (("standard", 300),)
    assert allocation.allocations[0].package_count == 900
    assert allocation.allocations[0].packages_by_service_level[0].service_level == "priority"

    candidate = RecoveryCandidate(
        option_id="swap-FX207",
        kind=RecoveryOptionKind.SWAP,
        description="Redistribute to spare tail",
        substitute_tail_id="FX207",
    )
    cost = estimate_option_cost(
        candidate,
        0,
        sum(item.package_count for item in allocation.unprotected_by_service_level),
        OptionCostRates(
            currency="USD",
            delay_per_minute=Decimal("1.00"),
            swap_flat_cost=Decimal("0"),
            unprotected_package_exposure=Decimal("2.00"),
        ),
    )
    assert cost.total == Decimal("600.00")


def test_cutoff_rejection_preserves_unprotected_packages() -> None:
    too_late = READY + timedelta(hours=2)
    allocation = redistribute_packages(
        (
            PackageCohort(
                cohort_id="late-priority",
                service_level="priority",
                package_count=10,
                ready_at=too_late,
            ),
        ),
        (
            target(
                "FX955",
                100,
                arrival=too_late,
                sort_end=too_late + timedelta(hours=1),
                cutoff=READY + timedelta(hours=1),
            ),
        ),
        ("priority",),
    )

    assert allocation.protected_by_service_level == ()
    assert allocation.unprotected_by_service_level[0].package_count == 10
    assert allocation.rejected_targets[0].tail_id == "FX955"
    assert "cut-off" in allocation.rejected_targets[0].reason


def test_operations_proposal_scenario_three_counts_follow_priority_and_cutoff() -> None:
    cutoff = READY + timedelta(hours=1)
    manifest = (
        PackageCohort(
            cohort_id="priority-ready",
            service_level="priority",
            package_count=170,
            ready_at=READY,
        ),
        PackageCohort(
            cohort_id="priority-late",
            service_level="priority",
            package_count=10,
            ready_at=cutoff + timedelta(minutes=1),
        ),
        PackageCohort(
            cohort_id="standard-ready-for-FX207",
            service_level="standard",
            package_count=830,
            ready_at=READY,
        ),
        PackageCohort(
            cohort_id="standard-ready-for-FX955",
            service_level="standard",
            package_count=150,
            ready_at=READY + timedelta(minutes=30),
        ),
        PackageCohort(
            cohort_id="standard-late",
            service_level="standard",
            package_count=40,
            ready_at=cutoff + timedelta(minutes=1),
        ),
    )
    allocation = redistribute_packages(
        manifest,
        (
            target("FX207", 1000, sort_end=cutoff + timedelta(hours=1), cutoff=cutoff),
            target("FX955", 300, sort_end=cutoff + timedelta(hours=1), cutoff=cutoff),
        ),
        ("priority", "standard"),
    )

    assert {item.tail_id: item.package_count for item in allocation.allocations} == {
        "FX207": 1000,
        "FX955": 150,
    }
    assert {
        item.service_level: item.package_count for item in allocation.unprotected_by_service_level
    } == {"priority": 10, "standard": 40}
    assert allocation.total_package_count == 1200


def test_missing_service_level_order_fails_visibly() -> None:
    manifest = (
        PackageCohort(
            cohort_id="standard-1",
            service_level="standard",
            package_count=1,
            ready_at=READY,
        ),
    )

    with pytest.raises(ValueError, match="service-level order is missing"):
        redistribute_packages(manifest, (target("FX207", 1),), ("priority",))


def test_redistribution_is_repeatable_for_identical_inputs() -> None:
    manifest = (
        PackageCohort(
            cohort_id="priority-1",
            service_level="priority",
            package_count=10,
            ready_at=READY,
        ),
        PackageCohort(
            cohort_id="standard-1",
            service_level="standard",
            package_count=10,
            ready_at=READY,
        ),
    )
    targets = (target("FX207", 12), target("FX955", 4))

    first = redistribute_packages(manifest, targets, ("priority", "standard"))
    second = redistribute_packages(manifest, targets, ("priority", "standard"))

    assert first == second
