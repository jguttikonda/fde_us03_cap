"""Operations Agent (ARD-OPS-001..009). Advisory only: never ranks, approves, or executes."""

from collections.abc import Mapping
from dataclasses import dataclass

from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.contracts.agent import (
    AgentResult,
    AgentResultStatus,
    AgentRole,
)
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.evidence import (
    Assumption,
    EvidenceConflict,
    EvidenceValidity,
    EvidenceWarning,
    Unknown,
)
from aog_recovery.contracts.tool import ToolName
from aog_recovery.observability.context import correlation_scope
from aog_recovery.observability.structured import emit_event
from aog_recovery.operations.gateway import (
    OperationsToolGateway,
    SourceOutcome,
    SourceStatus,
    SourceView,
)
from aog_recovery.operations.models import (
    IMPACT_ORDER,
    AlternateFlightData,
    ConflictCode,
    EtaBasis,
    FleetAvailabilityData,
    FlightRecord,
    FlightScheduleData,
    ImpactLevel,
    NetworkStatusData,
    OperationsAssessment,
    OperationsOutcome,
    OperationsRecommendation,
    OperationsRequest,
    OptionKind,
    PackageImpactSummary,
    PackageLoadData,
    RecommendationDecision,
    RecoveryOptionAssessment,
    ReplacementFlight,
    RouteConflict,
    Viability,
)
from aog_recovery.operations.reasoning import (
    DETERMINISTIC_MODE,
    DeterministicReasoner,
    OperationsFacts,
    OperationsReasoner,
    OptionFacts,
    validate_judgment,
)
from aog_recovery.operations.rules import (
    CandidateEvaluation,
    EvaluationContext,
    ScheduleValidation,
    evaluate_candidate,
    find_replacement_flights,
    validate_flight_schedule,
)
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.validation.boundaries import validate_contract_json
from aog_recovery.validation.confidence import ConfidenceDisposition, assess_confidence
from aog_recovery.validation.models import ValidationReport

COMPONENT = "operations-agent"

_SOURCE_LABELS: dict[ToolName, str] = {
    ToolName.FLIGHT_SCHEDULE: "flight schedule validation",
    ToolName.FLEET_AVAILABILITY: "substitute aircraft availability",
    ToolName.PACKAGE_LOAD: "package load redistribution",
    ToolName.ALTERNATE_FLIGHTS: "alternate flight search (own network and partners)",
    ToolName.OPERATIONS_STATUS: "network disruption context",
}
_VIABLE = frozenset({Viability.VIABLE, Viability.VIABLE_WITH_RISK})
_CRITICAL_SOURCES = frozenset(
    {ToolName.PACKAGE_LOAD, ToolName.FLEET_AVAILABILITY, ToolName.ALTERNATE_FLIGHTS}
)


@dataclass(frozen=True, slots=True)
class _Sources:
    schedule: SourceOutcome[FlightScheduleData]
    fleet: SourceOutcome[FleetAvailabilityData] | None
    packages: SourceOutcome[PackageLoadData]
    alternates: SourceOutcome[AlternateFlightData]
    network: SourceOutcome[NetworkStatusData]

    def all(self) -> tuple[SourceView, ...]:
        sources: list[SourceView] = [self.schedule, self.packages, self.alternates, self.network]
        if self.fleet is not None:
            sources.append(self.fleet)
        return tuple(sources)


class OperationsAgent:
    def __init__(
        self,
        adapters: Mapping[ToolName, ReadOnlyAdapter],
        reasoner: OperationsReasoner | None = None,
        settings: OperationsSettings | None = None,
    ) -> None:
        self._settings = settings or OperationsSettings()
        self._gateway = OperationsToolGateway(adapters, self._settings)
        self._reasoner: OperationsReasoner = reasoner or DeterministicReasoner()

    def assess_payload(self, payload: object) -> OperationsOutcome | ValidationReport:
        """Validate an untrusted request payload; invalid input yields findings, no assessment."""
        request, report = validate_contract_json(OperationsRequest, payload)
        if request is None:
            return report
        return self.assess(request)

    def assess(self, request: OperationsRequest) -> OperationsOutcome:
        with correlation_scope(
            request.case.case_id, request.case.trace_context, request.request_id
        ):
            return _Assessment(request, self._gateway, self._reasoner, self._settings).run()


