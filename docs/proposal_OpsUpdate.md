# Operations Agent Remediation Proposal

**Status:** Draft for review
**Scope:** Corrective planning for the Operations impact-analysis capability
**Implementation status:** Not implemented by this proposal

## Summary

The Operations implementation has a passing automated baseline, but direct
input/output retesting found three gaps between observed behavior and the
Operations requirements:

1. Evidence timestamps are not checked against the configured source-freshness
   limit, and contradictory values are not detected when both records are
   labeled `CURRENT`.
2. Candidate assessments reuse the request-wide affected-flight list, so swap,
   repair, and delay options can report the same flight impacts even when their
   schedules and recovery times differ.
3. Adapter request parameters and response data are generic dictionaries and
   are not validated against tool-specific payload schemas.

This proposal adds deterministic, regression-tested behavior for those cases.
It does not replace the Operations Agent or expand it into Controller
orchestration.

## Retest evidence and problem statement

The retest against [the Operations proposal](./agent-proposals/operations-agent-proposal.md),
[the system proposal](./proposal.md), [the Operations prompt](./openspec-proposal-prompts.md),
and the existing
[Operations OpenSpec specification](../openspec/changes/implement-operations-impact-analysis/specs/operations-impact-analysis/spec.md)
reported:

- `pytest`: **138 passed**; no automated test failures.
- Ruff check, Ruff format check, mypy, and strict OpenSpec validation: **passed**.
- Direct behavioral probes: **not fully conformant**. A 90-day-old record marked
  `CURRENT` and a contradictory current record produced a complete assessment
  with no conflict or missing-evidence indication. In a three-flight probe,
  swap, repair, and delay assessments all returned the same affected flights.
- Contract review: adapter `parameters` and returned `data` use generic
  dictionaries, so arbitrary invalid per-tool payload shapes are not rejected
  at the adapter boundary.

The green automated baseline therefore does not establish the required
timestamp, cross-source conflict, option-specific impact, or tool-payload
behavior. The corrective work must add explicit tests for those behaviors
rather than treating lint, typing, or the existing suite as a proxy.

## Problem and value

Stale or contradictory operational evidence can currently appear complete and
reliable. Reusing a case-wide flight list can also make materially different
recovery options look operationally identical. Finally, weak adapter payload
contracts allow malformed or unexpected data to reach deterministic analysis.

The proposed change makes these conditions visible at the boundary and in each
option result. This improves Controller aggregation and human review without
claiming that an option has been executed or approved.

## Proposed change

### 1. Enforce timestamp-based freshness and detect conflicts

- Wire the typed `operations_source_freshness_seconds` setting into evidence
  evaluation; do not leave the configured threshold unused.
- Evaluate age from an injected or otherwise deterministic UTC clock and the
  evidence `observed_at` value. When age exceeds the configured threshold,
  classify the evidence as stale even if its provider-supplied state says
  `CURRENT`.
- Preserve provider-supplied state and provenance. A disagreement between the
  provider label and timestamp-derived state must be surfaced; never upgrade
  stale, partial, or unavailable evidence based only on a fresh timestamp.
- Reject or explicitly mark invalid timestamps that are missing where
  required, timezone-naive, or implausibly in the future; do not silently use
  the local clock or a business-value default.
- Compare normalized claims about the same subject and attribute across
  overlapping validity periods. Detect materially different values even when
  each source labels its own record `CURRENT`. Retain both values, sources,
  observation times, and the affected claims in the conflict record.
- Apply freshness and conflict outcomes to the affected option conclusions:
  list stale/missing evidence, lower confidence or mark the result partial or
  provisional as appropriate, and emit a structured conflict/escalation
  marker that requires Controller/human adjudication for material conflicts
  regardless of numeric confidence. Operations does not implement or perform
  approval.

### 2. Calculate affected flights separately for every candidate

- Derive each candidate's affected flights from that candidate's action,
  recovery availability time or delay, aircraft assignment, and the relevant
  schedule evidence. Do not use the request-wide list as the answer for every
  option.
- Keep the request-wide flight list as the set of flights to consider, not as
  a precomputed impact result.
- Base inclusion and exclusion on deterministic time-window and assignment
  rules. Preserve the evidence references for each result. If required timing
  or assignment evidence is unavailable, identify the missing input and leave
  the impact provisional rather than assuming a flight is unaffected.
- Use the Operations proposal's FX123 example as a regression oracle:
  - Swap to FX207: FX401 only; 1,200 packages affected; 180 priority packages
    at risk, with the stated short-delay assumption.
  - Repair with a 9-hour ETA: FX401 and FX812; 2,100 packages affected; 320
    priority packages at risk.
  - Delay by 27 hours: FX401, FX812, and FX955; 2,800 packages affected; 380
    priority packages at risk.
