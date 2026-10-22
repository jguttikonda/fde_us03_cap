# Proposal

## Why

The repository has a deterministic Controller demo CLI and an Operations-only ADK Web entry point, but no browser-accessible path that runs a complete Controller workflow over synthetic case data. A Controller ADK Web root backed by the existing deterministic workflow and mock specialist ports would let the team inspect intake, orchestration, compliance, ranking, evidence, and the pending human gate in one end-to-end demonstration without connecting airline systems.

## What Changes

- Add a Controller ADK Web root agent that invokes the real `ControllerWorkflow` using deterministic synthetic Maintenance and Materials & Logistics ports and the existing local Operations adapters.
- Provide named synthetic scenarios for the complete repair path, unavailable inventory with degraded cached evidence, the three-hour/seven-hour time conflict, and close-score human choice; preserve typed Controller responses, warnings, conflicts, evidence references, and approval state in the Web interaction.
- Keep all enterprise data adapters local/mock and read-only. The web agent may call its configured Gemini model to interpret the user's request and select a demo scenario; it MUST NOT send live airline data, enable operational writes, decide a winner when human selection is required, or approve/execute an action.
- Add deterministic tests at the ADK tool and Controller workflow boundaries for every scenario, repeatability, structured errors, pending human approval, and absence of network/operational actions.
- Update the sponsor runbook and local setup notes with the ADK Web launch command, scenario prompts, expected outputs, model-credential requirement, and the distinction between mock enterprise data and model-provider traffic.

## Capabilities

### New Capabilities

None. The change reuses the existing Controller runtime and synthetic Operations contracts.

### Modified Capabilities

- `capstone-demonstration`: Make the deterministic synthetic Controller scenarios accessible through Google ADK Web while preserving the existing bounded, explainable, advisory-only demonstration contract.

## Impact

Expected changes are a new `adk_agents/controller_agent/` web entry point, deterministic synthetic Controller workflow adapters or fixtures under `src/aog_recovery/controller/`, focused tests under `tests/integration/`, and updates to `docs/capstone-demo-runbook.md`, `README.md`, and the ADK traceability evidence. No dependency or live enterprise adapter is assumed. Google ADK Web requires a locally configured model credential for conversational interaction; the credential remains in ignored environment configuration and must not be logged or committed. All airline case, specialist, inventory, fleet, schedule, and package data remains synthetic.

## ARD Traceability

### Addressed

- `ARD-TEC-002/005`, `ARD-CTL-006..010/016..018`: expose the existing typed Controller workflow through ADK Web without changing deterministic ownership, validation, escalation, or report contracts.
- `ARD-CTL-011..019`, `ARD-SYS-005`, `ARD-OPS-009`: demonstrate compliance-before-ranking, deterministic scores/trade-offs, candidate impact, and package evidence without adding a second scoring path.
- `ARD-GOV-001..008`, `ARD-PRN-001..002/006`, `ARD-SEC-001..003/008`: keep every result advisory, preserve confidence and close-score gates, and provide no approval or operational action capability.
- `ARD-RES-001..007`, `ARD-DAT-001..012`, `ARD-OBS-001..004`, `ARD-TST-001..009`: preserve typed synthetic inputs, stale/conflicting/unavailable states, case/trace evidence, structured failure behavior, and repeatable no-network scenario tests.
- `ARD-DEP-001..003/006`, `ARD-RUB-001..004/010`: document reproducible ADK Web setup and sponsor-facing expected outputs without implying live-system health or rehearsal completion.

### Deferred

- Validating a configured model credential with its provider; this requires an authorized model-backed request and is not part of offline tests.
- Qualified peer/InfoSec/Reference Architecture review, team Go/No-Go, demo rehearsal/presentation, live Q&A, sponsor acceptance, and all operational approvals (`ARD-TEC-020`, `ARD-RUB-005..011`, `ARD-DEP-005..006`).
- Live enterprise integrations and production deployment (`ARD-SYS-007..009`, `ARD-NFR-005`).

### Out of Scope

- Live airline, supplier, inventory, schedule, or identity data; the workflow uses synthetic fixtures and local adapters only.
- Any purchase, transfer, shipment, booking, dispatch, flight delay, aircraft assignment, approval, or other operational write (`ARD-PRN-001..002`, `ARD-GOV-006..008`, `ARD-SEC-001..003/008`).
- Changes to Controller scoring policy, compliance rules, confidence thresholds, or the inclusive two-point close-score rule (`ARD-CTL-011..019`).

**ARD deviations:** None. ADK Web's model-provider traffic is limited to conversational interpretation of synthetic demo requests; no live airline data is supplied to the model.

## Rubric and Capability Coverage

| Rubric area | Verification and retained evidence | Human responsibility |
|---|---|---|
| Agent functionality and engineering quality (Categories 1 and 3) | Deterministic Controller workflow scenarios, typed ADK response validation, tool/security tests, and repeatability evidence | Review behavior and unresolved risks; decide whether the model-backed demo boundary is acceptable |
| Spec-driven design (Category 2) | Modified `capstone-demonstration` delta, ARD-linked design/tasks, and implementation-to-test mapping | Review scope and confirm the implementation matches the ADK and mock-data boundary |
| RAPID controls (Category 4) | Update the modified-file inventory, tests, security findings, and backout guidance in retained readiness records | Qualified reviewer records identity, findings, and recommendation; team owns Go/No-Go |
| AI-assisted development practice (Category 5) | Preserve OpenSpec iteration and test-backed corrections in repository artifacts | Team explains accepted/rejected assistance; no human redirection is fabricated |
| Demonstration and communication (Category 6) | ADK Web launch/runbook, four scenario prompts, expected outputs, limitations, and pending human gate | Rehearse and present, answer live questions, and record sponsor feedback |
