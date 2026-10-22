# Tasks

## 1. Recommendation contracts and deterministic scoring

- [x] 1.1 Define versioned typed contracts for candidate score factors, ranked options, exclusions, decision brief, and recommendation version; add valid/invalid contract tests for required fields, evidence references, score bounds, and USD cost (`recovery-recommendations`, ARD-DAT-001/004..006/010..012, ARD-CTL-013..016).
- [x] 1.2 Expand candidate construction to create one stable variant per sourcing offer, narrow M&L inputs to the selected offer, and derive repair readiness from the later of repair and source ETAs with both evidence trails; test missing ETA behavior and update candidate requirement-to-test traceability (ARD-CTL-018, ARD-DAT-004/009, ARD-GOV-005, ARD-TST-001..003/009).
- [x] 1.3 Implement the fixed 30/30/30/10 factor normalization and USD cost aggregation from Maintenance, Materials & Logistics, and Operations fields; add unit tests for individual mappings, missing/unknown values, single/equal candidates, ties, exact weights, cost-driven ordering, reproducibility, and no double-counting (ARD-CTL-011..014/019, ARD-TST-004/009).
- [x] 1.4 Implement deterministic ordering and the inclusive 2.0-point close-score group without asserting a unique winner; add boundary tests at exactly 2.0 points, just over 2.0, ties, and one scoreable option, and update traceability (ARD-CTL-014..015, ARD-TST-001/004).

## 2. Compliance-first report workflow

- [x] 2.1 Compose the recommendation stage after the existing compliant unranked handoff; test that engineering approval and part authorization/compatibility/traceability failures are listed with reasons and never scored or ranked (ARD-CTL-009/017..018, ARD-TST-004/006).
- [x] 2.2 Assemble the decision brief with evidence references, score factors, trade-offs, assumptions, risks, warnings, missing data, and confidence; add workflow tests for repair, preferred/alternate sourcing, swap, delay, package redistribution, and cost trade-offs (ARD-CTL-013..016/018..019, ARD-OPS-009, ARD-TST-001/006/009).
- [x] 2.3 Keep partial, stale, unavailable, failed, and conflicting evidence visible; test provisional status, escalation, unscored candidates, zero scoreable options, and structured audit/workflow failures without success-shaped output (ARD-CTL-008/010/016, ARD-GOV-002..005, ARD-RES-001..006, ARD-TST-003/006/008..009).
- [x] 2.4 Make the report summary identify its leading option or close-score group and assert report-level human selection; assert all-excluded reports escalate while preserving exclusion reasons (ARD-CTL-015..017, ARD-CTL-016, ARD-TST-004/006).

## 3. Human decision gate and audit

- [x] 3.1 Validate typed approve, reject, escalate, and request-information records against case, option, reviewer role, timezone-aware timestamp, rationale, and active recommendation version; add contract tests for invalid, stale, and mismatched decisions (ARD-GOV-006..007, ARD-DAT-010..011, ARD-TST-002/005).
- [x] 3.2 Require matching Ops lead and Maintenance/airworthiness approvals for the same option and recommendation version; add gate tests for both approvals, either approval missing, conflicting selections, and all confidence levels, and verify no decision invokes operational actions (ARD-GOV-001..008, ARD-PRN-001..002, ARD-TST-005).
- [x] 3.3 Append case-correlated recommendation, exclusion, escalation, and human-decision audit events; test recommendation-version linkage, append failure, case isolation, and absence of private reasoning or sensitive source content (ARD-PRN-008, ARD-OBS-001..004, ARD-SEC-007/009, ARD-RES-003..007, ARD-TST-007..009).
- [x] 3.4 Set the report's terminal status to `resolved` only after both required roles approve the same active option and report version; test that approval changes status but never executes an operational action (ARD-CTL-010, ARD-GOV-006..008, ARD-TST-005).

## 4. Runtime integration and traceability

- [x] 4.1 Expose the versioned decision brief and human-gate state in the typed ADK workflow response while preserving the unranked handoff for diagnostics; add runtime contract tests for completed, partial, and structured-failure responses with no operational action capability (controller-runtime-integration, ARD-TEC-002/005, ARD-CTL-010/016..018, ARD-SEC-001..003, ARD-TST-002/005/007).
- [x] 4.2 Update the capability requirement-to-test mapping and implementation evidence with links to the scoring, contract, workflow, human-gate, audit, and runtime tests; verify every addressed ARD is covered or explicitly deferred (ARD-TST-001/008, ARD-TEC-019).

## 5. Integrated verification and delivery evidence

- [x] 5.1 Run the focused Controller contract, scoring, compliance, workflow, and ADK integration tests plus Ruff and strict OpenSpec validation; retain results and resolve any new regressions without weakening the human gate (ARD-TST-001..009, ARD-TEC-008/017, ARD-NFR-001..002).
- [x] 5.2 Retain AI-assisted development evidence and prepare the RAPID peer-review/Go-No-Go record; mark sponsor demonstration evidence pending until the human-led demonstration is completed, and do not treat test success or framework setup as approval evidence (ARD-TEC-019..020).
