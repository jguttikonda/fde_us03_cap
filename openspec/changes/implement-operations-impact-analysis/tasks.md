## 1. Shared Tool Identifiers and Operations Settings

- [x] 1.1 Add `flight_schedule`, `fleet_availability`, `package_load`, and `alternate_flights` tool identifiers and allowlist them for the Operations and Controller roles only; test Operations read success and Maintenance/M&L structured denial, and that the existing foundation suite still passes (ARD-SEC-001..003, ARD-SYS-007, ARD-TST-007, Spec: Operations read-only tool identifiers and allowlist).
- [x] 1.2 Implement `OperationsSettings` (`AOG_OPS_` prefix) with documented defaults for delay thresholds, buffers, conflict threshold, staleness, retry bound, mock cost rates, materiality, and confidence penalties; test defaults, ordering validation, env override, and invalid values; add variables to `.env.example` (ARD-NFR-001/006/007, ARD-TEC-004, Spec: Configured disruption impact classification).

## 2. Operations Contracts

- [x] 2.1 Implement strict versioned request, candidate, and source-data models (flights, aircraft, package groups, alternate flights, disruptions); test valid input, missing ETA basis or provenance, duplicate option ids, naive timestamps, unknown fields, and unsupported schema version (ARD-OPS-001, ARD-DAT-001/009/010, ARD-SEC-004, Spec: Per-candidate operations request and evaluation).
- [x] 2.2 Implement result and payload models (impact level, viability, package outcome, cost breakdown, conflicts, recommendation, advisory and approval literals); test serialization shape, literal enforcement, and that the payload fits the shared `AgentResult` envelope (ARD-OPS-005, ARD-DAT-006/011/012, ARD-CTL-006, Spec: Structured operations result and confidence).

## 3. Deterministic Rules

- [x] 3.1 Implement `validate_flight_schedule` and `detect_route_conflicts` (crew gap, double-booked substitute, time-estimate conflict); test resource identification, boundary conflict threshold, and determinism (ARD-OPS-002/008, ARD-GOV-004, ARD-NFR-003, Spec: Deterministic schedule validation and conflict detection).
- [x] 3.2 Implement `check_fleet_availability` with deterministic ordering, positioning limit, and swap window; test selection, tie-breaks, and the no-aircraft case (ARD-OPS-001/002/004, Spec: Fleet substitution evaluation).
- [x] 3.3 Implement `apply_disruption_thresholds` with uplift and rule naming; test every boundary and uplift case (ARD-OPS-003, ARD-NFR-006, Spec: Configured disruption impact classification).
- [x] 3.4 Implement `check_load_redistribution` and cost computation; test proposal test case 6 exactly (900 allocated, 700 priority, 300 unprotected), cut-off misses, rerouting flights, priority order, empty capacity, and cost component sums (ARD-OPS-009, ARD-CTL-019, Spec: Package load redistribution; Spec: Operational cost component).

## 4. Tool Gateway

- [x] 4.1 Implement the read-only gateway with same-request-id bounded retry, typed validation of tool data, evidence and validity derivation, staleness by age, and structured failures including missing adapter; test success, timeout with retry bound and idempotent id, unavailable, malformed, unknown-field, stale, partial, and conflicting modes (ARD-RES-002/003/005/006, ARD-SEC-004, ARD-NFR-002, Spec: Timeout and unavailable-source handling; Spec: Untrusted tool data and read-only allowlisted access).
- [x] 4.2 Provide deterministic synthetic source data and local adapter builders for the normal, swap, package-capacity, conflicting-estimate, and degraded scenarios; verify they contain no real operational or secret data and are repeatable (ARD-SYS-008, ARD-TST-009, Spec: Untrusted tool data and read-only allowlisted access).

## 5. Reasoning and ADK Boundary

- [x] 5.1 Implement facts-only reasoning input, the reasoner protocol, the deterministic offline reasoner, and the output guardrail; test acceptance, empty output, airworthiness claim, approval or execution claim, and number-mismatch rejection with a visible warning (ARD-PRN-003/004, ARD-SEC-008, ARD-GOV-008, ARD-RES-006, Spec: Bounded reasoning with deterministic guardrails).
- [x] 5.2 Implement Prompts A, B, C and the Google ADK `LlmAgent` definition with one read-only tool; test construction, instruction content, tool allowlist, and that no model or network call occurs (ARD-TEC-002/005, ARD-TST-009, Spec: Bounded reasoning with deterministic guardrails).

## 6. Operations Agent

