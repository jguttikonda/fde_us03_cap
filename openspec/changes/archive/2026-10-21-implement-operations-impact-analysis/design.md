## Context

See [proposal.md](./proposal.md) for motivation and scope, and [specs/operations-impact-analysis/spec.md](./specs/operations-impact-analysis/spec.md) for the behavior contract. The shared foundation (archived `shared-aog-recovery-foundation`) provides strict Pydantic contracts (`AogCase`, `Evidence`, `AgentResult`, `ToolRequest`/`ToolResult`, `AuditEvent`), a read-only allowlisted `LocalReadOnlyAdapter`, confidence assessment, structured logging, and `pydantic-settings` configuration. The Operations proposal (`docs/agent-proposals/operations-agent-proposal.md`) defines the prompt stages, tool names, and output format; the ARD (`ARD-OPS-001..009`) is normative. Operations is called per candidate by the Controller after Maintenance and Materials & Logistics supply an ETA (ARD-CTL-018); it never ranks or approves (ARD-SYS-005, ARD-PRN-001).

## Goals / Non-Goals

**Goals:**

- Implement the Operations Agent as a deterministic-first pipeline with a bounded, replaceable reasoning stage, returning the shared `AgentResult` envelope with a typed Operations payload.
- Keep rules, arithmetic, thresholds, redistribution, cost, confidence, and conflict detection deterministic, configurable, and independently testable.
- Make missing, stale, partial, conflicting, malformed, and unavailable evidence visible and confidence-reducing, with no success-shaped fallback.
- Provide a Google ADK agent definition and prompt stages without any live model or network use in tests.

**Non-Goals:**

- Controller orchestration, routing, compliance gate, scoring, ranking, decision brief, A2A, Maintenance or Materials & Logistics analysis.
- Live integrations, MCP server exposure, asynchronous I/O, write operations, a database, API, or UI.
- Modeling downstream aircraft rotation chaining or slot capacity (assumptions are recorded; slot data is not in the mock scope).

## Decisions

### Package layout and ownership

```text
src/aog_recovery/operations/
  models.py      # request, source-data, and result/payload Pydantic models
  settings.py    # OperationsSettings (AOG_OPS_*): thresholds, buffers, mock rates, confidence policy
  rules.py       # pure deterministic functions named after the proposal tools
  gateway.py     # typed read-only tool gateway: allowlisted call, bounded retry, untrusted-data validation, evidence
  reasoning.py   # OperationsFacts/Judgment, reasoner protocol, deterministic offline reasoner, guardrail
  prompts.py     # Prompt A / B / C text (single source for the ADK agent)
  agent.py       # OperationsAgent: validates, gathers, evaluates, reasons, assembles AgentResult, audits
  adk_agent.py   # google.adk LlmAgent definition wrapping the agent as a read-only tool
  synthetic.py   # deterministic synthetic scenarios and local adapters for tests and demonstration
  demo.py        # runnable synthetic demonstration (python -m aog_recovery.operations.demo)
```

Operations imports shared contracts and adapters; shared modules do not import Operations (ARD-NFR-004, ARD-SYS-003). The only shared-module edit is additive: new `ToolName` members and allowlist entries.

### Contracts and request boundary

All models extend `ContractModel` (strict, `extra="forbid"`, versioned). `OperationsRequest` carries `request_id`, `AogCase`, affected flight numbers, `evaluated_at`, and one or more `CandidateOption`. A repair or delay candidate carries `readiness_eta`, an `EtaBasis` (confirmed or estimated), and at least one upstream `eta_evidence_references`; an ETA without basis or provenance is rejected at the boundary, and an absent ETA is allowed but becomes missing data (ARD-GOV-005, ARD-DAT-004/005). `evaluated_at` is an input, never the wall clock, so results are reproducible (ARD-NFR-003). Source-data models (flights, aircraft, package groups, capacity targets, disruptions) are strict so that tool output is validated as untrusted input (ARD-SEC-004).

### Deterministic rules named after the proposal tools

`rules.py` exposes `validate_flight_schedule`, `detect_route_conflicts`, `check_fleet_availability`, `apply_disruption_thresholds`, and `check_load_redistribution`; the payload assembly is `format_impact_payload`. They are pure functions of validated models and `OperationsSettings`, so a later MCP wrapper can expose them unchanged (ARD-TEC-006 deferred, ARD-OPS-002).

