# Go/No-Go Checklist

**Change:** `validate-aog-recovery-readiness`
**Record status:** Draft; team decision pending  
**Decision owner(s):** Pending team entry  
**Decision date:** Pending team review

## Readiness Evidence

| Check | Evidence | Status |
|---|---|---|
| ARD and rubric traceability | Active OpenSpec proposal, design, four capability deltas, task list, [consolidated readiness record](aog-recovery-readiness-verification.md), and Controller/Materials evidence maps | `openspec validate --changes "validate-aog-recovery-readiness" --strict` valid; no issues |
| Core contracts and recovery behavior | Cache fallback through the built ADK inventory tool, Controller functional cases, degraded/failure/conflict cases, close-score selection, and human-gate tests | 488 tests passed; 93% total coverage in a fresh Python 3.14.7 environment |
| Lint, format, and types | `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src` | Passed; 216 files formatted; no issues in 68 source files |
| Locked setup | `uv sync --locked --all-groups`; `uv lock --check` | Passed; 91 locked packages installed and lockfile synchronized |
| Security scans | Bandit 1.9.4, pip-audit 2.10.1, Gitleaks 8.30.1; details in `docs/controller-orchestration-verification.md` | No medium/high Bandit issues or known dependency vulnerabilities; low findings and scan limits are listed for review |
| Local startup/readiness | Secret-free `AogSettings` check and offline Operations synthetic demo | Passed; local/mock only. No HTTP health endpoint or live enterprise connectivity is provided. |
| Backout readiness | Whole-workflow backout in `docs/rapid-peer-review.md` | Drafted; release owner must identify the known-good baseline before any release decision |
| Controller sponsor demo and runbook | Offline four-scenario CLI, ten-minute [runbook](capstone-demo-runbook.md), and focused tests | Demo code and runbook are present; rehearsal, acceptance, and presentation remain pending |
| Qualified peer/InfoSec/Reference Architecture review | RAPID record and applicable project review criteria | Pending human review; identities and conclusions not supplied |
| Operational approval | Ops lead plus Maintenance/airworthiness authority for applicable decisions | Always required. Agents do not execute operational actions. |

## Findings and Conditions

- Two dependency warnings remain: the Google GenAI deprecated alias and Google ADK experimental `PLUGGABLE_AUTH` warning.
- Bandit reports seven low-severity `B101` assertion notices; no medium/high findings. These remain for qualified review.
- The Operations ADK entry point rejects a missing or example-placeholder `GEMINI_API_KEY` before serving; provider authenticity cannot be checked without an authorized request.
- Gitleaks found 250 signatures only in ignored `.venv` dependency sources; project-owned files and 39 commit-history entries had no leaks. Binary DOCX/PDF contents are not inspected and remain a manual review limitation.
- The system is advisory and mock-backed. Live airline connectivity, production deployment, airworthiness, and operational readiness are not established.
- Automated validation is complete. Controller demo rehearsal/delivery, qualified review, and team Go/No-Go deliberation remain pending.

## Whole-Workflow Backout

1. Stop local demos or optional ADK processes and suspend use of affected recommendation output; do not perform an operational action.
2. Record the affected revision and have the release owner select the prior known-good baseline. Revert the full readiness change as a reviewed unit while preserving unrelated worktree changes.
3. Restore the paired runtime/dependency state (`pyproject.toml`, `uv.lock`, and `envsetuprequirements.txt`) from that baseline. Preserve audit records, case evidence, and failure status; do not enable write-capable tools.
4. Present an explicit unavailable/partial advisory handoff with human approval pending. Do not fabricate a successful report or clear degraded evidence.
5. Rebuild with `uv sync --locked --all-groups` and rerun pytest, Ruff check/format, mypy, focused security scans, and strict OpenSpec validation. Retain rollback evidence.
6. Re-enable the workflow only after the regression is corrected and required human review is complete.

## Team Decision

**Go/No-Go:** Pending team review.  
**Rationale:** Automated checks are evidence only; they do not replace qualified peer review, security/architecture review, sponsor communication, or team deliberation.
**Decision owner(s), conditions, and date:** To be completed by the team.
