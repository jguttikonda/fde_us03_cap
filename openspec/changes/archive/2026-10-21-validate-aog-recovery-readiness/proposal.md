# Proposal

## Why

The AOG Coordinator now has implemented agents, typed boundaries, deterministic scoring, and focused test evidence, but capstone readiness still depends on integrated proof, current operating documentation, and human-owned RAPID, Go/No-Go, and sponsor activities. The rubric and ARD require end-to-end degraded-mode validation and retained evidence; the current repository also lacks an unavailable-inventory-to-labeled-cache fallback test and a sponsor demo runbook, while some readiness drafts still describe the earlier change or leave critical sections pending.

## What Changes

- Add deterministic end-to-end and regression acceptance coverage for the proposal's functional cases: normal repair; unavailable part with swap; unavailable Materials & Logistics source with explicitly labeled cached evidence, reduced confidence, and a visible warning; options within the inclusive two-point threshold requiring human selection; P-110/P-120 Maintenance–Materials A2A with recorded exchange; capacity- and cut-off-limited package redistribution; pre-score compliance exclusion; cost-versus-speed ranking; and materially conflicting three-hour Maintenance versus seven-hour Operations estimates that defer approval. Include unavailable-tool, timeout, malformed-schema, missing/conflicting-data, and partial-result paths.
- Add cross-agent schema and tool-contract validation plus security and audit regression checks for role allowlists, read-only boundaries, untrusted tool content, secret redaction, case/trace correlation, evidence provenance, and absence of operational actions. Use deterministic fixtures and local/mock adapters; tests make no live model or enterprise calls.
- Close the documented cached-inventory fallback gap only within the existing Materials & Logistics contract: use cache only when provenance and retrieval time are available, mark cached/stale validity and fallback in result, brief, and audit, reduce confidence deterministically, and return a structured degraded result or failure when no usable cache exists. Never turn cache into current evidence or a success-shaped result.
- Update setup and readiness documentation to reflect the implemented system, supported Python/dependency setup, configuration without committed secrets, startup and adapter health checks, verification commands/results, known limitations, and a whole-workflow backout procedure. Refresh the RAPID peer-review and Go/No-Go drafts with current scope, inventory, evidence, outstanding risks, and explicit fields for qualified human review and team decisions.
- Add a sponsor-facing, deterministic demo runbook with a concise happy path and degraded/conflict/close-score scenarios, expected evidence-backed outputs, business value, caveats, human approval boundary, and Q&A prompts. Keep the rehearsal, presentation, reviewer judgments, and final decisions pending until people perform them.

No live enterprise integration, production deployment, purchase/transfer/booking/dispatch action, or automated approval is introduced. Any operational decision remains advisory and subject to the required human approval.

## Capabilities

### New Capabilities
- `recovery-workflow-resilience`: Integrated, reproducible verification of complete and degraded AOG recovery workflows, including the proposal's functional cases and explicit evidence gaps.
- `security-and-audit`: Cross-component verification of least privilege, read-only allowlists, input boundaries, redaction, audit integrity, and the prohibition on agent-executed operational actions.
- `deployment-readiness`: Reproducible environment and configuration guidance, health checks, verification evidence, documented limitations, and backout readiness.
- `capstone-demonstration`: Deterministic sponsor scenarios and a runbook that communicates value, explainability, degraded behavior, and human accountability.

### Modified Capabilities

None. Existing specialist and Controller specifications already define the underlying domain behavior; this change adds cross-capability readiness and evidence requirements. The implementation gap in cached fallback is covered by the existing `materials-logistics-sourcing` contract and will be verified against it, not used to weaken or replace it.

## Impact

Expected implementation touches the Materials & Logistics cache boundary and Controller end-to-end fixtures only where verification exposes a gap; tests under `tests/` will cover contracts, integrated scenarios, security, audit, and regressions. Documentation work will update `README.md`, `docs/rapid-peer-review.md`, and `docs/go-no-go-checklist.md`, and add a sponsor runbook and consolidated readiness evidence. No new runtime dependency or live adapter is assumed. Review identities, human decisions, operational/airworthiness approvals, and sponsor acceptance must be supplied by their authorized people.

## ARD Traceability

### Addressed

