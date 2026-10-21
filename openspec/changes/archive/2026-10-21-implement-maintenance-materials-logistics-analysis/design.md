# Design

## Context

See [proposal.md](./proposal.md) for motivation and scope and `specs/` for the observable contracts. The archived `shared-foundation` provides versioned case, evidence, agent-result, tool-result, error, audit, settings, confidence, and human-decision primitives plus deterministic local adapters. It has no Maintenance/M&L agent definitions, domain payloads, H3/H4 exchange, or Controller case-context recorder. The existing agent proposals provide the domain roles and H2/H3/H4/H5 handshakes; the ARD remains normative.

## Goals / Non-Goals

**Goals:**

- Implement two domain-bounded Google ADK specialists that consume and return the shared versioned envelopes with typed domain payloads.
- Make Maintenance repairability, root-cause, recurrence, approval evidence, ground-time, need-by comparison, and ETA traceable to evidence.
- Make Materials & Logistics practical availability, compatibility/authorization, sourcing, shipping, ETA, and mock USD cost independently testable.
- Provide a direct, correlated H3/H4 peer exchange whose request and response can be appended to Controller-managed case context without implementing Controller ownership.
- Keep deterministic checks, confidence degradation, adapter allowlists, failure handling, and approval boundaries outside unconstrained model reasoning.

**Non-Goals:**

- Controller intake, routing, orchestration, shared context ownership, aggregation, conflict adjudication, or workflow completion.
- Operations analysis, candidate option construction, compliance-gate ownership, weighted scoring, ranking, or decision-reporting.
- Human approval execution, maintenance/work-order updates, procurement, reservation, transfer, borrowing, shipment, or other operational writes.
- Live airline, maintenance, inventory, vendor, or carrier connections. Any such integration requires a separate approved change.

## Decisions

### Specialist boundaries and shared result envelope

Add separate Maintenance and Materials & Logistics ADK agent modules, domain payload models, deterministic validators, and tool-adapter packages. Each agent returns the shared `AgentResult` envelope; role-specific content is validated by a dedicated Pydantic payload before it enters `role_payload`. Keep common evidence, assumptions, unknowns, warnings, conflicts, tool results, structured errors, confidence, and correlation contracts in `shared-foundation`; do not fork or modify those contracts here. This preserves domain isolation (ARD-SYS-003, ARD-NFR-004) and means a specialist result is evidence for the Controller, not a final recommendation or approval (ARD-CTL-006, ARD-GOV-008).

Use the proposals' bounded Prompt A (evidence grounding), Prompt B (domain assessment), and Prompt C (output validation) pattern. Model reasoning may interpret validated evidence and describe trade-offs only within its agent domain. Required fields, schema/version checks, recurring-failure counts, compatibility, authorization/traceability states, source freshness labels, cost arithmetic, confidence penalties, and result-shape checks remain deterministic. Retrieved content is untrusted data and cannot alter agent policy or tool permissions (ARD-PRN-003..005, ARD-SEC-004..005).

### Maintenance assessment and ETA

Maintenance consumes the case, defect, aircraft/work-order facts, maintenance history, engineering/safety evidence, part dependencies, and H4 response when available. Its result contains repairability (`feasible`, `uncertain`, `not_feasible`), root-cause category/confidence/evidence, required actions, estimated ground time or an explicit unsupported reason, repair labor cost, approval evidence state, assumptions, missing data, technical risks, confidence, and need-by assessment (ARD-MNT-001..010).

Apply the documented recurring-failure example as the initial deterministic policy: count matching part failures in a rolling 90-day window and report the count only when records support it. The initial configured threshold is three occurrences; the threshold/window remain typed non-secret settings so domain owners can adjust them without changing the serialized payload. A preferred replacement is a request for Materials & Logistics evaluation, never an assertion that a part is authorized, available, or airworthy.