- Keep package redistribution and per-option cost tied to the corresponding
  candidate's flight set. A package count or cost unavailable for an option
  remains visibly unavailable; it is not treated as zero.

### 3. Validate tool-specific request and response payloads

- Define versioned Pydantic request and response models for each allowlisted
  Operations tool, including the fields and constraints required by that
  tool's schedule, route, fleet/assignment, crew/station, customer, disruption,
  and package data.
- Use a tool-name-discriminated typed contract (or equivalent explicit typed
  dispatch) instead of relying on `dict[str, object]` as the validation
  boundary. Forbid unexpected fields unless a documented compatibility rule
  requires them.
- Validate adapter inputs before dispatch and adapter results before analysis.
  Preserve source, `observed_at`, evidence state, schema version, and
  correlation identifiers.
- Convert malformed tool responses into structured, tool-specific failures.
  Identify which analysis is unavailable, retain unaffected supported
  conclusions as partial where possible, and lower confidence or escalate
  according to policy. Do not return malformed data as a success-shaped
  response.

### 4. Preserve existing domain and governance boundaries

- Continue to provide an Operations assessment for Controller aggregation;
  do not add cross-agent orchestration, compliance gating, system-wide
  scoring/ranking, or final report generation.
- Keep all tools read-only and allowlisted. Do not perform a swap, dispatch,
  schedule change, booking, package transfer, or approval action.
- Keep source-backed evidence, assumptions, warnings, unknowns, and
  recommendation rationale distinct in the structured result.
- Continue to require authorized human approval for every operational
  decision. Confidence and degraded status never bypass approval.
- Do not make airworthiness or regulatory-approval claims.

## Scope

### In scope

- Timestamp-derived evidence freshness using typed settings.
- Detection and provenance of materially contradictory evidence, including
  records provider-labeled `CURRENT`.
- Candidate-specific flight, route, package, and cost impacts.
- Strict, versioned tool-specific request/response validation.
- Structured malformed-payload and stale/conflict failure paths.
- Deterministic unit, contract, and agent regression tests, with retained
  verification evidence.

### Out of scope

- Controller orchestration, compliance-gate ownership, option scoring or
  ranking, and final decision-brief generation.
- Live airline-system integration or write-enabled adapters.
- Automatically approving or executing any operational option.
- Changing the shared human approval policy or Operations' domain ownership.
- Treating mock estimates, tests, or framework setup as operational evidence
  or human sign-off.

## Acceptance criteria

The change is acceptable only when all of the following are demonstrated:

1. **Freshness is wired and deterministic.** With a fixed UTC clock and a
   configured 900-second threshold, evidence observed 901 seconds earlier is
   marked stale, listed in the result, and affects status/confidence; evidence
   exactly 900 seconds old follows a documented boundary rule. A record
   provider-labeled `CURRENT` but older than the threshold is not treated as
   current.
2. **Conflicts are derived from claim values.** Two current records from
   distinct sources for the same subject/attribute with incompatible values
   produce a conflict containing both evidence references, values, sources,
   and times. Unrelated subjects or compatible values do not create a false
   conflict.
3. **Conflict cannot be hidden by confidence.** A material conflict makes the
   affected result provisional or escalated and emits a structured marker for
   the Controller to defer approval, even when input confidence is at least
   0.70. Missing and stale evidence is listed, not replaced by an assumption.
4. **Each candidate gets its own flight set.** The FX123 fixture produces the
   three distinct expected sets and package/priority totals above. The
   assessments retain each option's evidence and assumptions. Missing
   candidate timing does not silently reuse the request-wide set as a proven
   impact.
5. **Cost follows candidate impact.** Delay, swap, and unprotected-package
   cost line items use their own candidate-specific inputs. Missing cost
   evidence is represented as unavailable, not zero.
6. **Tool payloads are validated at both boundaries.** Valid fixtures pass;
   missing required fields, invalid field types/enums, and forbidden extra
   fields fail validation. A malformed response produces a structured failure
   and partial/degraded result where supported.
7. **Existing behavior remains covered.** Existing feasible-swap,
   assignment-conflict, package capacity/cut-off, timeout, and security tests
   continue to pass.
8. **Governance and reproducibility hold.** No operational write/action is
   introduced; no confidence or test/degraded mode bypasses human review; tests
   use deterministic local fixtures and no live operations systems or model
   calls. Verification commands and outcomes are retained in a repository
   evidence artifact.

## Required regression test matrix

