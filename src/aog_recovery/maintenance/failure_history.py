"""Deterministic recurring-failure analysis from source-backed records (ARD-MNT-009)."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta

from pydantic import ValidationError

from aog_recovery.config import AogSettings
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.maintenance.models import (
    MaintenanceFailureOccurrence,
    RecurringFailureAnalysis,
    RecurringFailureSummary,
)
from aog_recovery.validation.models import ValidationFinding


def analyze_recurring_failures(
    evidence_records: Iterable[Evidence],
    as_of: datetime,
    settings: AogSettings,
) -> RecurringFailureAnalysis:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must include a timezone")

    cutoff = as_of - timedelta(days=settings.maintenance_recurrence_window_days)
    occurrences_by_part: dict[str, list[MaintenanceFailureOccurrence]] = defaultdict(list)
    findings: list[ValidationFinding] = []

    for record in evidence_records:
        content = record.content
        if "part_number" not in content and "occurred_at" not in content:
            continue
        try:
            occurrence = MaintenanceFailureOccurrence.model_validate(
                {
                    "part_number": content.get("part_number"),
                    "occurred_at": content.get("occurred_at"),
                    "evidence_reference": record.evidence_id,
                }
            )
        except ValidationError as error:
            findings.extend(
                ValidationFinding(
                    field_path=(
                        f"maintenance_history[{record.evidence_id}]."
                        f"{'.'.join(str(part) for part in issue['loc'])}"
                    ),
                    code=issue["type"],
                    message=issue["msg"],
                )
                for issue in error.errors(include_input=False)
            )
            continue

        if record.validity_state is not EvidenceValidity.CURRENT:
            findings.append(
                ValidationFinding(
                    field_path=f"maintenance_history[{record.evidence_id}]",
                    code=f"{record.validity_state.value}_evidence",
                    message="failure history was not counted because its evidence is not current",
                )
            )
            continue
        if occurrence.occurred_at > as_of:
            findings.append(
                ValidationFinding(
                    field_path=f"maintenance_history[{record.evidence_id}].occurred_at",
                    code="future_failure_timestamp",
                    message="failure occurrence is later than the assessment time",
                )
            )
            continue
        if cutoff <= occurrence.occurred_at <= as_of:
            occurrences_by_part[occurrence.part_number].append(occurrence)

    summaries = tuple(
        RecurringFailureSummary(
            part_number=part_number,
            occurrences=len(occurrences),
            window_days=settings.maintenance_recurrence_window_days,
            evidence_references=tuple(
                sorted(occurrence.evidence_reference for occurrence in occurrences)
            ),
        )
        for part_number, occurrences in sorted(occurrences_by_part.items())
        if len(occurrences) >= settings.maintenance_recurrence_threshold
    )
    return RecurringFailureAnalysis(
        summaries=summaries,
        findings=tuple(sorted(findings, key=lambda finding: (finding.field_path, finding.code))),
    )
