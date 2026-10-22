# Proposal

## Why

Maintenance and Materials & Logistics currently have approved domain contracts but no runtime specialist implementations. Repair feasibility, recurring-failure history, practical part availability, authorized substitutes, sourcing cost, and lead time must be assessed together; without a typed peer exchange, their independent findings cannot reliably support a traceable recovery case.

## What Changes

- Implement Google ADK Maintenance and Materials & Logistics specialists over the archived `shared-foundation` contracts, with bounded Prompt A/B/C reasoning and deterministic validation before and after model calls.
- Add versioned role-specific result payloads for repairability, root-cause evidence, ground-time/return-to-service estimates, recurring failures, engineering/airworthiness approval state, material availability, part authorization/traceability, sourcing paths, shipping, cost, ETA, risks, assumptions, unknowns, and confidence.
- Implement the H3/H4 Maintenance-to-Materials & Logistics exchange for the original and preferred replacement parts. Define a typed recorder seam so each request and response can be appended to Controller-managed case context without implementing Controller routing or orchestration here.
- Add deterministic, allowlisted, read-only tool adapters and synthetic fixtures for maintenance/work-order/engineering and inventory/alternate-parts/transfer/supplier/shipping data. Use the supported MCP SDK when tools cross a process or service boundary; local tests and demos require no enterprise connectivity.
- Label cached or stale data, preserve source and retrieval time, emit warnings, and deterministically lower confidence. Unavailable, timeout, malformed, partial, or conflicting inputs remain explicit; no success-shaped fallback or operational write is permitted.
- Calculate sourcing costs in mock USD and compare internal transfer, borrow/pool, vendor purchase, and expedite paths, including FedEx Network priority freight/courier and commercial-carrier options. No live pricing, purchasing, reservation, transfer, shipment, or maintenance action is performed.
- Add contract, deterministic rule, adapter-failure, H3/H4, and integrated synthetic tests, with requirement-to-test traceability and concise implementation evidence.

### Assumptions

- Recurring failure is initially reported when at least three matching part failures occur within a rolling 90-day window, following the documented P-110/P-120 example; the window and threshold are typed non-secret policy settings.
- Staleness is determined only from explicit source validity metadata or a configured source policy. The initial implementation does not invent a universal inventory TTL.
- When a required part gates repair start, the initial synthetic ETA policy treats parts-ready time and repair duration as sequential; the result retains both component estimates and flags unsupported overlap as unknown rather than presenting a false precision.
- Cost, carrier, supplier, engineering, and maintenance records used in tests and demonstrations are synthetic fixtures.

## Capabilities

### New Capabilities

- `maintenance-assessment`: Evidence-grounded maintenance repairability, root-cause, recurring-failure, ground-time, need-by, approval-status, risk, and return-to-service assessment.
- `materials-logistics-sourcing`: Practical part availability, deterministic compatibility/authorization checks, sourcing and shipping comparisons, cost/ETA, material readiness, and visible degradation.
- `maintenance-materials-logistics-coordination`: Typed H3/H4 requests and responses for failed and preferred parts, with traceable exchange recording through a Controller-context recorder interface.

### Modified Capabilities

None. The existing `shared-foundation` contract remains the common boundary; this change adds specialist behavior and domain payloads without changing its requirements.

## Impact

- Adds specialist ADK agent modules, typed domain payloads and validators, maintenance and Materials & Logistics read-only tool adapters, H3/H4 exchange/recording contracts, synthetic fixtures, and unit/contract/integration tests.
- Extends runtime dependencies with the supported MCP Python SDK only for the scoped MCP process/service tool boundary; retains the existing Python 3.14, Google ADK, Pydantic, `pydantic-settings`, pytest, and Ruff stack.
- No live enterprise APIs, credential integration, procurement/transfer/shipping execution, Controller workflow, option scoring/ranking, report generation, Operations analysis, or human approval UI/workflow is introduced.

## ARD Traceability

### Addressed