| ID | Input | Expected observable output |
|---|---|---|
| FRESH-01 | Fixed UTC clock; 900-second threshold; current-labeled evidence observed 901 seconds ago | Evidence is stale, listed by ID/source/claim, and affects status or confidence |
| FRESH-02 | Evidence observed exactly at the freshness boundary | Result follows the documented inclusive/exclusive boundary deterministically |
| FRESH-03 | Provider state says stale but timestamp is recent | Evidence remains degraded; a recent timestamp does not silently upgrade it |
| FRESH-04 | Missing, naive, or invalid/future observation time | Contract rejection or explicit structured degraded state; no silent timestamp default |
| CONFLICT-01 | Same claim, overlapping interval, two `CURRENT` sources with different route/assignment values | Conflict names both values and provenance; affected option is provisional/escalated and emits a Controller-consumable human-adjudication marker |
| CONFLICT-02 | Same claim with equivalent normalized values, or different subjects | No false conflict |
| OPTION-01 | FX123 swap, repair, and delay fixture described above | Distinct flight sets and exact package/priority counts per candidate |
| OPTION-02 | Candidate has no recovery ETA or required schedule evidence | Missing evidence is listed; result does not claim an unsupported affected-flight set |
| OPTION-03 | Candidate-specific redistribution/cost data differs | Each option's protected/unprotected package counts and cost reflect only its own candidate |
| CONTRACT-01 | Valid request and response fixture for each allowlisted tool | Parsed into the corresponding typed model; provenance and correlation preserved |
| CONTRACT-02 | Invalid type, missing required field, unknown enum, and unexpected field per tool | Rejected at the boundary and reported as structured adapter failure |
| CONTRACT-03 | Malformed response from one tool while another result is valid | Failed analysis is named; supported independent findings remain partial, never success-shaped |
| GOVERN-01 | Conflict with confidence >= 0.70; missing evidence at each confidence band | Human approval remains mandatory; conflict marker requires Controller/human adjudication; thresholds and missing list are visible |
| REGRESSION-01 | Existing swap, assignment conflict, cut-off, timeout, allowlist, read-only, and redaction fixtures | Prior supported behavior continues to pass |

Tests should assert structured fields, not only status labels or prose: evidence
IDs and timestamps, conflict references, option IDs, affected flight IDs,
package counts by service level, cost availability, structured error category,
confidence/status, and approval-deferred indicators.

## Implementation work packages

1. **Contracts and policy:** Define or refine typed tool payloads and freshness
   normalization. Cite ARD-DAT-001/004/007/008/009/010 and
   ARD-OPS-006. Include valid, invalid, boundary, and structured-error tests.
2. **Evidence evaluation:** Inject the configured freshness policy and a
   deterministic clock; derive conflicts on normalized claim keys and retain
   provenance. Cite ARD-PRN-005/006, ARD-DAT-004/005, ARD-GOV-004/005, and
   ARD-TST-003.
3. **Candidate impact:** Compute flight impact separately per recovery option
   and flow it into package redistribution, customer impact, and cost. Cite
   ARD-OPS-001..005/007/009 and ARD-TST-006.
4. **Degraded paths and governance:** Ensure stale, conflict, malformed, and
   unavailable evidence remains explicit; preserve mandatory human review and
   read-only boundaries. Cite ARD-RES-002..006, ARD-GOV-001..008,
   ARD-SEC-001..009, and ARD-TST-005/007.
5. **Regression evidence:** Run focused and full deterministic tests, type and
   lint checks, and OpenSpec validation; record exact commands, results, and
   remaining human-review/RAPID/sponsor-demonstration status. Cite
   ARD-TST-001/008/009 and ARD-TEC-008/009/017/019/020.

## ARD Traceability

This standalone proposal introduces no ARD deviation. The IDs below identify
the requirements the follow-up implementation must address or preserve; they
are not a claim that this proposal itself satisfies them.

### Addressed by the proposed remediation

| ARD IDs | Rationale |
|---|---|
| ARD-OPS-001..009 | Strengthens evidence-based operations inputs, deterministic per-option assessment, explicit conflict/route impact, package redistribution, and structured outputs. |
| ARD-PRN-003/005/006/007 | Makes freshness, comparisons, typed boundaries, and degradation deterministic and visible. |
| ARD-DAT-001/003/004/005/007..010 | Requires validated versioned tool schemas, provenance, freshness, fact/assumption separation, and structured failures. |
| ARD-GOV-001..005/008 | Keeps confidence thresholds, missing-data visibility, conflict deferral, and mandatory approval enforcement. |
| ARD-RES-002..006 | Requires timeout/malformed-data failures, partial conclusions, bounded-safe behavior, and no silent fallback. |
| ARD-SEC-001..009 | Preserves least privilege, read-only allowlisting, untrusted-input validation, redaction, safety-claim limits, and auditability. |
| ARD-TST-001..003/005..009 | Adds traceable regression, contract, agent, governance, security, deterministic, and retained-evidence tests. |
| ARD-TEC-003/004/008/009/017/019/020 | Uses Pydantic and typed settings, project test/quality checks, and reviewable evidence without conflating tooling with behavior. |

