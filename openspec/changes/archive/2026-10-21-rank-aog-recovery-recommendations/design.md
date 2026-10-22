# Design

## Context

See proposal.md for motivation. The existing Controller builds stable candidates, evaluates Maintenance and Materials & Logistics concurrently per repair candidate, then evaluates Operations per candidate and returns `UnrankedHandoff`. The compliance gate already preserves exclusion reasons and a pending human gate. `HumanDecisionRecord` already captures case, action, selected option, reviewer, timestamp, rationale, and recommendation version, but the current workflow does not construct a ranked report or bind decisions to one. Operations `CostBreakdown.total_usd` includes delay, swap, rerouting, and unprotected-package costs; Maintenance and Materials & Logistics provide repair-labor and sourcing costs separately.

## Goals / Non-Goals

**Goals:**

- Compose a Controller-owned recommendation stage after validated specialist aggregation and compliance screening.
- Define reproducible, inspectable factor scoring and cost aggregation without LLM arithmetic.
- Return a versioned, typed decision brief while keeping missing or conflicting evidence explicit.
- Record human decisions against the exact recommendation version and enforce the requested dual-approval boundary.
- Keep the ADK response advisory and free of operational execution capabilities.

**Non-Goals:**

- Changing specialist reasoning, the Maintenance/Materials & Logistics handshake, or Operations allocation policy.
- Adding a Recommendation/Report agent, live enterprise adapters, approval automation, or operational write tools.
- Treating recommendation approval as execution or proof that a repair, swap, delay, order, booking, or transfer occurred.

## Decisions

### 1. Keep candidate evaluation and recommendation as separate Controller stages

Consume the existing unranked handoff as an internal input to a new Controller-owned recommendation capability. Preserve candidate-specific evidence and results. Expand repair candidates into distinct candidate variants for each sourcing path rather than allowing a candidate with multiple sourcing options to silently use only its first source. Narrow the typed M&L assessment to the selected offer. For repair, derive the Operations readiness ETA as the later of the Maintenance readiness ETA and selected source ETA; retain both evidence-reference sets and mark the combined estimate estimated. If either required ETA is missing, leave readiness absent and report the candidate unscored instead of treating the other ETA as complete. Include candidate kind, part/source identity, sourcing method, combined readiness, and load plan in stable candidate identity. This preserves the specialist boundary and keeps ranking authority in the Controller. (ARD-SYS-002/005, ARD-CTL-009/018, ARD-DAT-004..005, ARD-GOV-005)

**Alternative considered:** Put ranking into Operations or add a Recommendation Agent. Rejected because Operations owns only operational analysis and the ARD assigns ranking, explanation, and report ownership to the Controller; a fifth agent is not allowed. (ARD-SYS-001/003/005)

### 2. Gate before score; treat compliance and scoreability separately

Run the existing deterministic repair compliance checks before any score calculation. Keep failed or missing approval, compatibility, authorization, or traceability as an excluded candidate with reasons and no score. A compliant candidate with incomplete numeric scoring evidence is not a compliance exclusion: label it unscored, expose missing inputs, lower confidence or escalate, and never substitute a favorable default. Operations candidates marked not viable are not ranked; undetermined viability remains visible and unscored. (ARD-CTL-017, ARD-GOV-004..005, ARD-RES-004..006)

### 3. Use explicit deterministic factor normalization

Represent each factor and aggregate score on a 0-100 higher-is-better scale. Compute the aggregate as `0.30 * speed + 0.30 * impact + 0.30 * risk + 0.10 * cost`. Scores are case-relative decision aids, not probabilities, compliance evidence, or approval.

- **Speed:** derive elapsed minutes from case creation to candidate readiness ETA. Normalize against the minimum and maximum scoreable candidate elapsed times in the case: fastest is 100 and slowest is 0; when all values are equal, all receive 100.
- **Operational/package impact:** map Operations impact levels `low/medium/high/critical` to `100/66.67/33.33/0`. Compute package protection as `100 * (1 - (2 * unprotected_time_critical + unprotected_standard) / (2 * time_critical + standard))`, where standard counts are total affected minus time-critical. Average the impact-level and package-protection values. Missing or inconsistent counts make the factor unscorable rather than assumed zero impact.
- **Risk:** map each of the three structured Maintenance risk metrics `low/medium/high` to `100/50/0` and take their arithmetic mean. `unknown` makes the factor unscorable. Preserve Operations risk flags and specialist conflicts in the report even though free-text flags are not converted into hidden numeric adjustments.
- **Cost:** sum Maintenance repair-labor USD where repair is required, the selected Materials & Logistics sourcing USD where sourcing is required, and Operations `total_usd` (which already contains delay, swap, rerouting, and unprotected-package components). A non-required component is zero by candidate type; a required missing or incomplete component makes the candidate unscorable. Normalize eligible complete costs case-relatively: cheapest is 100, most expensive is 0, and equal costs receive 100.

Keep full precision for ranking and the 2-point comparison; round only displayed values to two decimals. Sort deterministically by aggregate score descending and stable candidate ID ascending. Candidates whose unrounded top scores differ by no more than 2.0 points form a human-selection group; stable display order MUST NOT imply a unique preferred option. Record the scoring algorithm version and applied weights. (ARD-CTL-011..015/019)

**Alternative considered:** Use an LLM to assess factor weights or calculate scores. Rejected because calculations and exclusions must be deterministic, repeatable, and independently testable; bounded language generation may only explain already-computed fields. (ARD-PRN-003..004, ARD-CTL-012..013)

### 4. Build a typed, versioned report from source-backed fields