- **ARD-PRN-001..008** — bound specialist reasoning to its domain, keep the system advisory, use deterministic gates/calculations, preserve evidence and degradation, use typed contracts, and correlate exchanges to a case.
- **ARD-TEC-002..006, ARD-TEC-008..014** — use Google ADK and Pydantic, keep model access inside ADK, use the MCP SDK when crossing a process/service boundary, test with pytest/Ruff/mypy, declare compatible dependencies, and retain the documented reproducible setup.
- **ARD-SYS-003..004, ARD-SYS-007..009** — isolate specialist responsibilities, support direct Maintenance/M&L peer collaboration with both messages recorded through Controller-owned context, and use replaceable typed read-only adapters with deterministic mocks.
- **ARD-DAT-001, ARD-DAT-003..010, ARD-DAT-011..012** — validate versioned role-specific results, provenance, correlation, explicit failures and decision status; represent repair, substitution, transfer, and escalation paths without ranking them.
- **ARD-MNT-001..010** — validate maintenance inputs and safety evidence; report repairability, ground time, required actions, uncertainty, recurring-failure support, root-cause evidence, repair labor cost, need-by comparison, and return-to-service estimate.
- **ARD-MLG-001..009** — validate stock, compatibility, thresholds, location and lead time; distinguish physical from practical availability; compare sourcing/shipping paths and costs; label stale data; prohibit unsupported substitutions; compare original/preferred parts and record H3/H4.
- **ARD-GOV-001..005, ARD-GOV-008** — preserve confidence thresholds, missing-data/conflict escalation, and the no-bypass boundary; specialist outputs never approve an operational decision.
- **ARD-RES-001, ARD-RES-003..007** — model labeled cached data, explicit agent/tool failures, partial results, bounded idempotent retries where used, visible fallback, and case isolation.
- **ARD-SEC-001..008, ARD-SEC-009** — enforce least privilege, read-only allowlists, untrusted-input validation, prompt-injection boundaries, secret/redaction safeguards, no unsupported airworthiness claims, and append-oriented exchange evidence.
- **ARD-OBS-001..004, ARD-NFR-001..007, ARD-TST-001..003/005/007/009, ARD-RUB-001..004, ARD-CAP-001..003** — define correlated events, bounded configuration, deterministic modules and fixtures, scenario/contract/security/human-gate tests, and explicit model/adapter/control/verification mapping.

### Deferred

- **ARD-SYS-001..002, ARD-CTL-001..019, ARD-OPS-001..010** — complete Controller intake/routing/context ownership, end-to-end orchestration, cross-domain adjudication, compliance gating, option generation/ranking, reporting, and Operations analysis remain separate changes. This change supplies specialist outputs and a recorder port only.
- **ARD-GOV-006..007, ARD-TST-005 end-to-end approval flow** — human approval records and the dual-authority approval workflow remain in the later reporting/approval capability. Here, agents report approval evidence/state and cannot approve.
- **ARD-TEC-017..020, ARD-RUB-005..011, ARD-DEP-001 onward** — CI/security scanning, final RAPID peer review and Go/No-Go, complete capstone evidence, and live sponsor demonstration remain human/project delivery work. This change retains focused test and synthetic scenario evidence only.
- Live integrations and source-specific freshness policies remain subject to separately approved changes with their system owners.

### Out of Scope

- **ARD-PRN-002 operational execution** and **ARD-SEC-002 write access** — no ordering, reservation, transfer, shipment, work-order update, aircraft action, or flight action.
- **ARD-CTL-009..019** — no candidate recovery-option ranking, weighted scoring, close-score behavior, or decision brief.
- Operations impact, package redistribution, Controller orchestration, and final recommendation synthesis.

No ARD deviation is requested.

## Rubric and Capability Coverage

| Rubric checkbox / proposal capability | Planned support | Retained evidence | Verification | Human responsibility |
|---|---|---|---|---|
| Phase 2: OpenSpec contracts and implementation checklist | Three focused capability deltas with domain contracts, H3/H4 seams, and traced tasks | Proposal, design, specs, tasks | Requirement-to-model-to-test mapping | Review boundaries and domain semantics |
| Phase 3: correct specialist behavior and engineering quality | Evidence-grounded maintenance and sourcing results, deterministic checks, MCP/read-only adapters, visible failures | Synthetic fixtures and structured events | Contract, rule, degraded-mode, and adapter tests | Confirm technical and supply decisions are credible |
| Phase 4: degraded operation and regression evidence | Labeled cache, partial/stale/conflicting source modes, bounded retries, explicit missing data | Focused test summary and scenario records | Failure, conflict, stale data, no-fallback, and regression tests | Review accepted limits and risk |
| A2A coordination | H3/H4 payloads and Controller-context recording seam | Exchange identifiers and deterministic recorder fixtures | Round-trip, correlation, retry/idempotency, and conflict tests | Controller owner integrates the recorder in its later change |
| Human approval and safety | Approval status is evidence only; all actions remain human-controlled | Decision-boundary contract and test output | No-agent-approval and no-write tests | Authorized Ops and Maintenance/airworthiness roles retain approval |

Framework installation is not evidence of behavior. The implementation change must retain passing behavior tests and sanitized synthetic results.