### Deferred

| ARD IDs | Rationale |
|---|---|
| ARD-GOV-006/007 | The follow-up remains the Operations capability and does not implement the system approval workflow or approval record. It must still provide a result suitable for that downstream workflow. |
| ARD-OPS-005 recommendation rationale beyond affected-impact correction | Existing recommendation behavior is not being redesigned here; the correction is limited to evidence integrity, candidate-specific impact, and adapter contracts. |
| ARD-TEC-019/020 human review, RAPID/Go-No-Go, and sponsor demonstration evidence | These remain human-owned readiness activities and cannot be asserted by implementation tests. |

### Out of scope

| ARD IDs / area | Rationale |
|---|---|
| ARD-CTL scoring, compliance gating, Controller orchestration, and final report generation | Explicitly outside the Operations Agent boundary and not part of this corrective scope. |
| ARD-GOV-006/007 implementation | Approval actions and approval-record workflow belong to the system governance/Controller capability; Operations must not approve or execute. |
| Live external operations integration | The remediation is verified with deterministic local/mock adapters; live integration needs its own approved scope and governance. |

## Rubric and Capability Coverage

| Rubric/capability | Proposed evidence and verification | Human responsibility |
|---|---|---|
| Capstone Category 1: Agent functionality and correctness; Operations capability: evidence freshness and conflict handling | FRESH and CONFLICT cases assert normalized freshness, source provenance, visible conflicts, and degraded status | Reviewer confirms policy matches operational context; humans adjudicate conflicts |
| Capstone Category 1: Agent functionality and correctness; Operations capability: candidate impact | OPTION cases assert distinct FX401/FX812/FX955 outcomes and candidate-specific package/cost results | Operations lead evaluates operational trade-offs; no automated action |
| Capstone Category 2: Spec-driven design quality | Follow-up OpenSpec delta should map requirements/scenarios/tasks to the ARD IDs above and this proposal's test matrix | Peer reviewer checks traceability and scope boundaries |
| Capstone Category 3: Engineering quality | Tool contract tests, deterministic unit/agent tests, Ruff, mypy, full pytest, and OpenSpec validation are retained | Human reviewer evaluates evidence and unresolved limitations |
| Capstone Category 5: AI-assisted development practice | Retain reviewable change artifacts and AI-assistance evidence per repository practice; do not treat tool use as approval | Human peer review and project evidence owner complete records |
| Capstone Category 6: Demonstration and communication | Run the FX123 mock scenarios and communicate stale/conflicting/malformed-data limitations in the demo evidence | Sponsor demonstration and Go/No-Go remain human-owned |
| Advisory-only and approval capability | Tests verify no write adapter/action and that conflict, high confidence, timeout, or test mode cannot bypass approval | Authorized humans decide approve, reject, escalate, or request more information under the system workflow |

## Verification plan

After the follow-up is implemented, run the focused Operations tests for the
new freshness, conflict, option-impact, and adapter-contract cases, then the
full configured pytest, Ruff check/format, type check, and strict OpenSpec
validation. Retain exact command output and record failures or deferrals.
Human review, RAPID/Go-No-Go, sponsor demonstration, and any operational
approval must be recorded separately; passing automated checks is not their
substitute.

## Source references

- [Operations prompt and expected scope](./openspec-proposal-prompts.md)
- [System proposal](./proposal.md)
- [Operations Agent proposal and mock scenarios](./agent-proposals/operations-agent-proposal.md)
- [ARD](./architecture-requirements.md)
- [Existing Operations OpenSpec delta](../openspec/changes/implement-operations-impact-analysis/specs/operations-impact-analysis/spec.md)
- [Operations agent implementation](../src/aog_recovery/operations/agent.py)
- [Operations tool and domain contracts](../src/aog_recovery/operations/contracts.py)
- [Typed settings](../src/aog_recovery/config.py)
- [Operations agent tests](../tests/operations/test_agent.py)
- [Operations verification record](./operations-impact-analysis-verification.md)
- [Operations readiness record](./operations-impact-analysis-readiness.md)