Introduce a report contract containing case ID, recommendation version, workflow/decision status, candidate outcomes, exclusions, score factors and weights, total USD cost, evidence references, assumptions, risks, warnings, conflicts, missing data, confidence, close-score selection requirement, and required human action. Use deterministic templates over validated values for summaries and trade-offs; identify the leading option or close-score selection group and its material trade-off without asking a model to invent fields or change the ranking. Derive recommendation version from a canonical fingerprint of the case inputs, validated specialist outputs, evidence references, and scoring algorithm version so a decision against an older report is detectable. (ARD-DAT-004..006/010..012, ARD-CTL-013..016)

Keep the existing unranked handoff available as internal diagnostic context and add the report to the runtime result. This is an additive runtime field; the report has its own schema version. An incomplete workflow may return the validated handoff and structured errors without a recommendation report, but MUST NOT return a fabricated successful report. (ARD-TEC-002/005, ARD-DAT-008..010, ARD-RES-003..006)

### 5. Preserve confidence posture and terminal workflow outcomes

Carry forward the conservative Controller confidence assessment; scoring MUST NOT raise confidence. Confidence at or above 0.70 may identify a preferred path, 0.50-0.69 is provisional, and below 0.50 or material conflict is escalation-required with approval deferred. With no scoreable option, return exclusions and missing-data details with escalation or awaiting-additional-data status. A human rejection, escalation, information request, or completed dual approval maps to the required terminal workflow status. `resolved` means both approvals are recorded for the active report and the human decision is complete, not that an operational action was performed. (ARD-CTL-008/010/016, ARD-GOV-001..005)

### 6. Require two human approvals and append decision records

Accept decisions only through a typed human-decision boundary; the model cannot author a reviewer identity or decision. Retain the existing `HumanDecisionRecord` fields and validate case ID, active recommendation version, selected option, reviewer role, timezone-aware timestamp, and rationale. For approval, require matching records from both Ops lead and Maintenance/airworthiness authority for the same option and version, as requested. Rejection, escalation, and request-more-information remain supported actions; they do not trigger operations. Append each decision and its audit event; stale or mismatched decisions remain visible and cannot satisfy the gate. (ARD-GOV-006..008, ARD-PRN-001..002/008, ARD-OBS-001..004)

**Alternative considered:** Treat a high score or one approver as sufficient. Rejected because the user requires dual approval and the ARD prohibits every confidence, test, or degraded-mode bypass. The additional approver for non-repair recommendations is intentionally stricter than the minimum condition in ARD-GOV-006 and does not weaken any requirement.

### 7. Make persistence and failures explicit

Emit case-correlated audit events for scoring, each exclusion, report generation, escalation, and human decision. Store concise rationale, status, timestamp, recommendation version, and evidence references; never store private chain-of-thought or sensitive source payloads. An append failure makes the corresponding workflow incomplete or failed and prevents a claim of auditable completion. Keep all adapters read-only/allowlisted; the human gate changes decision state only and has no connection to operational command adapters. (ARD-PRN-008, ARD-OBS-001..004, ARD-SEC-002..003/007..009, ARD-RES-003..007)

## Risks / Trade-offs

- [Relative normalization depends on the candidate set] → Label scores as case-relative, show raw ETA and USD amounts, preserve factor values and algorithm version, and never present score as confidence.
- [Missing cost or risk evidence can leave a candidate unranked] → Show the exact missing component and keep the candidate visible; escalate or request information rather than infer a value.
- [Stricter dual approval may increase time to decision] → Make both required roles and their outstanding decisions visible in the report and gate state.
- [Adding a report field changes runtime behavior] → Keep the current unranked handoff in the result for diagnostics and introduce the report as a separately versioned additive contract.
- [Audit persistence outage can block completion] → Return a structured incomplete/error result and preserve the failure; do not report a completed decision without the audit record.

## Migration Plan

1. Add the versioned recommendation contract and deterministic scoring/report stage behind the existing unranked handoff.
2. Add the report field to the runtime result while retaining the existing handoff; update ADK contract and consumers to recognize recommendation status and schema version.
3. Deploy tests and local/mock integration first. No live data migration or operational adapter is required.
4. Roll back by disabling the recommendation stage and returning the existing unranked handoff with a structured capability-unavailable status; do not substitute a success-shaped report.

## ARD Coverage

- `ARD-CTL-009..019`: Controller owns recommendation, workflow completion, deterministic 30/30/30/10 scoring, factor transparency, ranked alternatives, close-score handling, brief, gate-before-score, candidate inputs, and total USD cost.
- `ARD-SYS-002/005..006`, `ARD-DAT-004..006/010..012`: Controller ownership, no separate agent, human decision ownership, evidence/assumption separation, versioned typed contracts, decision status, and option model.
- `ARD-GOV-001..008`, `ARD-PRN-001..008`: confidence, conflict, missing-data, dual human decisions, approval non-bypass, evidence grounding, deterministic boundaries, and traceability.
- `ARD-OPS-009`, `ARD-RES-001..007`: package impact, visible degraded evidence, structured failures, audit persistence, and case isolation.
- `ARD-SEC-002..003/007..009`, `ARD-OBS-001..004`: read-only allowlisted boundary and reconstructable, non-sensitive audit events.
- `ARD-TST-001..009`, `ARD-TEC-002/005`, `ARD-NFR-001..002`: traceable deterministic contract/workflow tests, bounded integrations, and regressions.

## Deviations

None. The dual-approval rule is stricter than the minimum ARD condition for non-repair options, per the explicit request; the advisory-only and no-execution requirements remain unchanged.