- **Timing.** For repair and delay candidates the operationally feasible departure per flight is `max(scheduled_departure, readiness_eta + turnaround_buffer, crew_available_from)`. For swap it is `max(scheduled_departure, substitute ready time, crew_available_from)`, where substitute ready time is `available_from + positioning + turnaround`. Delay minutes are the difference from the scheduled departure, never negative.
- **Conflicts.** `crew_coverage` is `available`, `delayed` (with `crew_available_from`), or `gap`. A gap is a conflict that makes every candidate not viable. A substitute whose own assignments overlap the affected window is rejected with a conflict naming the aircraft and flights, and the next aircraft in deterministic order is tried. A `time_estimate_conflict` is raised when crew availability exceeds the Maintenance/M&L ETA plus turnaround by more than `time_conflict_threshold_minutes`; it preserves both estimates and evidence references and is the only operations condition that forces adjudication through the shared conflict model (ARD-GOV-004, ARD-OPS-008).
- **Substitution.** Candidates must be serviceable, of the required type, within the positioning limit, and ready within the swap window, ordered by ready time, then larger capacity, then aircraft identifier (ARD-OPS-002, ARD-NFR-003).
- **Classification.** Delay thresholds (`medium`, `high`, `critical` minutes) map to levels; one uplift step (never above critical) applies when a flight is service-critical or time-critical packages remain unprotected; the applied rule name is recorded (ARD-OPS-003, ARD-NFR-006).
- **Package redistribution.** Groups are sorted by time-critical, then service-level rank, then cut-off, then identifier. Each group is allocated first to its primary path (original aircraft held to the new departure for repair and delay, or the substitute's capacity for swap) when the flight's feasible departure meets the group's cut-off, then to usable replacement flights (see Flight sourcing below) that fly the group's route, accept its service level, and depart by the cut-off, decrementing each flight's spare capacity. Anything left is unprotected and counted by service level (ARD-OPS-009). This reproduces proposal test case 6 exactly when no alternate flights exist: 900 allocated (700 priority, 200 standard), 300 unprotected.
- **Flight sourcing (own network vs partner).** `find_replacement_flights` filters the mock Flight Capacity source to direct flights on the affected routes and marks each `bookable` or restricted with a stated reason: partner not permitted by policy, partner cost above the cap, already departed, booking deadline passed, no spare capacity, or departure after the latest package cut-off. The request carries a `ReroutePolicy` (partners allowed, own network first, partner cost cap) so the human sets the boundary and the agent only applies it. Usable flights are ordered own-network first (when preferred), then by departure, cost, and flight number, so allocation is deterministic. The agent proposes; it never books, and any use of partner flights is flagged for human booking in risk factors and next steps. Connections and interlining are not modeled. Spare aircraft dispatched as an extra section are represented as own-network flights.
- **Cost.** Integer USD from configured mock rates: delay minutes times rate per affected flight, a flat swap cost, rerouting priced per package by the flight's cost, and unprotected packages priced by service level. This is the operational part of ARD-CTL-019; repair labor and part cost stay with Maintenance and Materials & Logistics. When package impact or the flight search is not assessed the cost is flagged incomplete rather than treated as zero.

### Tool gateway, untrusted data, and bounded retry

`OperationsToolGateway` wraps `ReadOnlyAdapter` instances keyed by `ToolName`. For each source it issues a `ToolRequest` with `access_mode="read"` as the Operations role, retries only retryable failures up to `max_retries` using the same request identifier (ARD-RES-005, ARD-NFR-002), validates `ToolResult.data` into the typed source model (failure category `malformed_response` on invalid or unknown-field data), converts the result into `Evidence` with a validity state (partial warnings map to stale, partial, or conflicting; age beyond `schedule_max_age_minutes` makes it stale), and returns a `SourceOutcome` preserving the original structured error. The flight schedule is the only essential source; fleet availability matters when a swap candidate exists; package load, alternate flights, and network status degrade the result when absent (an unavailable flight search marks unprotected counts as upper bounds and cost as incomplete). A missing adapter is a visible `tool_not_configured` failure. Wall-clock timeout enforcement belongs to adapter implementations and the existing configured `tool_timeout_seconds`; the local adapter simulates timeout as a retryable structured failure.

### Confidence and result status

Confidence is a deterministic policy: base 0.90 reduced by configured penalties for stale evidence, partial evidence, unavailable sources, unconfirmed ETA, conflict, and undetermined candidates. Any degradation caps confidence at 0.69 so incomplete or time-sensitive data is always provisional (ARD-OPS-006), and the shared `assess_confidence` assigns the disposition and escalates on conflict or confidence below 0.50 (ARD-GOV-001..004). Status is `failed` when the essential schedule is unavailable, `escalation_required` on escalation or when no candidate is viable, `partial` when degraded, otherwise `complete`. The payload always carries `advisory_only` and `human_approval_required` as `Literal[True]` (ARD-GOV-008).

### Bounded reasoning, ADK, and guardrail

`OperationsFacts` is the only input to reasoning: deterministic metrics and codes, with no tool free text, so injected text cannot reach a model (ARD-SEC-005). `OperationsReasoner` is a typed protocol returning `OperationsJudgment` (summary, reasoning, next steps). `DeterministicReasoner` is the offline implementation used in tests and the demonstration and is labelled as such in the result. A live reasoner would run the staged prompts in `prompts.py` through the ADK `LlmAgent`; `adk_agent.py` builds that agent (instruction composed from Prompts A/B/C plus guardrails, one read-only tool that calls the deterministic agent), and no domain code calls a model provider directly (ARD-TEC-002, ARD-TEC-005). The guardrail rejects empty output, claims of safety or airworthiness, statements of approval or execution, and stated unprotected counts or dollar amounts that do not match the facts; a rejection adds a visible warning and substitutes the deterministic narrative (ARD-PRN-003/004, ARD-SEC-008, ARD-RES-006).

### Recommendation semantics without ranking

The payload recommendation reports operational viability only. With one viable candidate it names that kind; with none or on conflict or low confidence it is `escalate`; with several viable candidates it is `defer_to_controller` and the payload lists the viable options and trade-offs, requiring human selection when impact or unprotected packages differ materially (`material_unprotected_packages_gap`, one or more impact-level steps) (ARD-OPS-007, ARD-SYS-005, ARD-CTL-015). `defer_to_controller` extends the proposal's decision list; the ARD does not fix that list and the extension protects Controller ownership of ranking.

### Settings and audit

`OperationsSettings` (`AOG_OPS_` prefix, validated ordering of thresholds) externalizes thresholds, buffers, mock rates, retry bound, staleness, and confidence penalties with documented defaults (ARD-NFR-001/006). The agent emits redacted, correlated `AuditEvent`s inside a `correlation_scope` for request validation, each source degradation or failure, conflict, escalation, and completion, and returns them for inspection; rationale is concise and excludes private reasoning (ARD-OBS-001..004, ARD-SEC-007/009).

## ARD Requirement Mapping

| ARD requirements | Design response |
|---|---|
| ARD-OPS-001/002/004 | Typed per-candidate request, source models, deterministic schedule, fleet, and conflict rules over every supplied candidate |
| ARD-OPS-003 | `apply_disruption_thresholds` with configured boundaries and recorded rule |
| ARD-OPS-005 | `OperationsAssessment` payload and shared `AgentResult` envelope |
| ARD-OPS-006 | Stale/partial labelling, provisional confidence cap, missing-data lists |
| ARD-OPS-007/008 | Trade-off statements and human selection flag; conflict records naming resources and the more viable option |
| ARD-OPS-009, ARD-CTL-019 | `check_load_redistribution` with unprotected remainder; cost components |
| ARD-GOV-001..005/008 | Shared confidence assessment, conflict escalation, missing-data list, advisory literals |
| ARD-RES-002..007 | Structured failures, bounded same-id retry, named missing analysis, visible fallback labels, case-scoped state |
| ARD-SEC-001..009 | Allowlisted read-only gateway, strict untrusted-data models, facts-only reasoning, redaction, no safety claim |
| ARD-OBS-001..004, ARD-NFR-001..003/006/007 | Correlated events, concise rationale, externalized settings, determinism, declared dependencies |
| ARD-TEC-002/005/008/009, ARD-PRN-003/004 | ADK agent definition, no direct model calls, pytest/Ruff/mypy, deterministic-first design |
| ARD-TST-001..003/005/007/009 | Requirement-mapped tests with deterministic synthetic fixtures |

ARD-TEC-006 and ARD-TEC-007 are deferred as stated in the proposal; no ARD deviation is proposed.

## Risks / Trade-offs

- **[Offline reasoner mistaken for LLM behavior]** -> Label `reasoner_mode` in the result and demonstration, document it in the verification evidence, and require a separate approved change for live model evaluation.
- **[Mock cost rates and thresholds treated as real business values]** -> Mark them mock and externalized; business owners validate them before any use beyond the capstone.
- **[Simplified rotation model]** -> Record the no-downstream-chaining and single-substitute assumptions in every result; extend when schedule chaining data exists.
- **[Additive shared edits ripple]** -> Edits are enum members and allowlist entries only; the full foundation suite must still pass.
- **[Confidence cap hides granularity]** -> The payload retains each penalty reason so a reviewer can see why confidence is provisional.
- **[`defer_to_controller` extension]** -> Documented and additive; revisit when the Controller change defines handoff semantics.

## Migration Plan

Additive only: new package, tests, and settings. Rollback is reverting the change; the two shared-module edits are enum/allowlist additions with no data migration. Live adapters, MCP exposure, and model configuration require their own approved changes.

## Open Questions

None blocking. Mock thresholds, rates, package priority rules, and freshness limits should be confirmed with the Operations owner before use beyond the capstone.