- `ARD-TST-001..009`: Map each requirement and functional case to deterministic schema, tool, agent, scoring, human-gate, security, and regression tests; retain test results.
- `ARD-RES-001..007`, `ARD-GOV-004..008`, `ARD-MLG-007`, `ARD-CTL-015..017`, `ARD-OPS-009`: Verify labeled cached fallback, timeouts, missing/conflicting evidence, inclusive close-score selection, compliance-first ranking, package impact, and approval deferral.
- `ARD-SEC-001..009`, `ARD-OBS-001..004`, `ARD-SYS-004`: Verify least privilege, role allowlists, read-only access, untrusted-input handling, secret redaction, append-oriented case-correlated audit, and recorded A2A exchange without private chain-of-thought.
- `ARD-DEP-001..006`, `ARD-CAP-001..003`, `ARD-RUB-001..004/008..010`, `ARD-TEC-019`: Map rubric capabilities to runtime behavior, tests, retained evidence, setup/health/backout documentation, and demo preparation; identify gaps rather than claiming framework installation as proof.
- `ARD-TEC-020`, `ARD-RUB-005..007/011`, and `ARD-DEP-005..006`: Prepare review and Go/No-Go records and sponsor materials, while leaving reviewer conclusions, team decisions, rehearsal, live presentation, and Q&A to humans.

### Deferred

- Qualified independent RAPID review, author/reviewer identities, review findings, and final review recommendation; the team Go/No-Go outcome and rationale; and sponsor rehearsal, presentation, and live Q&A remain human delivery activities (`ARD-TEC-020`, `ARD-RUB-005..007/010..011`, `ARD-DEP-005..006`). This change may update draft records and collect supporting evidence but MUST NOT mark those activities complete on behalf of people.
- Production deployment and live enterprise-system connectivity remain future work; local/mock verification does not establish live operational readiness (`ARD-SYS-007..009`, `ARD-NFR-005`).

### Out of Scope

- Adding operational write tools, automatic approval, or claims of airworthiness; the system remains advisory and read-only (`ARD-PRN-001..002`, `ARD-GOV-006..008`, `ARD-SEC-001..003/008`).
- Changing specialist reasoning or the Controller scoring policy, weights, compliance gate, or two-point close-score rule; readiness tests verify those existing contracts (`ARD-CTL-011..019`, `ARD-SYS-005`).

**ARD deviations:** None requested. No requirement is waived or weakened.

## Rubric and Capability Coverage

| Rubric area | Framework and verification | Retained evidence | Human responsibility |
|---|---|---|---|
| Agent functionality and engineering quality (Categories 1 and 3) | Python/Pydantic contracts, deterministic pytest fixtures and local adapters, Ruff/mypy, coverage and approved security scans; validate complete, degraded, failure, conflict, and regression cases | Test-to-ARD map, command results, coverage, known warnings and limitations | Review findings and decide whether remaining risks are acceptable |
| Spec-driven design (Category 2) | OpenSpec requirements, scenarios, tasks, and ARD-linked traceability | Proposal, design, four capability deltas, tasks, and validation result | Review scope, assumptions, capability coverage, and deviations |
| RAPID controls (Category 4) | Existing RAPID and Go/No-Go templates updated against current implementation and evidence | Modified-file inventory, review criteria, test summary, open findings, actionable backout, decision fields | Qualified peer completes review; team records the Go/No-Go decision and rationale |
| AI-assisted development (Category 5) | Existing project instructions and OpenSpec iteration evidence | Inspectable prompts/design notes, accepted corrections, and human redirection evidence where available | Team explains what was accepted, rejected, or corrected; no human redirection is fabricated |
| Demonstration and communication (Category 6) | Deterministic fixtures and a sponsor-oriented runbook designed for a maximum ten-minute demonstration | Scenario inputs/outputs, expected report, risks, caveats, business value, and debrief prompts | Rehearse, present, answer live questions, and defend decisions |

| New capability | Runtime/framework and deterministic controls | Verification and retained evidence | Human responsibility |
|---|---|---|---|
| `recovery-workflow-resilience` | Existing Controller and specialist contracts with local/mock adapters; deterministic cache and failure state | End-to-end functional cases, schema/tool contracts, timeout and degraded-mode regressions, requirement-to-test map | Review evidence and any unresolved behavior gaps |
| `security-and-audit` | Existing typed read-only adapters, role allowlists, and structured audit boundary | Security-negative tests, redaction and correlation assertions, audit/event evidence | Complete independent security and architecture review |
| `deployment-readiness` | Existing Python 3.14, `uv`, typed settings, and documented local startup | Environment, health, backout, test evidence, and updated readiness decision drafts | Supply review identities, outstanding issue disposition, and Go/No-Go outcome |
| `capstone-demonstration` | Synthetic cases and deterministic Controller report; no live service required | Runbook with expected outputs, timing, caveats, and scenario-to-requirement mapping | Rehearse and deliver the presentation and live Q&A |