- [x] 6.1 Implement `OperationsAgent.assess` and `assess_payload`: boundary validation, source gathering, per-candidate evaluation, trade-off and material-difference detection, evidence/assumption/unknown/conflict assembly, confidence policy and status, recommendation semantics without ranking, and `AgentResult` assembly; test normal, partial, stale, missing ETA, conflicting estimates, low confidence, schedule failure, and no-viable-candidate outcomes (ARD-OPS-001..009, ARD-GOV-001..005, ARD-RES-002..004, Spec: Per-candidate operations request and evaluation; Spec: Conflicting time estimates and material customer trade-offs; Spec: Structured operations result and confidence).
- [x] 6.2 Emit redacted, correlated audit events for validation, degradation, conflict, escalation, and completion, and verify case isolation across two cases; test required event fields and that one case's failure does not alter another (ARD-OBS-001..004, ARD-SEC-007/009, ARD-RES-007, Spec: Correlated audit events and case isolation).

## 7. Verification, Security, and Human Gate

- [x] 7.1 Add security tests for prompt-injection text in tool data, unauthorized tool role, malformed data, secret redaction in events, and read-only adapter behavior (ARD-SEC-001..007, ARD-TST-007).
- [x] 7.2 Add human-gate tests proving no confidence level, degraded mode, or test mode produces an approval, execution, or ranking, that approval literals hold, and that no write method exists on the agent or gateway (ARD-GOV-008, ARD-PRN-001/002, ARD-TST-005).
- [x] 7.3 Validate `AgentResult` against the shared validator with upstream ETA evidence ids and run Ruff, mypy, and the full pytest suite; fix all findings (ARD-TEC-008/009, ARD-RUB-004).

## 8. Evidence and Demonstration

- [x] 8.1 Provide a runnable synthetic demonstration printing the input scenario, per-candidate results, and the reasoning output for the normal, test case 6, conflicting-estimate, and timeout scenarios; verify it runs offline (ARD-TST-009, ARD-RUB-010/012).
- [x] 8.2 Write the verification evidence document mapping ARD IDs and spec scenarios to tests, recording actual test, lint, and type-check results, AI-assisted development notes, the modified-file inventory for peer review, and the limits of the offline reasoner; leave peer review, Go/No-Go, live model evaluation, and sponsor communication to people (ARD-TST-001, ARD-TST-008, ARD-TEC-019/020, ARD-RUB-005..011).

## 9. Flight Sourcing and Package Rerouting (own network and partners)

- [x] 9.1 Add `AlternateFlight`/`AlternateFlightData`, `ReplacementFlight`, and a request-level `ReroutePolicy` (partners allowed, own network first, partner cost cap); test strict validation, defaults, unknown fields, and arrival-after-departure (ARD-OPS-009, ARD-DAT-001/009, ARD-SEC-004, Spec: Own-network and partner flight sourcing for package rerouting).
- [x] 9.2 Implement `find_replacement_flights` marking each flight bookable or restricted with a reason (policy, cost cap, departed, deadline, capacity, cut-off) and deterministic own-first ordering; test every restriction and ordering (ARD-OPS-009, ARD-NFR-003).
- [x] 9.3 Extend `check_load_redistribution` to allocate by route, service level, cut-off, and capacity onto own and partner flights with per-allocation path, carrier, departure, and cost, and price rerouting in the cost breakdown; test own-before-partner, service-level restriction, unusable flights, different route, substitute-then-reroute, and cost sums (ARD-OPS-009, ARD-CTL-019).
- [x] 9.4 Fetch the alternate-flight source in the agent; expose `available_flights`, per-option reroute plans, partner-booking risk and next step; treat a flight-search outage as named missing analysis, upper-bound unprotected counts, incomplete cost, and reduced confidence; test own-first, own-only policy, cost cap, and outage (ARD-RES-002/004/006, ARD-GOV-005, Spec: Own-network and partner flight sourcing for package rerouting).
- [x] 9.5 Add `partner_reroute` and `own_network_only` synthetic scenarios and show the policy, flights found, and reroute plan in the demonstration and ADK web demo (ARD-TST-009).

## 10. Cross-Agent Readiness (Maintenance and Materials & Logistics handoff)

- [x] 10.1 Add the shared `ReadinessEstimate` contract (absolute ETA, basis, optional window, evidence references; window end and lead-time helpers) and `CandidateOption.with_readiness`; test windows, hours, invalid inputs, and Operations use (ARD-DAT-004/005, ARD-GOV-005).
- [x] 10.2 Replace the draft Operations output format in the agent proposal with the implemented payload and add a test that the documented keys equal the models (ARD-RUB-004, ARD-OSP-002).
