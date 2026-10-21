# Design

## Context

See [proposal.md](proposal.md) for motivation and scope and [specs/operations-impact-analysis/spec.md](specs/operations-impact-analysis/spec.md) for the observable behavior contract. The repository currently has no capability specifications or Operations implementation. The source Operations proposal calls for a top-level specialist returning operational impact to the Controller (H6/H7), and the system proposal reserves orchestration, compliance gating, weighted ranking, and final report generation for the Controller.

Implementation must use the existing project baseline: Python, Google ADK, Pydantic 2, typed adapters, deterministic local/mock integrations, pytest, and Ruff. All actions remain advisory; adapter calls are read-only. Unit and contract tests must not depend on live operational services or model calls.

## Goals / Non-Goals

**Goals:**

- Define a versioned boundary for Controller-supplied recovery candidates and Operations results.
- Gather relevant schedule, route, fleet, crew, customer, disruption, and package evidence through validated adapters.
- Keep reproducible schedule/assignment feasibility, impact classification, redistribution, and cost arithmetic outside model judgment.
- Make evidence provenance, missing/stale inputs, uncertainty, tool failures, and degraded status explicit in output and audit events.
- Return domain-specific option findings that a later Controller change can aggregate.

**Non-Goals:**

- Implement Controller intake, routing, shared-case orchestration, conflict aggregation, compliance gating, weighted scoring, close-score behavior, or final report generation.
- Call Maintenance or Materials & Logistics directly or add cross-agent orchestration.
- Execute swaps, bookings, dispatch, schedule changes, or package transfers; make approval decisions; assert airworthiness or regulatory approval.
- Require live airline systems for local operation, demonstration, or tests.

## Decisions

### Component boundaries and contracts

Use a domain package with separate responsibilities for:

1. **ADK Operations specialist boundary:** accepts a validated case context and candidate options supplied by the Controller and returns one complete domain result. It does not own routing, shared workflow state, or system-wide candidate ranking (ARD-SYS-001..003, ARD-OPS-004..005).
2. **Pydantic contracts:** validate and version the request, candidate option, evidence item, adapter result/error, package allocation, cost estimate, and response. Evidence items carry source, observed-at time, freshness/status, and the fact value. The result carries status, confidence, impact level, affected resources, per-option findings, evidence references, assumptions, missing/stale data, conflicts, risks, rationale, and next steps (ARD-TEC-003, ARD-PRN-005, ARD-PRN-007, ARD-OPS-005).
3. **Read-only adapters:** translate typed domain requests to operational source calls, validate responses, and return structured success or failure. Mock and future live implementations share the same typed interface (ARD-SYS-007..009, ARD-SEC-001..004).
4. **Deterministic assessment services:** validate schedules and assignments, establish option feasibility, calculate impacts/costs, classify impact, and allocate package capacity under configured constraints. No adapter or deterministic service can issue an operational write (ARD-PRN-002..003, ARD-SEC-002).
5. **Bounded reasoning and normalization:** if ADK model reasoning is used, provide only validated, relevant evidence and deterministic results. The model may interpret trade-offs and produce concise rationale but cannot alter facts, calculations, allowlists, thresholds, or approval policy; its output is validated against the response contract (ARD-TEC-002, ARD-TEC-005, ARD-PRN-004, ARD-SEC-005).

The result contract distinguishes **evidence** (source-backed values and provenance) from **assumptions** (explicitly labeled decision inputs), **derived values** (deterministic calculations with their inputs), and **reasoning** (bounded plain-language interpretation). It does not include private chain-of-thought.

### Tool adapter contracts and MCP boundary

Define typed read-only operations for:

| Adapter operation | Required request context | Validated result |
|---|---|---|
| Flight schedule and route | Case/correlation IDs, affected flight IDs, route, operating window | Flight legs, planned times, route state, source freshness |
| Disruption context | Routes and time window | Active disruption facts, affected segments, source freshness |
| Fleet assignment and substitute availability | Candidate tail/type, station, time window | Existing assignments, availability window, conflicts |
| Crew and station constraints | Candidate flight/route and operating window | Coverage/constraint facts and provenance |
| Customer service priority | Affected service/route context | Service commitments and configured priority facts |
| Package manifest and capacity | Flight IDs and candidate tails | Package counts/service levels, tail-specific capacity, sort/cut-off windows |

Requests and results use Pydantic validation and structured errors for invalid data, unavailable source, timeout, stale response, and conflict. Adapters expose no write methods. Implement local/mock adapters first. If an adapter crosses an MCP process or service boundary, use the supported MCP SDK and preserve the same typed validation, allowlisting, timeout, error, and audit behavior; do not add MCP as a requirement for an in-process mock (ARD-TEC-006, ARD-SEC-001..004).

### Deterministic evaluation

- Validate required fields, source timestamps, and configured freshness limits before calculating impact. Treat missing freshness metadata as unavailable freshness evidence, not as current data.
- Detect overlapping aircraft assignments, route/schedule conflicts, unavailable substitute tails, and explicit crew/station constraints using deterministic rules. Return the affected resource and rule outcome; do not ask the model to decide feasibility.
- Evaluate each candidate supplied by the Controller: repair using the supplied return-to-service estimate, aircraft swap, or delay. Return candidate-level impact and cost estimates. Do not calculate a system-wide score or rank (ARD-OPS-002..008).
- Calculate impact level from documented configurable thresholds. Keep thresholds in settings, not prompts or source literals, and include the applied rule/configuration version in derived evidence.
- Redistribute no more packages than the remaining capacity of each target tail and only when arrival and handling fit its sort/cut-off windows. Apply the configured service-level ordering, then a stable manifest order for ties; preserve the allocation and unprotected counts by service level. If the ordering or required timing/capacity evidence is missing, do not infer a protected allocation.
- Calculate costs from explicit per-option mock/configured line items, including delay/swap cost and configured exposure cost for unprotected packages. Return currency, source/configuration provenance, and calculation inputs. If a component cannot be calculated, mark it unavailable and identify the missing input instead of substituting zero. Mock values are demonstrations, not claims about real operating costs.