When a required replacement part gates repair start, calculate the initial synthetic return-to-service estimate as parts-ready time plus the stated repair duration. Do not silently model overlapping maintenance work; retain both input estimates, mark unsupported overlap as unknown, and mark the result provisional when timing evidence is incomplete. Compare the resulting estimate with the case need-by time (the next scheduled departure when supplied by the case) (ARD-MNT-004, ARD-MNT-010, ARD-GOV-005).

### Materials & Logistics sourcing

Materials & Logistics receives part number, aircraft compatibility, quantity, station, transfer state, approved-alternate data, supplier/carrier constraints, need-by time, and the Maintenance H3 context. Deterministic validators calculate location consistency, source availability, transfer/transit lead time, and mock costs; they distinguish physical stock from practical usability within the recovery window. The output compares the failed and preferred part, and exposes each source path separately: internal transfer, borrow/pool, vendor purchase, and expedite, with FedEx Network priority freight/courier or commercial-carrier service, estimated USD cost, ETA, transfer requirement, source, and evidence references (ARD-MLG-001..006/009).

Part compatibility, authorization, and traceability are eligibility checks, not LLM judgments. A failed or unknown check prevents a part from being labeled eligible; the Controller remains responsible for excluding non-compliant recovery options before ranking (ARD-MLG-008, ARD-CTL-017).

The Materials & Logistics specialist receives validated source results and a deterministic assessment payload. It uses the same bounded Prompt A/B/C boundary as Maintenance and returns the shared `AgentResult` envelope with the versioned Materials payload. Model output may summarize evidence and add domain risks or assumptions, but a final validator preserves deterministic availability, eligibility, quote, and ETA fields from the supplied assessment. Missing, stale, conflicting, and failed source states remain visible in status, warnings, errors, and confidence; the specialist does not rank recovery options or perform approval or sourcing actions (ARD-PRN-003..005, ARD-MLG-001..009, ARD-GOV-003..005/008, ARD-RES-003..006).

### H3/H4 exchange and Controller-context seam

H3/H4 messages use versioned Pydantic payloads with case ID, exchange/request ID, trace/correlation context, timestamps, part identifiers, source-backed maintenance facts, station, need-by time, and response status. Request and response share the same exchange ID. Retries, if used, are bounded and idempotent for that ID; the original failure remains observable (ARD-DAT-003, ARD-RES-005).

Define a narrow append-only recorder protocol supplied by the caller. The peer workflow submits both H3 and H4 records to this port; the future Controller change will implement it against Controller-managed case context. The specialist change includes a deterministic in-memory recorder fixture and verifies ordering, case isolation, and failure behavior, but does not implement Controller state or routing. If recording fails, the exchange is incomplete and must not be represented as successfully coordinated (ARD-SYS-002/004, ARD-OBS-001..003, ARD-SEC-009).

### Read-only adapters, MCP, and degraded evidence

Expose only role-allowlisted read tools. Local tests and demos use explicit deterministic fixtures and the existing adapter result/error contracts. Where a tool crosses a process or service boundary using MCP, use the supported Python MCP SDK through the Google ADK tool integration and validate requests/responses as untrusted data. Do not add a direct model-provider call, arbitrary HTTP tool, live system endpoint, or write tool (ARD-TEC-002/005/006, ARD-SYS-007..009, ARD-SEC-001..005).

Unavailable, timed-out, malformed, partial, conflicting, and cached responses remain distinguishable. A cached response preserves original source/retrieval time, is explicitly marked stale/fallback, and carries a warning. Apply a configurable non-secret confidence penalty of `0.10` for the initial mock policy; clamp at zero and test that equivalent stale evidence never increases confidence. Missing or untrusted cache data produces a structured failure instead of a success-shaped fallback (ARD-MLG-007, ARD-RES-001/003..006, ARD-GOV-003..005). Source-specific freshness windows are not invented; a source must provide validity metadata or a later owner-approved policy.

### Verification and evidence

