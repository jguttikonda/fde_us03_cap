# Capstone Sponsor Demonstration Runbook

**Target duration:** 10 minutes  
**Status:** Draft for team rehearsal; no rehearsal or sponsor acceptance is claimed  
**Entry point:** `uv run python -m aog_recovery.controller.demo`  
**Evidence:** [Controller verification](controller-orchestration-verification.md) and [readiness verification](aog-recovery-readiness-verification.md)

## Before the Session

From the repository root, use Python 3.14.x and the locked dependencies:

```powershell
uv sync --locked --all-groups
uv run python -m aog_recovery.controller.demo
```

The demo uses synthetic evidence and deterministic local adapters. It needs no `.env`, model key, airline network, external service, or operational system. Run an individual scenario with one of `happy_path`, `cache_degraded`, `time_conflict`, or `close_score_choice`; append `--json` for structured output. The CLI is repeatable and makes no operational action.

The CLI uses fixed typed Maintenance and Materials findings, runs the synthetic
Operations adapter, and exercises Controller aggregation, compliance, scoring,
and report generation. It does not invoke the Maintenance or Materials prompt
pipelines, Controller intake/routing, or H3/H4 recorder; those boundaries are
covered separately by the integration suite.

The CLI uses fixed typed Maintenance and Materials findings, runs the synthetic
Operations adapter, and exercises Controller aggregation, compliance, scoring,
and report generation. It does not invoke the Maintenance or Materials prompt
pipelines, Controller intake/routing, or H3/H4 recorder; those boundaries are
covered separately by the integration suite.

## Ten-Minute Flow

| Time | Presenter flow | Synthetic inputs | Expected demonstration result |
|---|---|---|---|
| 0:00-1:00 | Frame the AOG problem and the system boundary: four specialist workflows support, but do not replace, human decisions. | No case input. | Explain that all case data and adapters are synthetic/local; no live airline integration or write capability is present. |
| 1:00-3:00 | Run `uv run python -m aog_recovery.controller.demo happy_path`. | Synthetic AOG-SYN-0001 / P-110 failure; current P-120 compatibility, authorization, and traceability; recorded engineering approval; a two-hour repair estimate. | One source-backed P-120 repair option is ranked with evidence references, trade-off, confidence, and a pending two-role human gate. The sample is provisional at 0.69 because the readiness ETA is estimated; it is not an approval. |
| 3:00-5:00 | Run `uv run python -m aog_recovery.controller.demo cache_degraded`. | Same synthetic case; live inventory unavailable; P-120 quantity from a provenance-bearing cache retrieved one day earlier; current authorization and traceability evidence. | The live inventory failure remains visible alongside stale cached quantity evidence and `CACHED_EVIDENCE`; the report escalates at 0.49 and keeps the human gate pending. |
| 5:00-7:00 | Run `uv run python -m aog_recovery.controller.demo time_conflict`. | Same synthetic case; Maintenance estimate 3 hours and Operations disruption estimate 7 hours on the same recovery-time claim. | Both estimates and source references, conflict warning, escalation, and pending approval are visible together. |
| 7:00-8:30 | Run `uv run python -m aog_recovery.controller.demo close_score_choice`. | Two otherwise identical compliant P-120 repair candidates with equal synthetic ETA, cost, risk, and Operations impact. | Both tied options are shown in selection group 1 with their trade-offs; the report requests human selection and does not choose a winner. |
| 8:30-10:00 | Summarize business value, limits, and next validation steps; take questions. | Review the four report outputs and evidence references; no additional operational input. | Emphasize that ranking prioritizes review, while humans own selection, airworthiness judgment, approval, and any operational action. |

For machine-readable output, for example:

```powershell
uv run python -m aog_recovery.controller.demo --json happy_path cache_degraded
```

## Business Value and Design Rationale

The workflow brings technical feasibility, material readiness, and operational impact into one evidence-linked Controller report. This helps teams compare alternatives faster, exposes missing or stale information, and makes cost, package, risk, and timing trade-offs reviewable.

The demo is offline and deterministic so the same inputs produce the same outputs without model variability or enterprise access. Typed contracts validate agent/tool boundaries; deterministic logic handles compliance, confidence, scoring, and close-score grouping. Compliance exclusions occur before ranking. Close scores require human choice, and every scenario leaves the human gate pending until the required people approve the same report/option.

## Risks and Caveats

- All case facts, costs, inventory, flight data, and adapters are synthetic; they do not represent an airline or current operational state.
- The sample cost model and estimates are illustrative. The happy path is provisional because its ETA basis is estimated.
- Cache data stays stale and does not establish current stock or part authorization. Conflicting time evidence requires human adjudication.
- The Operations synthetic adapter is not a live schedule/fleet integration. The demo does not establish production readiness, airworthiness, regulatory compliance, or operational approval.
- The demo invokes no purchase, transfer, shipment, booking, dispatch, delay, aircraft assignment, or other operational write.
- The Controller demo is a local CLI, not an always-on service; no HTTP health endpoint or live enterprise health check is provided.
- The close-score case demonstrates a pending selection gate; it does not collect or fabricate a real human decision.

## Future Improvements

- Rehearse the timed flow and have the team practice explaining evidence, confidence, score factors, limits, and approval responsibilities.
- Add live read-only integrations only after interface, identity, security, audit, and degraded-mode reviews are approved.
- Add service health/telemetry only when a deployed service and configured live adapters exist.
- Gather sponsor feedback before proposing workflow, report, or UI changes.

## Q&A Prompts

- Which additional evidence would change the repair-versus-swap comparison?
- How should an operational team respond when only stale inventory evidence is available?
- What controls and ownership would be required before connecting a live inventory or schedule source?
- Which people must agree before any repair or operational plan proceeds?
- What should be measured in a future rehearsal or controlled pilot?

## Human Follow-Through

The team must rehearse and deliver the presentation, answer live questions, and record sponsor feedback. A qualified peer must complete the RAPID review; the team must make its own evidence-backed Go/No-Go decision. These activities are pending and are not satisfied by the automated scenarios or this runbook.
