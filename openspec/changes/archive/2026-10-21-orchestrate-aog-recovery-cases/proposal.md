# Proposal

## Why

The shared contracts and Maintenance, Materials & Logistics, and Operations specialists now exist, but there is no Controller runtime to accept an AOG case, own the case-scoped workflow state, invoke the specialists, or deliver a validated, traceable pre-ranking handoff. This change adds that orchestration boundary while leaving weighted ranking and decision-brief generation to a later Controller stage.

## What Changes

- Add a bounded Google ADK Controller entry point backed by deterministic intake, routing, invocation, result validation, aggregation, and escalation logic.
- Validate versioned AOG intake before any agent or tool is invoked. Record source health, selected and omitted agents, and routing rationale against case-scoped context, then enforce those routing decisions during specialist invocation.
- Deterministically construct the repair-original, repair-preferred/alternate, aircraft-swap, and flight-delay candidates supported by the case evidence. For each candidate, invoke Maintenance and Materials & Logistics concurrently, preserve their direct H3/H4 collaboration through Controller-owned case context, and validate every result envelope and evidence reference before aggregation.
- Invoke Operations for each candidate using its typed request boundary and the readiness ETA produced by that candidate's specialist assessments. Preserve per-candidate operational impact, package outcomes, conflicts, and costs in an unranked handoff without scoring or sorting candidates.
- Apply deterministic result-presence checks, conflict and missing-data handling, confidence disposition, escalation rules, and the compliance eligibility gate before handing the unranked package to the later Controller ranking stage.
- Keep the approval boundary fail-closed: orchestration output remains advisory, explicitly requires human approval, and exposes no operational write or execution action. Existing human decision records and gate contracts remain authoritative.
- Add deterministic fake-agent and mock-adapter tests for valid/invalid intake, routing, case isolation, parallel specialist failure, H3/H4 recording, Operations candidate evaluation, missing/stale/conflicting evidence, confidence reduction, compliance exclusion, and approval non-bypass.

### Assumptions

- An accepted AOG case initially routes to Maintenance, Materials & Logistics, and Operations; any agent intentionally omitted by a future policy must have a deterministic recorded reason.
- Maintenance and Materials & Logistics run concurrently for each candidate. Their H3/H4 exchange remains peer-to-peer but is persisted through a recorder owned by Controller case context. Operations runs once per candidate after its required readiness evidence is available.
- The Controller creates only the candidate set and compliance eligibility data required by Operations and the downstream ranking stage. It does not calculate weighted scores, assign relative ranks, or render a decision brief in this change.
- Confidence aggregation uses the minimum confidence among required validated agent results, with deterministic caps or escalation for missing results and conflicts; conflict always requires human adjudication regardless of numeric confidence.
- A workflow handoff is not an operational recommendation or approval. The workflow status remains pending, provisional, or escalation-required until the later recommendation and human-decision stages complete.

## Capabilities

### New Capabilities

- `recovery-orchestration`: Controller-owned AOG intake, deterministic routing, shared case context, bounded specialist invocation, result aggregation, conflict/failure handling, pre-ranking candidate/compliance handoff, escalation, and fail-closed human-approval state.

### Modified Capabilities

None. This change consumes the existing `shared-foundation`, `maintenance-assessment`, `materials-logistics-sourcing`, `maintenance-materials-logistics-coordination`, and `operations-impact-analysis` contracts without changing their requirements.

## Impact

- Adds a Controller orchestration package and versioned workflow/context/routing/handoff contracts, with typed specialist invocation ports and deterministic local/mock composition.
- Uses existing Maintenance and Materials & Logistics ADK boundaries, existing H3/H4 exchange/recorder contracts, existing Operations request/outcome models, shared tool/error/evidence contracts, confidence policy, audit events, and human gate.
- Adds no live enterprise integration, operational write tool, new model provider, ranking algorithm, ranked recommendation, or decision-report renderer.
- Adds unit, contract, integration, and traceability evidence for the orchestration capability.

## ARD Traceability

### Addressed