Use synthetic pytest fixtures and deterministic local tools only. Contract tests cover valid/invalid domain payloads; behavior tests cover repairability, recurring failures, authorization, practical availability, sourcing/cost/ETA, stale cache, timeouts, malformed responses, H3/H4 round-trip/recording failure, conflicts, and read-only/no-approval properties. The integrated scenario demonstrates P-110/P-120 with three failures in 90 days and leaves final approval, ranking, Go/No-Go, and sponsor communication to humans (ARD-TST-001..003/005/007/009, ARD-RUB-001..004).

### ARD requirement mapping

| ARD requirements | Design response |
|---|---|
| ARD-PRN-001..008 | Advisory-only specialist outputs, deterministic guards, evidence-backed domain conclusions, and traceable peer exchange. |
| ARD-TEC-002..006, 008..014 | Google ADK/Pydantic boundaries, MCP SDK when a process boundary is used, pytest/Ruff/mypy, declared dependency ranges, and reproducible setup. |
| ARD-SYS-003..004, 007..009 | Domain isolation, H3/H4 peer protocol and recorder port, typed read-only tools, deterministic local mocks, and a replaceable integration seam. |
| ARD-DAT-001, 003..010, 011..012 | Reuse shared versioned envelopes; add typed domain payloads, source references, explicit decision status, errors, and recovery-option references. |
| ARD-MNT-001..010 | Deterministic input/safety checks, repairability and ground-time fields, recurring-failure count, root-cause evidence, labor cost, need-by and return-to-service assessment. |
| ARD-MLG-001..009 | Deterministic stock/compatibility/ETA/cost checks, practical availability, stale-data labeling, authorization gating, and original/preferred part comparison. |
| ARD-GOV-001..005, 008 | Reuse confidence policy; missing/conflicting evidence remains visible; neither model nor degraded mode approves or bypasses the human gate. |
| ARD-RES-001, 003..007; ARD-SEC-001..009 | Explicit cached/degraded results, bounded/idempotent retries, case isolation, allowlisted read-only tools, prompt-injection boundary, redaction, and append-only recording. |
| ARD-OBS-001..004; ARD-NFR-001..007 | Correlated events, concise safe rationale, bounded settings, deterministic calculations, module separation, and local portability. |
| ARD-TST-001..003, 005, 007, 009; ARD-RUB-001..004; ARD-CAP-001..003 | Requirement-to-test mapping, normal/degraded/security/human-gate coverage, synthetic fixtures, and explicit framework/model/adapter/verification mapping. |

## Risks / Trade-offs

- **[LLM could overstate technical or supply certainty]** → Validate typed evidence first, separate facts from assumptions, retain missing/stale/conflict states, and keep eligibility calculations deterministic.
- **[The Controller recorder is not implemented in this scope]** → Require a typed append-only port and deterministic recorder tests; the later Controller capability must supply the production case-context adapter before orchestration uses H3/H4.
- **[The sequential ETA assumption can overestimate parallel maintenance work]** → Keep parts-ready and repair-duration components visible, mark unmodeled overlap as unknown, and revise only with approved task-dependency data.
- **[A confidence penalty may be mistaken for calibrated probability]** → Label the `0.10` value as a deterministic mock policy, expose it in non-secret settings, and do not claim empirical calibration.
- **[MCP may add operational complexity without a live backend]** → Keep MCP transport behind the typed adapter boundary and use deterministic in-process fixtures for unit tests; no live enterprise endpoint is introduced.

## Migration Plan

This is additive and has no existing specialist runtime data to migrate. Add domain modules and tests alongside `shared-foundation`; existing contracts remain backward compatible. Roll back by removing the specialist capability implementation and its new dependencies before downstream Controller work adopts these payload versions. Any persisted H3/H4 records require explicit schema-version handling before future storage is introduced.

## Open Questions

None block this proposal. The exact source-specific freshness limits and any live-system credentials/permissions require owner approval in a future integration change.