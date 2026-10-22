# Design

## Context

See `proposal.md` for motivation and `specs/` for the behavior contracts. The repository already has typed case, evidence, tool, specialist, Controller, and human-decision contracts; deterministic local adapters; component-level degradation, timeout, security, audit, scoring, and approval tests; and verification/RAPID/Go-No-Go drafts. `LocalMaterialsReadOnlyAdapter` currently reports unavailable, timeout, and malformed responses as structured failures with no evidence. `summarize_materials_evidence` can preserve errors and warnings from multiple tool results, but no source/cache fallback path currently supplies labeled cached evidence. The README's project-phase summary is stale, and the existing Go/No-Go backout section is specific to the previous recommendation change.

## Goals / Non-Goals

**Goals:**
- Close the documented inventory-outage fallback gap without hiding the original failure or promoting stale data to current.
- Prove the established behavior through end-to-end deterministic tests and a requirement-to-evidence map.
- Keep security, audit, deployment, RAPID, and demonstration records accurate about what automation has and has not verified.

**Non-Goals:**
- Add a live airline, supplier, inventory, scheduling, or identity integration; make a production deployment; or add operational write capability.
- Change specialist reasoning, Controller ownership, compliance rules, score weights, close-score threshold, or human approval policy.
- Complete a human peer review, Go/No-Go decision, sponsor rehearsal, presentation, or Q&A on behalf of the team.

## Decisions

1. **Keep cache fallback at the Materials read boundary.** Add a typed fallback path around the existing read-only inventory adapter, not in Controller scoring or report generation. The ADK inventory tool builder accepts an optional, role-allowlisted cache adapter; when configured, source-unavailable or timeout outcomes query it, while default tool output remains the existing single result when no cache is configured. The fallback tool response is a versioned envelope with the primary structured error and separate cache result. Usable cache data is partial with original source, retrieval time, stale validity, and a `CACHED_EVIDENCE` warning. Pass both results through the existing degradation aggregation so warnings, error, evidence, and deterministic confidence penalty reach Maintenance/Controller. If no usable cache exists, retain the explicit failure. Do not mask malformed data, allowlist denial, or schema errors with cache. This reuses the existing `MaterialsToolResult` status invariants and avoids adding evidence to a failed result.

   **Alternative considered:** Return cache data as a normal successful inventory response. Rejected because it would erase the outage, misstate freshness, and risk a success-shaped result contrary to `ARD-RES-006`.

2. **Use one deterministic integration harness over existing boundaries.** Extend established pytest fixtures and Controller workflow ports to exercise the proposal's cases at the recommendation/report boundary; use fixed synthetic inputs, local adapters, fixed clocks, and no live model or network calls. Reuse component tests for agent-specific invariants and add cross-component assertions for the visible report, audit, and gate. Verify the inclusive two-point threshold and baseline weights without introducing a second scoring implementation.

   **Alternative considered:** Treat the existing component suite and historical command summaries as end-to-end proof. Rejected because they do not demonstrate propagation of cache degradation, evidence conflicts, and human selection through the completed Controller report.

3. **Keep security/audit checks at observable boundaries.** Reuse typed read-only adapter interfaces, role allowlists, untrusted-input validation, redacting audit serialization, and case-scoped events. Add negative tests for denied tools/writes, injection text, malformed data, secrets, append failures, and mismatched human decisions. Evidence records inputs, outputs, source references, rule outcomes, concise rationale, and recommendation version, never private chain-of-thought.

4. **Treat readiness documentation as evidence, not an approval mechanism.** Update the README to describe the implemented local/mock system and its limits. Keep the existing RAPID and Go/No-Go records as human-completed templates, revise their scope and evidence after implementation, and retain pending labels until named people supply review and decision outcomes. Add a deterministic demo runbook and a consolidated readiness verification record; do not synthesize reviewer identities, team decisions, or sponsor acceptance.

5. **Document local readiness, not nonexistent service health.** The project has local test and demo entry points rather than a deployed service. Define the readiness check as supported-environment/configuration validation plus focused and full deterministic test commands, and state that it does not prove live adapter connectivity, airworthiness, or production readiness. The optional model-backed Operations ADK entry point rejects a missing or template `GEMINI_API_KEY` before startup; it cannot validate provider authenticity without an authorized request. Add no dependency unless a demonstrated check cannot be implemented with existing tools.

## ARD Coverage

- `ARD-TST-001..009`, `ARD-RES-001..007`, `ARD-MLG-007`, `ARD-CTL-015..017`, `ARD-OPS-009`, and `ARD-GOV-004..008`: requirement-linked deterministic scenarios verify the functional cases, source/cache degradation, bounded failures, package impact, compliance-before-score, close-score human choice, conflicts, and approval deferral.
- `ARD-SEC-001..009`, `ARD-OBS-001..004`, `ARD-SYS-004`, and `ARD-PRN-008`: tests verify allowlisted read-only access, untrusted input and secret boundaries, correlated redacted audit, H3/H4 recording, and evidence-based explanation without private reasoning.
- `ARD-DEP-001..006`, `ARD-CAP-001..003`, `ARD-RUB-001..011`, and `ARD-TEC-019..020`: docs and retained results map capabilities to behavior, expose gaps, document setup/health/backout, and prepare human-owned review and sponsor activities. Automation does not substitute for peer review, Go/No-Go, or sponsor communication.
- `ARD-CTL-011..014/019` and `ARD-SYS-005`: existing deterministic ranking and Controller ownership are verified as-is; this change does not alter policy.

No ARD deviation is proposed. Any unmet readiness criterion remains a visible finding or explicit human deferral; test success is not operational or airworthiness approval.

## Risks / Trade-offs

- **Stale cache appears current downstream** → Preserve the primary failure and cached retrieval time, validity, warning, and confidence reduction through the full report and audit path.
- **Broad end-to-end fixtures become brittle** → Keep them at the Controller boundary, reuse existing synthetic factories, and keep domain-specific edge assertions in the current unit/contract suites.
- **Automated evidence is mistaken for approval** → Keep reviewer/team/sponsor fields pending and label local mock results as non-production evidence.
- **Security tooling is unavailable or reports findings** → Record the tool and result or the precise gap; do not claim security readiness from dependency installation alone.

## Migration Plan

No data migration or runtime rollout is required. Implement the cache fallback and integrated tests additively; preserve the current failure-only path when no cache is configured. Update docs and evidence after the final verification run. If a regression appears, disable the fallback/readiness entry point and return to the prior structured advisory handoff; retain source failures and audit evidence, and rerun focused Controller/Materials tests plus the repository verification gates before re-enabling.