- **ARD-SYS-001..004, ARD-SYS-006..009** — introduce Controller orchestration over the existing four-agent architecture; own case context/routing; preserve Maintenance–Materials H3/H4 audit; keep human approval separate; use typed read-only adapters and deterministic mocks.
- **ARD-DAT-001..010** — validate versioned AOG input, specialist envelopes, evidence references, correlation, tool failures, and explicit degradation at Controller boundaries.
- **ARD-CTL-001..008, ARD-CTL-010** — validate intake; record source health and explicit routing; own case-scoped context; validate specialist presence/completeness/evidence; preserve conflicts and partial failures; escalate; record non-final workflow status.
- **ARD-CTL-017..018** — apply the deterministic compliance eligibility gate, construct the supported candidate set, evaluate Maintenance and Materials & Logistics concurrently per candidate, and evaluate Operations per candidate. Weighted scoring and ranking are deferred separately.
- **ARD-GOV-001..005, ARD-GOV-008** — apply shared confidence thresholds, mark provisional/low-confidence cases, preserve conflict and missing-input effects, and prevent confidence or degraded mode from bypassing human approval.
- **ARD-RES-002..007** — retain Operations timeouts, structured specialist failures, bounded calls, partial results, visible fallback/degradation, and case isolation.
- **ARD-SEC-001..009** — use role-appropriate read-only tools, validate untrusted inputs, preserve the prompt-injection boundary, prevent operational writes, and retain append-oriented case/audit evidence.
- **ARD-OBS-001..004, ARD-NFR-001..003/005..006, ARD-TST-001..003/005/007..009** — correlate routing/invocation/aggregation/escalation events; bound timeouts; keep deterministic test seams; test normal, partial, failed, conflicting, security, and human-gate cases.
- **ARD-TEC-002..005, ARD-TEC-008..009** — use Google ADK and Pydantic boundaries, pytest fakes, Ruff, and deterministic local integrations.

### Deferred

- **ARD-CTL-009, ARD-CTL-011..016, ARD-CTL-019, ARD-SYS-005** — final recommendation generation, weighted scoring, score transparency, relative ranking, close-score behavior, decision-brief rendering, and final cost/ranking synthesis belong to the later recommendation stage. This change hands off unranked candidate assessments and preserves Controller ownership of that future stage.
- **ARD-TST-006** — the complete ranked-recommendation functional scenarios, including close-score selection and final recovery recommendation, are deferred to the later ranking/approval change. This change tests orchestration outcomes only and does not assert a final recommendation.
- **ARD-GOV-006..007 and approval UI/workflow** — the shared decision and gate contracts remain authoritative, but collecting human decisions and producing the final recommendation version are handled by the later approval capability. This workflow cannot mark a case approved or execute an action.
- **ARD-TEC-017..020, ARD-RUB-005..011, ARD-DEP-001 onward** — CI/security scans, RAPID sign-off, Go/No-Go, sponsor demonstration/live Q&A, and deployment readiness remain human/project delivery work; synthetic orchestration evidence is retained here only.

### Out of Scope

- **ARD-PRN-002 operational execution and ARD-SEC-002 write access** — no booking, purchase, reservation, transfer, shipment, aircraft assignment change, flight delay, or customer action.
- **ARD-OPS-001..010 implementation** — Operations behavior is consumed through its existing contract; this change does not alter Operations domain logic.
- Weighted scores, ranks, final recommendation prose, final decision-brief rendering, and presentation/UI.

No ARD deviation is requested. The ranking/report boundary is an explicit scope deferral, not a change to Controller ownership in the complete system.

## Rubric and Capability Coverage

| Rubric checkbox / proposal capability | Planned support | Retained evidence | Verification | Human responsibility |
|---|---|---|---|---|
| Phase 2: OpenSpec contracts and implementation checklist | One focused orchestration capability with typed workflow, context, routing, and handoff contracts | Proposal, design, spec, tasks | Requirement-to-model-to-test mapping | Review ownership and deferred boundaries |
| Phase 3: correct orchestration and engineering quality | Validated intake, explicit routing, specialist invocation, result validation, conflict handling, deterministic pre-ranking handoff | Synthetic case records and structured audit events | Contract, routing, failure, conflict, and integration tests | Confirm operational workflow and domain ownership |
| Phase 4: degraded operation and regression evidence | Partial results, timeouts, missing/stale/conflicting evidence, bounded retries, fail-closed status | Synthetic degraded-case output and audit trail | Failure, low-confidence, isolation, and no-fallback tests | Review degraded-mode risk and recovery policy |
| A2A coordination | Maintenance–Materials H3/H4 remains peer-to-peer with Controller-owned recording | Exchange IDs, order, evidence references, and audit events | H3/H4 recording and case-isolation tests | Controller owner reviews case-context retention |
| Human approval and safety | Every handoff requires human approval; no automatic action or confidence bypass | Pending gate state and shared human-decision references | High-confidence, low-confidence, conflict, and no-action tests | Authorized Ops and Maintenance/airworthiness reviewers decide |

Framework installation is not evidence of behavior. Verification evidence is produced by deterministic tests and retained synthetic results.
