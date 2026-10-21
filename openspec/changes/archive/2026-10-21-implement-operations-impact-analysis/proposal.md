## Why

The shared foundation is archived, but no specialist agent exists yet. The Controller cannot weigh recovery speed against flight, customer, and package impact until the Operations Agent can assess each candidate recovery option and explain which flights, packages, and commitments it puts at risk. Operations depends only on the shared contracts, so it can be built now, in parallel with Maintenance and Materials & Logistics.

## What Changes

- Add an Operations Agent that evaluates each Controller-supplied candidate (repair with original part, repair with preferred or alternate part, aircraft swap, delay) for route, schedule, fleet, crew, customer, and package-load impact.
- Add deterministic operations rules: flight and schedule validation, route and assignment conflict detection, substitute-aircraft availability, configurable disruption thresholds mapped to low/medium/high/critical, package load redistribution (aircraft capacity by tail, service level, sort and cut-off windows, unprotected remainder), and mock operational cost in USD.
- Add typed, read-only, allowlisted operations tool gateways (flight schedule, fleet availability, package load, alternate flights, network disruption) over the existing adapter contract, with deterministic synthetic mock data, bounded idempotent retry, and structured timeout/unavailable/malformed handling. Tool names and JSON contracts follow the proposal's `validate_flight_schedule`, `detect_route_conflicts`, `check_fleet_availability`, `apply_disruption_thresholds`, `check_load_redistribution`, and `format_impact_payload`, plus `find_replacement_flights`; they stay in-process because no process boundary is crossed (MCP exposure is deferred, ARD-TEC-006).
- Add flight sourcing for package rerouting: search own-network and partner flights on each affected route (mock Flight Capacity API), apply a human-set reroute policy carried in the request (partner flights allowed or not, own network first, partner cost cap), honor booking deadlines, accepted service levels, sort cut-offs, and spare capacity, price the rerouting in USD, and return the flights found with whether each is usable and why not, plus a per-option reroute plan (which packages go on which own or partner flight). The agent proposes only; it never books a flight or moves a package.
- Add a bounded reasoning boundary (Prompt A grounding, Prompt B trade-off, Prompt C validation) behind a typed reasoner protocol, a Google ADK `LlmAgent` definition carrying those prompts, and a deterministic offline reasoner used for tests and demonstration. A guardrail rejects reasoning that changes computed values, claims airworthiness, or implies approval.
- Return the shared `AgentResult` envelope with an Operations role payload (ARD-OPS-005): affected routes, per-candidate recovery options with impact and cost, package impact, risk factors, assumptions, missing data, recommendation, confidence, reasoning, next steps, and conflicts. Surface a time-estimate conflict between the Maintenance/M&L ETA and operational feasibility as a conflict, a provisional or escalated result, and a human-adjudication requirement.
- Extend the shared tool identifiers and role allowlist additively with the operations read tools.
- Keep the agent advisory: it never ranks options, approves anything, reschedules flights, or moves packages.
- Not changed: Maintenance, Materials & Logistics, Controller orchestration, compliance gate, weighted ranking, decision-report rendering, live integrations, MCP server exposure, and the human approval workflow.

## Capabilities

### New Capabilities

- `operations-impact-analysis`: Per-candidate operational impact assessment, deterministic operations rules and package load redistribution, read-only operations tool gateways, bounded reasoning with guardrails, degraded/conflict handling, and the structured Operations result for Controller aggregation.

### Modified Capabilities

- `shared-foundation`: Additive requirement for operations read-only tool identifiers (flight schedule, fleet availability, package load, alternate flights) and their role allowlist; existing requirements are unchanged.

## Impact

- Adds `src/aog_recovery/operations/` (models, settings, rules, gateway, reasoning, prompts, agent, ADK definition, synthetic data), `tests/operations/`, a runnable synthetic demonstration, and a verification evidence document.
- Additive edits to `src/aog_recovery/contracts/tool.py` and `src/aog_recovery/adapters/local.py` (tool names and allowlist) and `.env.example` (operations policy variables).
- No new runtime dependencies: Python, Google ADK, Pydantic, `pydantic-settings`, pytest, Ruff, and mypy are already declared. No live system, database, broker, or write operation is introduced; the model boundary stays behind ADK and is not called in tests.

## ARD Traceability

### Addressed

