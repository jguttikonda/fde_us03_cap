"""Deterministic ranking and close-score selection (ARD-CTL-014..015)."""

from dataclasses import dataclass
from decimal import Decimal

from aog_recovery.controller.models import RankedRecoveryOption, ScoredRecoveryOption

_CLOSE_SCORE_POINTS = Decimal("2.0")


@dataclass(frozen=True, slots=True)
class RankingResult:
    ranked_options: tuple[RankedRecoveryOption, ...]
    requires_human_selection: bool


def rank_options(scored_options: tuple[ScoredRecoveryOption, ...]) -> RankingResult:
    """Rank scores deterministically and group all top options within two points."""
    option_ids = tuple(option.option_id for option in scored_options)
    if len(set(option_ids)) != len(option_ids):
        raise ValueError("scored option IDs must be unique")

    ordered = tuple(
        sorted(scored_options, key=lambda option: (-option.aggregate_score, option.option_id))
    )
    close_group = len(ordered) > 1 and (
        ordered[0].aggregate_score - ordered[1].aggregate_score <= _CLOSE_SCORE_POINTS
    )
    ranked = tuple(
        RankedRecoveryOption.model_validate(
            {
                **option.model_dump(),
                "rank": index,
                "selection_group": (
                    1
                    if close_group
                    and ordered[0].aggregate_score - option.aggregate_score <= _CLOSE_SCORE_POINTS
                    else None
                ),
            }
        )
        for index, option in enumerate(ordered, start=1)
    )
    return RankingResult(ranked_options=ranked, requires_human_selection=close_group)
