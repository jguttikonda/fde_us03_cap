# Go/No-Go Checklist

**Change:** `rank-aog-recovery-recommendations`  
**Record status:** Draft; team decision pending  
**Decision owner(s):** Pending team entry  
**Decision date:** Pending team review

## Readiness Evidence

| Check | Evidence | Status |
|---|---|---|
| Requirements and traceability documented | Proposal, `recovery-recommendations`, `recovery-orchestration`, and `controller-runtime-integration` deltas; ARD mapping in `docs/controller-orchestration-verification.md` | Complete for this implementation |
| Contracts and behavior tests | Versioned report, scoring/ranking, candidate sourcing, compliance, human gate, audit, and ADK tests | Complete; see test summary below |
| Test results retained | `uv run pytest --cov=aog_recovery --cov-report=term` | 463 passed; 93% total coverage |
| Lint and format | `uv run ruff check .`; `uv run ruff format --check .` | Passed; 202 files formatted |
| Type checks | `uv run mypy src` | Passed; 67 source files |
| OpenSpec validation | `openspec validate --changes "rank-aog-recovery-recommendations" --strict` | Passed |
| Code review complete | Qualified peer review and final RAPID recommendation in `docs/rapid-peer-review.md` | Pending human review |
| Security/readiness review | InfoSec, Reference Architecture, secret scanning, Bandit, and dependency-audit review | Not completed by this change; reviewer/team to record outcome |
| Sponsor demonstration | Human-led demonstration and live Q&A | Pending; no sponsor acceptance claimed |
| Operational approval | Ops lead and Maintenance/airworthiness authority approval for any operational recommendation | Always required; no operational action is executed by this system |

## Outstanding Issues and Conditions

- A qualified reviewer must complete the six Code Work Product criteria using the applicable RAPID peer-review prompt, identify themselves, and record findings and the final review recommendation.
- The team must review the Go/No-Go evidence, unresolved security findings, backout readiness, and demonstration plan before assigning a decision.
- Two dependency warnings remain in the full test run: the Google GenAI deprecated alias and Google ADK experimental `PLUGGABLE_AUTH` warning.
- Relative scores are case-specific decision aids, not probabilities or compliance results. Missing required score inputs remain unscored; stale/conflicting evidence may escalate.
- The score is advisory only. Both required human roles must approve the same option and recommendation version before any operational action; this project does not execute that action.

## Backout Plan

1. Disable the recommendation-stage invocation in `ControllerWorkflow.run` and retain the existing validated `UnrankedHandoff` response.
2. Return an explicit structured capability-unavailable or partial status; do not synthesize a ranked report or imply that recommendation processing succeeded.
3. Keep the read-only specialist integrations, evidence, and compliance exclusions intact. Do not add or invoke operational write adapters during rollback.
4. Run the focused Controller contract, compliance, workflow, ADK, and audit tests, then Ruff, mypy, formatting, and strict OpenSpec validation; retain the rollback results and update the evidence map.
5. Re-enable ranked recommendations only after the regression is corrected and the same human-review and verification gates pass.

## Team Decision

**Go/No-Go:** Pending team review.  
**Rationale:** Automated verification is recorded above, but it does not replace qualified peer review, InfoSec/Reference Architecture review, sponsor communication, or the team's evidence-backed Go/No-Go decision.  
**Decision owner(s), conditions, and date:** To be completed by the team.