- **ARD-OPS-001..009** — inputs, deterministic validation, impact classification, per-candidate alternatives, output contents, provisional handling of time-sensitive data, material customer trade-off display, route-conflict explanation, and package load redistribution.
- **ARD-PRN-001..008, ARD-SYS-003, ARD-SYS-007..009** — advisory-only boundary, deterministic guardrails with bounded reasoning, evidence before conclusion, no silent degradation, typed boundaries, domain isolation, and adapter abstraction with deterministic local data.
- **ARD-DAT-001..012, ARD-CTL-006, ARD-CTL-018, ARD-CTL-019** — versioned Pydantic request/result/evidence/tool contracts, shared result envelope, per-candidate evaluation using the supplied ETA, and the operations cost component of the single estimated cost.
- **ARD-GOV-001..005, ARD-GOV-008** — confidence thresholds, conflict deferral, missing-data lists instead of assumptions, and no bypass of human approval.
- **ARD-RES-002, ARD-RES-003, ARD-RES-004, ARD-RES-005, ARD-RES-006, ARD-RES-007** — timeout and failure handling with named missing analysis, structured failures, partial results stating supported conclusions, bounded idempotent retry, visible fallback, and case isolation.
- **ARD-SEC-001..005, ARD-SEC-006..009** — least-privilege allowlisted read-only tools, untrusted tool data validated and excluded from reasoning, prompt-injection resistance, redaction, no airworthiness claim, append-oriented audit.
- **ARD-OBS-001..004, ARD-NFR-001..003, ARD-NFR-006..007** — structured correlated events, concise rationale, configurable bounded timeouts/retries, determinism, externalized thresholds and rates.
- **ARD-TEC-001..005, ARD-TEC-008..009** — Python, ADK, Pydantic, typed settings, ADK-governed model boundary, pytest, Ruff and mypy.
- **ARD-TST-001..003, ARD-TST-005, ARD-TST-007, ARD-TST-009, ARD-RUB-001..004** — requirement-mapped contract, agent, human-gate, security, and deterministic tests.

### Deferred

- **ARD-TEC-006** — MCP is required only when a tool crosses a process or service boundary; the operations tools are in-process, so MCP exposure is deferred without weakening typed validation, allowlisting, timeouts, errors, or audit.
- **ARD-TEC-007** — asynchronous I/O is a SHOULD; the synchronous foundation adapter contract is retained and bounded by configured timeouts and retries.
- **ARD-SYS-001, ARD-SYS-002, ARD-SYS-004..006, ARD-CTL-001..005, ARD-CTL-007..017** — orchestration, routing, A2A, conflict detection across agents, compliance gate, scoring, and brief generation belong to later Controller changes; this agent returns evidence only.
- **ARD-TST-004, ARD-TST-006, ARD-TST-008** — scoring and full multi-agent end-to-end scenarios require the Controller; Operations-level scenarios that feed cases 2, 3 (Operations side), 5-conflict, and 6 are covered here.
- **ARD-TEC-017..019, ARD-RUB-005..012** — CI, security scanning, peer review, Go/No-Go, and live sponsor communication remain delivery activities; this change retains local test and demonstration evidence only.

### Out of Scope

- Live airline, schedule, fleet, crew, or package systems and any operational write operation (**ARD-SYS-008, ARD-SEC-002, ARD-GOV-008**).
- Standalone Risk, Recommendation, or Report agents (**ARD-SYS-002..005**, ADR-001).

No ARD deviation is requested.

## Rubric and Capability Coverage

| Rubric checkbox / proposal capability | Operations support | Retained evidence | Verification | Human responsibility |
|---|---|---|---|---|
| Phase 2: OpenSpec proposal, design, spec delta, task checklist; Pydantic models and tool contracts | New `operations-impact-analysis` spec; typed request, source-data, and result models; tool gateway contracts | This proposal, design, specs, tasks; model and tool contract tests | Requirement-to-test mapping in the verification document | Review that scope and contracts match Operations and Controller owners |
| Phase 3: schema validation, structured outputs, explicit failures, partial data, no secrets | Deterministic rules, strict boundary validation, labelled partial results, redacted audit events | Test results; sample structured result and audit events | Valid/invalid, stale, partial, conflicting, missing-field, timeout, and malformed-data tests | Validate business thresholds, cost rates, and accepted risks |
| Phase 4: output validation, unavailable tools, low confidence, regressions | Degraded-mode handling, confidence policy, guardrail on reasoning | Focused pytest summary; named scenario list | Agent tests for normal, partial, missing, conflicting, low-confidence evidence; security tests | Review evidence and confirm intended escalation behavior |
| Operations capability: flight/route impact, fleet substitution, package load redistribution, delay and swap cost | Rules, redistribution plan, cost components, trade-off statement | Synthetic scenarios including proposal test case 6 and the conflicting-estimate scenario | Exact-value tests on capacity, cut-off, priority order, unprotected remainder, thresholds, cost | Operations owner confirms substitution rules and package priorities |
| Operations capability: own-network and partner flight sourcing for package rerouting | `find_replacement_flights`, reroute policy in the request, own-first allocation, partner booking deadlines and cost cap | Late-repair scenarios with and without partner flights; flight-search outage scenario | Tests of route match, service level, cut-off, capacity, deadline, policy, ordering, cost, and outage | Humans book any partner or own flight and set the reroute policy; the agent books nothing |
| ADK agent and bounded model use | ADK `LlmAgent` definition, prompts A/B/C, typed reasoner protocol, deterministic offline reasoner | Prompt text and guardrail tests | Construction test; guardrail rejection tests; no network or model call in tests | Approve any live model configuration and credentials separately |
| Human approval and auditability | Advisory-only result, approval-required flag, correlated audit events | Sample audit events without sensitive data | Tests that no result approves or executes an action | Ops lead and Maintenance/airworthiness authority retain all approval authority |

The deterministic offline reasoner is a test and demonstration substitute, not evidence of live LLM behavior; live model evaluation requires a separate, approved configuration. Installation or scaffolding alone is not evidence of behavior; retained verification must show these rules and safeguards working.