These decisions implement ARD-OPS-001..009 and ARD-NFR-003. Model judgment may explain material customer trade-offs but cannot override a deterministic conflict, capacity limit, cut-off, or cost result (ARD-PRN-003..005, ARD-OPS-007..009).

### Uncertainty, timeout, and failure behavior

- Configure bounded timeouts for each adapter and model call; use asynchronous I/O where beneficial. Bound retries and make read retries idempotent for the same request/correlation identifier (ARD-TEC-007, ARD-NFR-001..002, ARD-RES-005).
- Convert adapter failures into a structured failure with component, category, retryability, and case impact. Return a partial result only when some conclusions remain evidence-supported; enumerate unavailable analysis and missing inputs (ARD-RES-002..004).
- Preserve source disagreement and its provenance. Mark affected conclusions provisional and defer approval regardless of confidence (ARD-OPS-006, ARD-GOV-004).
- Apply confidence policy consistently: at least 0.70 can identify a preferred path but never approve it; 0.50–0.69 is provisional; below 0.50 escalates. Missing data is not silently imputed (ARD-GOV-001..005, ARD-GOV-008).
- Do not add a successful-looking fallback for stale or unavailable operational inputs. If an explicitly configured mock is in use, label the evidence and result as mock (ARD-PRN-006, ARD-RES-006).

### Security, human gate, and observability

Tools are allowlisted by Operations role and least privilege. External content is untrusted and cannot redefine policy, agent role, or tool access. Logs and outputs exclude secrets and unnecessary sensitive operational details (ARD-SEC-001..008). The capability returns a recommendation for human review only; it cannot approve, reject, dispatch, or execute. A later approval workflow remains responsible for recording the authorized human action (ARD-PRN-001..002, ARD-GOV-006..008).

Emit structured events for input validation, each adapter invocation/result, conflict, degraded result, and completion. Include timestamp, event type, case ID, correlation/trace ID, component, status, and schema version; record evidence references, deterministic rule outcomes, and concise rationale, not private chain-of-thought. Add bounded counts/durations for tool failures, conflicts, and timeouts (ARD-PRN-008, ARD-OBS-001..005).

### ARD mapping

| Requirement | Design satisfaction |
|---|---|
| ARD-OPS-001..005 | Typed operational inputs, deterministic feasibility and classification, candidate repair/swap/delay assessment, and versioned structured output. |
| ARD-OPS-006..009 | Provisional treatment of stale/conflicting evidence, alternative customer trade-offs, conflict identification, and capacity/service/cut-off constrained package allocation with unprotected exposure and cost. |
| ARD-SYS-001, 003, 007..009 | One domain-scoped ADK specialist, typed adapters, deterministic mock implementation, and stable contracts for future sources. |
| ARD-TEC-001..009 | Python/ADK/Pydantic/settings/model boundaries, conditional MCP SDK use, bounded async calls, pytest, and Ruff validation. |
| ARD-PRN-001..008, ARD-GOV-001..008 | Advisory-only behavior, deterministic controls, evidence and uncertainty fields, confidence thresholds, conflict deferral, and no approval bypass. |
| ARD-RES-002..007, ARD-NFR-001..007 | Explicit timeout/failure/partial contracts, bounded retries, case isolation, reproducibility, configuration, and dependency declaration. |
| ARD-SEC-001..008, ARD-OBS-001..005 | Read-only allowlisted tools, validated untrusted inputs, prompt-injection resistance, redaction, traceable structured events, and no hidden-reasoning dependency. |
| ARD-TST-001..003, 005, 007..009 | Requirement-linked deterministic contract, behavior, security, regression, and human-gate tests. ARD-TST-004 and Controller ranking remain deferred. |
| ARD-OSP-001..005 | This change retains proposal/spec/design/task traceability and does not weaken normative requirements. |

## Risks / Trade-offs

- **Stale or inconsistent operational feeds** → Preserve source timestamps and conflicts, apply configured freshness limits, mark results provisional, and lower confidence or escalate rather than infer current state (ARD-OPS-006, ARD-PRN-006).
- **Package priority rules differ by station or service** → Keep the service-level order explicit and versioned in configuration; use deterministic fixtures and expose unprotected remainder. Missing policy configuration prevents claiming successful allocation (ARD-OPS-009, ARD-NFR-006).
- **Mock cost estimates are mistaken for real costs** → Label mock estimates, retain line-item inputs and configuration provenance, and report unavailable values explicitly (ARD-OPS-005, ARD-PRN-005..006).
- **Model wording overstates feasibility or certainty** → Treat deterministic calculations as authoritative, validate model output, expose evidence separately from assumptions, and apply confidence/human-gate rules outside the model (ARD-PRN-003..006, ARD-GOV-008).
- **MCP adds unnecessary coupling for local tests** → Keep the typed adapter interface independent of transport and introduce the MCP SDK only for a real process/service boundary (ARD-TEC-006, ARD-SYS-008).

No ARD deviation is required. The explicit trade-off is to prefer visible incomplete results over optimistic completion when freshness, capacity, cut-off, cost, or feasibility evidence is missing.

## Migration Plan

This is an additive capability with no existing Operations implementation or capability spec to migrate. Add the capability behind typed local/mock adapters first; future live adapters must satisfy the same contract and remain read-only. Rollback consists of disabling the new specialist entry point and retaining its OpenSpec artifacts and test evidence; no external operational state is changed by this capability.