class _Assessment:
    """State for one case's run, so concurrent cases never share mutable data (ARD-RES-007)."""

    def __init__(
        self,
        request: OperationsRequest,
        gateway: OperationsToolGateway,
        reasoner: OperationsReasoner,
        settings: OperationsSettings,
    ) -> None:
        self._request = request
        self._gateway = gateway
        self._reasoner = reasoner
        self._settings = settings
        self._events: list[AuditEvent] = []

    def _event(
        self,
        event_type: str,
        status: str,
        rationale: str,
        references: tuple[str, ...] = (),
        details: dict[str, object] | None = None,
    ) -> None:
        event = AuditEvent(
            schema_version="1.0",
            occurred_at=self._request.evaluated_at,
            event_type=event_type,
            case_id=self._request.case.case_id,
            request_id=self._request.request_id,
            trace_context=self._request.case.trace_context,
            component=COMPONENT,
            status=status,
            evidence_references=references,
            rationale=rationale[:500],
            details=details or {},
        )
        self._events.append(event)
        emit_event(event)

    # --- orchestration ---------------------------------------------------------------------

    def run(self) -> OperationsOutcome:
        request = self._request
        self._event(
            "operations_request_validated",
            "accepted",
            f"{len(request.candidates)} candidate option(s) for "
            f"{len(request.affected_flight_numbers)} flight(s)",
        )

        needs_fleet = any(c.kind is OptionKind.SWAP for c in request.candidates)
        sources = _Sources(
            schedule=self._gateway.fetch(request, ToolName.FLIGHT_SCHEDULE, FlightScheduleData),
            fleet=(
                self._gateway.fetch(request, ToolName.FLEET_AVAILABILITY, FleetAvailabilityData)
                if needs_fleet
                else None
            ),
            packages=self._gateway.fetch(request, ToolName.PACKAGE_LOAD, PackageLoadData),
            alternates=self._gateway.fetch(
                request, ToolName.ALTERNATE_FLIGHTS, AlternateFlightData
            ),
            network=self._gateway.fetch(request, ToolName.OPERATIONS_STATUS, NetworkStatusData),
        )
        for source in sources.all():
            self._record_source(source)

        if sources.schedule.data is None:
            return self._failed(
                "flight schedule unavailable; no recovery option could be assessed", sources, ()
            )
        validation = validate_flight_schedule(request, sources.schedule.data)
        if not validation.flights:
            return self._failed(
                "none of the affected flights were found in the schedule",
                sources,
                tuple(
                    f"flight {n} not found in schedule" for n in validation.missing_flight_numbers
                ),
            )
        return self._assess(sources, sources.schedule.data, validation)

    def _record_source(self, source: SourceView) -> None:
        label = _SOURCE_LABELS[source.tool_name]
        if source.status is SourceStatus.FAILED and source.error is not None:
            self._event(
                "operations_source_failed",
                "failed",
                f"{label} unavailable ({source.error.category}) after {source.attempts} attempt(s)",
                details={"tool": source.tool_name.value, "error_category": source.error.category},
            )
        elif source.status is SourceStatus.DEGRADED and source.evidence is not None:
            self._event(
                "operations_source_degraded",
                "degraded",
                f"{label} evidence is {source.evidence.validity_state.value}",
                (source.evidence.evidence_id,),
                {
                    "tool": source.tool_name.value,
                    "warning_codes": [w.code for w in source.warnings],
                },
            )

    # --- failure path ----------------------------------------------------------------------

    def _all_warnings(self, sources: _Sources) -> list[EvidenceWarning]:
        warnings = [w for s in sources.all() for w in s.warnings]
        warnings.extend(
            EvidenceWarning(
                warning_id=f"warning-{self._request.request_id}-{s.tool_name.value}-unavailable",
                claim_reference=f"operations:{s.tool_name.value}",
                code="SOURCE_UNAVAILABLE",
                message=(
                    f"{_SOURCE_LABELS[s.tool_name]} unavailable "
                    f"({s.error.category if s.error else 'unknown'}); analysis not performed"
                ),
                source_reference=None,
            )
            for s in sources.all()
            if s.status is SourceStatus.FAILED
        )
        return warnings

    def _failed(
        self, reason: str, sources: _Sources, missing_data: tuple[str, ...]
    ) -> OperationsOutcome:
        all_sources = sources.all()
        evidence = tuple(s.evidence for s in all_sources if s.evidence is not None)
        warnings = tuple(self._all_warnings(sources))
        errors = tuple(s.error for s in all_sources if s.error is not None)
        failed = [s for s in all_sources if s.status is SourceStatus.FAILED]
        unknowns = tuple(
            Unknown(
                claim_reference=f"operations:{s.tool_name.value}",
                description=f"{_SOURCE_LABELS[s.tool_name]} could not be established",
                required_evidence=(s.tool_name.value,),
            )
            for s in failed
        ) or (
            Unknown(
                claim_reference="operations:affected_flights",
                description="affected flights could not be validated against the schedule",
                required_evidence=("flight_schedule",),
            ),
        )
        self._event("operations_escalation", "failed", reason, details={"status": "failed"})
        payload: dict[str, object] = {
            "agent_name": "Operations Agent",
            "reason": reason,
            "missing_data": list(missing_data),
            "missing_analysis": [f"{_SOURCE_LABELS[s.tool_name]} not performed" for s in failed],
            "errors": [error.model_dump(mode="json") for error in errors],
            "warnings": [f"{w.code}: {w.message}" for w in warnings],
            "advisory_only": True,
            "human_approval_required": True,
        }
        return OperationsOutcome(
            result=AgentResult(
                schema_version="1.0",
                agent_role=AgentRole.OPERATIONS,
                status=AgentResultStatus.FAILED,
                summary=f"Operations assessment failed: {reason}.",
                confidence=0.0,
                assumptions=(),
                evidence_references=tuple(e.evidence_id for e in evidence),
                role_payload=payload,
            ),
            assessment=None,
            evidence=evidence,
            warnings=warnings,
            conflicts=(),
            unknowns=unknowns,
            errors=errors,
            audit_events=tuple(self._events),
            confidence=assess_confidence(0.0, (), unknowns),
        )

    # --- main path -------------------------------------------------------------------------

    def _assess(
        self,
        sources: _Sources,
        schedule_data: FlightScheduleData,
        validation: ScheduleValidation,
    ) -> OperationsOutcome:
        request = self._request
        flights = validation.flights
        schedule_evidence = sources.schedule.evidence
        assert schedule_evidence is not None  # schedule data implies evidence

        package_data = sources.packages.data
        package_gaps: tuple[str, ...] = ()
        if package_data is not None:
            covered = {group.flight_number for group in package_data.groups}
            package_gaps = tuple(
                f"package manifest for flight {f.flight_number}"
                for f in flights
                if f.flight_number not in covered
            )
            if package_gaps:
                package_data = None

        replacement: tuple[ReplacementFlight, ...] | None = None
        if sources.alternates.data is not None:
            manifest = sources.packages.data
            cutoffs = [g.cutoff_at for g in manifest.groups] if manifest is not None else []
            replacement = find_replacement_flights(
                flights,
                sources.alternates.data,
                request.reroute_policy,
                request.evaluated_at,
                max(cutoffs) if cutoffs else None,
            )

        evaluations = tuple(
            evaluate_candidate(
                candidate,
                EvaluationContext(
                    request=request,
                    flights=flights,
                    all_flights=schedule_data.flights,
                    fleet=sources.fleet.data if sources.fleet is not None else None,
                    packages=package_data,
                    replacement_flights=replacement,
                ),
                self._settings,
            )
            for candidate in request.candidates
        )
        assessments = tuple(e.assessment for e in evaluations)
        route_conflicts = tuple(c for e in evaluations for c in e.conflicts)
        evidence_conflicts = self._evidence_conflicts(
            route_conflicts, schedule_evidence.evidence_id
        )

        all_sources = sources.all()
        evidence = tuple(s.evidence for s in all_sources if s.evidence is not None)
        warnings = self._all_warnings(sources)
        errors = tuple(s.error for s in all_sources if s.error is not None)
        failed = [s for s in all_sources if s.status is SourceStatus.FAILED]

        missing_data = (
            *(f"flight {n} not found in schedule" for n in validation.missing_flight_numbers),
            *package_gaps,
            *(m for a in assessments for m in a.missing_inputs),
        )
        missing_analysis = (
            *(f"{_SOURCE_LABELS[s.tool_name]} not performed" for s in failed),
            *(f"{gap} not available" for gap in package_gaps),
        )
        unknowns = (
            *(
                Unknown(
                    claim_reference=f"operations:{s.tool_name.value}",
                    description=f"{_SOURCE_LABELS[s.tool_name]} could not be established",
                    required_evidence=(s.tool_name.value,),
                )
                for s in failed
            ),
            *(
                Unknown(
                    claim_reference=f"operations:option:{a.option_id}",
                    description=f"missing input for {a.option_id}: {missing}",
                    required_evidence=(missing,),
                )
                for a in assessments
                for missing in a.missing_inputs
            ),
            *(
                Unknown(
                    claim_reference="operations:package_load",
                    description=f"{gap} is missing",
                    required_evidence=("package_load",),
                )
                for gap in package_gaps
            ),
        )

        confidence_value, reasons = self._confidence(
            sources, evaluations, validation, package_gaps, bool(evidence_conflicts)
        )
        confidence = assess_confidence(confidence_value, evidence_conflicts, unknowns)

        viable_ids = tuple(a.option_id for a in assessments if a.viability in _VIABLE)
        trade_offs, needs_selection = self._trade_offs(assessments)
        escalate = (
            confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED or not viable_ids
        )
        if escalate:
            status = AgentResultStatus.ESCALATION_REQUIRED
        elif reasons or missing_data:
            status = AgentResultStatus.PARTIAL
        else:
            status = AgentResultStatus.COMPLETE

        facts = OperationsFacts(
            case_id=request.case.case_id,
            aircraft_id=request.case.aircraft_id,
            options=tuple(self._option_facts(e) for e in evaluations),
            missing_analysis=missing_analysis,
            warning_codes=tuple(sorted({w.code for w in warnings})),
            conflict_codes=tuple(sorted({c.code.value for c in route_conflicts})),
            confidence=confidence_value,
            disposition=confidence.disposition,
            requires_human_selection=needs_selection,
            viable_option_ids=viable_ids,
        )
        judgment = self._reasoner.reason(facts)
        violations = validate_judgment(judgment, facts)
        reasoner_mode = self._reasoner.mode
        if violations:
            judgment = DeterministicReasoner().reason(facts)
            joined = ", ".join(violations)
            reasoner_mode = f"{self._reasoner.mode}:rejected({joined})->{DETERMINISTIC_MODE}"
            warnings.append(
                EvidenceWarning(
                    warning_id=f"warning-{request.request_id}-reasoning",
                    claim_reference="operations:reasoning",
                    code="REASONING_REJECTED",
                    message=f"reasoning output rejected by guardrail: {joined}",
                    source_reference=self._reasoner.mode,
                )
            )
            self._event(
                "operations_fallback",
                "reasoning_rejected",
                f"guardrail rejected reasoning ({joined}); deterministic narrative used",
            )

        for conflict in evidence_conflicts:
            self._event(
                "operations_conflict_detected",
                "conflict",
                conflict.description,
                conflict.evidence_references,
                {"conflict_id": conflict.conflict_id},
            )
        if escalate:
            self._event(
                "operations_escalation",
                "escalation_required",
                "conflict, low confidence, or no viable option requires human adjudication",
                details={"confidence": confidence_value, "viable_options": list(viable_ids)},
            )

        if escalate:
            decision = RecommendationDecision.ESCALATE
        elif len(viable_ids) == 1:
            kind = next(a.kind for a in assessments if a.option_id == viable_ids[0])
            decision = RecommendationDecision(kind.value)
        else:
            decision = RecommendationDecision.DEFER_TO_CONTROLLER

        levels = [a.impact_level for a in assessments if a.impact_level is not None]
        assumptions = self._assumptions(evaluations)
        warning_lines = tuple(f"{w.code}: {w.message}" for w in warnings) + tuple(
            f"ASSIGNMENT_MISMATCH: flight {n} is not assigned to the AOG aircraft"
            for n in validation.assignment_mismatches
        )
        assessment = OperationsAssessment(
            operational_impact_level=max(levels, key=IMPACT_ORDER.index) if levels else None,
            summary=judgment.summary,
            affected_routes=tuple(sorted({f.route for f in flights})),
            package_impact=self._package_summary(package_data, flights, package_gaps),
            available_flights=replacement or (),
            recovery_options=assessments,
            risk_factors=self._risk_factors(assessments, route_conflicts, sources),
            assumptions=assumptions,
            missing_data=missing_data,
            missing_analysis=missing_analysis,
            conflicts=route_conflicts,
            warnings=warning_lines,
            trade_offs=trade_offs,
            requires_human_selection=needs_selection,
            recommendation=OperationsRecommendation(
                decision=decision,
                viable_option_ids=viable_ids,
                confidence=confidence_value,
                reasoning=judgment.reasoning,
                next_steps=judgment.next_steps,
            ),
            confidence=confidence_value,
            confidence_disposition=confidence.disposition,
            confidence_reasons=tuple(reason for reason, _ in reasons),
            reasoner_mode=reasoner_mode,
        )

        eta_references = tuple(
            dict.fromkeys(ref for c in request.candidates for ref in c.eta_evidence_references)
        )
        result = AgentResult(
            schema_version="1.0",
            agent_role=AgentRole.OPERATIONS,
            status=status,
            summary=judgment.summary,
            confidence=confidence_value,
            assumptions=tuple(
                Assumption(
                    assumption_id=f"assumption-{request.request_id}-{index}",
                    claim_reference="operations:assessment",
                    statement=statement,
                    evidence_references=(schedule_evidence.evidence_id,),
                )
                for index, statement in enumerate(assumptions, start=1)
            ),
            evidence_references=tuple(e.evidence_id for e in evidence) + eta_references,
            role_payload=assessment.model_dump(mode="json"),
        )
        self._event(
            "operations_assessment_completed",
            status.value,
            judgment.summary,
            result.evidence_references,
            {
                "confidence": confidence_value,
                "disposition": confidence.disposition.value,
                "viability": {a.option_id: a.viability.value for a in assessments},
            },
        )
        return OperationsOutcome(
            result=result,
            assessment=assessment,
            evidence=evidence,
            warnings=tuple(warnings),
            conflicts=evidence_conflicts,
            unknowns=unknowns,
            errors=errors,
            audit_events=tuple(self._events),
            confidence=confidence,
        )

    # --- helpers ---------------------------------------------------------------------------

    def _evidence_conflicts(
        self, route_conflicts: tuple[RouteConflict, ...], schedule_evidence_id: str
    ) -> tuple[EvidenceConflict, ...]:
        by_option = {c.option_id: c for c in self._request.candidates}
        return tuple(
            EvidenceConflict(
                conflict_id=conflict.conflict_id,
                claim_reference=f"operations:readiness:{conflict.option_id}",
                evidence_references=(
                    *by_option[conflict.option_id].eta_evidence_references,
                    schedule_evidence_id,
                ),
                description=conflict.description,
            )
            for conflict in route_conflicts
            if conflict.code is ConflictCode.TIME_ESTIMATE_CONFLICT
        )

    def _confidence(
        self,
        sources: _Sources,
        evaluations: tuple[CandidateEvaluation, ...],
        validation: ScheduleValidation,
        package_gaps: tuple[str, ...],
        has_conflict: bool,
    ) -> tuple[float, list[tuple[str, float]]]:
        s = self._settings
        reasons: list[tuple[str, float]] = []
        for source in sources.all():
            label = _SOURCE_LABELS[source.tool_name]
            if source.status is SourceStatus.DEGRADED and source.evidence is not None:
                validity = source.evidence.validity_state
                penalty = (
                    s.penalty_stale_evidence
                    if validity is EvidenceValidity.STALE
                    else s.penalty_partial_evidence
                )
                reasons.append((f"{label} evidence is {validity.value}", penalty))
            elif source.status is SourceStatus.FAILED:
                critical = source.tool_name in _CRITICAL_SOURCES
                reasons.append(
                    (
                        f"{label} unavailable",
                        s.penalty_critical_source_unavailable
                        if critical
                        else s.penalty_optional_source_unavailable,
                    )
                )
        if package_gaps:
            reasons.append(
                ("package manifest missing for an affected flight", s.penalty_partial_evidence)
            )
        if validation.missing_flight_numbers or validation.assignment_mismatches:
            reasons.append(
                ("schedule data is incomplete or inconsistent", s.penalty_partial_evidence)
            )
        if any(e.used_estimated_eta for e in evaluations):
            reasons.append(("readiness ETA is an estimate, not confirmed", s.penalty_estimated_eta))
        if has_conflict:
            reasons.append(
                (
                    "Maintenance/Materials ETA conflicts with operational feasibility",
                    s.penalty_conflict,
                )
            )
        if any(e.assessment.viability is Viability.UNDETERMINED for e in evaluations):
            reasons.append(
                ("a candidate could not be determined", s.penalty_undetermined_candidate)
            )

        value = max(0.0, s.base_confidence - sum(penalty for _, penalty in reasons))
        if reasons:
            value = min(value, s.provisional_confidence_cap)
        return round(value, 2), reasons

    def _trade_offs(
        self, assessments: tuple[RecoveryOptionAssessment, ...]
    ) -> tuple[tuple[str, ...], bool]:
        viable = [a for a in assessments if a.viability in _VIABLE and a.impact_level is not None]
        if len(viable) < 2:
            return (), False
        lines: list[str] = []
        for a in viable:
            unprotected = (
                f"{a.package.unprotected_count} packages unprotected"
                if a.package.unprotected_count is not None
                else "package impact not assessed"
            )
            cost = f", operational cost ${a.cost.total_usd}" if a.cost is not None else ""
            reroute = (
                f", {a.package.own_flight_count} rerouted on own-network flights and "
                f"{a.package.partner_flight_count} on partner flights"
                if (a.package.own_flight_count or 0) + (a.package.partner_flight_count or 0) > 0
                else ""
            )
            lines.append(
                f"{a.option_id} ({a.kind.value}): {a.schedule_delay_minutes} minute delay, "
                f"{unprotected}{reroute}{cost}"
            )
        indices = [IMPACT_ORDER.index(a.impact_level) for a in viable if a.impact_level]
        counts = [
            a.package.unprotected_count for a in viable if a.package.unprotected_count is not None
        ]
        gap = self._settings.material_unprotected_packages_gap
        material = max(indices) - min(indices) >= 1 or (
            len(counts) >= 2 and max(counts) - min(counts) >= gap
        )
        return tuple(lines), material

    def _option_facts(self, evaluation: CandidateEvaluation) -> OptionFacts:
        a = evaluation.assessment
        return OptionFacts(
            option_id=a.option_id,
            kind=a.kind,
            viability=a.viability,
            impact_level=a.impact_level,
            delay_minutes=a.schedule_delay_minutes,
            unprotected_count=a.package.unprotected_count,
            rerouted_own_count=a.package.own_flight_count,
            rerouted_partner_count=a.package.partner_flight_count,
            total_cost_usd=a.cost.total_usd if a.cost else None,
            cost_complete=a.cost.complete if a.cost else False,
            conflict_codes=tuple(c.code.value for c in evaluation.conflicts),
            missing_inputs=a.missing_inputs,
        )

    def _assumptions(self, evaluations: tuple[CandidateEvaluation, ...]) -> tuple[str, ...]:
        statements = [
            "Each affected flight is assessed independently; downstream aircraft rotation "
            "chaining is not modeled.",
            "Operational cost uses mock rates and covers delay, swap, rerouting, and "
            "unprotected-package components only; repair labor and part cost are added by "
            "the Controller.",
            "Rerouting uses direct flights on the same origin and destination only; "
            "connections and interlining are not modeled, and no flight is booked by this agent.",
        ]
        if any(e.assessment.substitute_aircraft_id for e in evaluations):
            statements.append(
                "A single substitute aircraft serves all affected flights; sequencing between "
                "them is not modeled."
            )
        statements.extend(
            f"Readiness ETA for {c.option_id} is an estimate, not confirmed."
            for c in self._request.candidates
            if c.eta_basis is EtaBasis.ESTIMATED
        )
        return tuple(statements)

    def _package_summary(
        self,
        package_data: PackageLoadData | None,
        flights: tuple[FlightRecord, ...],
        package_gaps: tuple[str, ...],
    ) -> PackageImpactSummary:
        if package_data is None:
            reason = (
                "package manifest missing for an affected flight"
                if package_gaps
                else "package load data unavailable"
            )
            return PackageImpactSummary(
                assessed=False,
                affected_package_count=None,
                time_critical_package_count=None,
                summary=f"Package impact not assessed: {reason}.",
            )
        affected = {f.flight_number for f in flights}
        groups = [g for g in package_data.groups if g.flight_number in affected]
        total = sum(g.count for g in groups)
        critical = sum(g.count for g in groups if g.time_critical)
        return PackageImpactSummary(
            assessed=True,
            affected_package_count=total,
            time_critical_package_count=critical,
            summary=f"{total} packages affected, {critical} time-critical, across "
            f"{len(affected)} flight(s).",
        )

    def _risk_factors(
        self,
        assessments: tuple[RecoveryOptionAssessment, ...],
        conflicts: tuple[RouteConflict, ...],
        sources: _Sources,
    ) -> tuple[str, ...]:
        risks: list[str] = []
        for a in assessments:
            if a.impact_level is not None and a.impact_level in {
                ImpactLevel.HIGH,
                ImpactLevel.CRITICAL,
            }:
                risks.append(
                    f"{a.option_id}: {a.impact_level.value} impact "
                    f"({a.schedule_delay_minutes} minute delay)"
                )
            if a.package.unprotected_count:
                risks.append(f"{a.option_id}: {a.package.unprotected_count} packages unprotected")
            if a.package.partner_flight_count:
                risks.append(
                    f"{a.option_id}: {a.package.partner_flight_count} packages depend on partner "
                    "flights that must be booked by humans before their deadlines"
                )
            if not a.package.reroute_assessed and a.package.assessed:
                risks.append(
                    f"{a.option_id}: alternate flights could not be searched, so rerouting "
                    "capacity is unknown"
                )
        risks.extend(c.description for c in conflicts)
        if sources.network.data is not None:
            risks.extend(
                f"Active {d.kind.value} disruption at {d.station} (severity {d.severity.value})"
                for d in sources.network.data.disruptions
            )
        return tuple(dict.fromkeys(risks))
