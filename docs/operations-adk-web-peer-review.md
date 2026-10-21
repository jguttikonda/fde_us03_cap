# Operations ADK Web Peer Review

This is a synthetic, advisory-only demo of the existing Operations assessment
and its live Google ADK reasoning boundary. It is not a Controller workflow,
operational integration, approval, airworthiness claim, or application of
[the remediation proposal](./proposal_OpsUpdate.md).

**Test run (2026-10-21): all five browser scenarios passed their expected
checks with live `gemini-3.5-flash` reasoning.** This document retains the
runbook, results, and limitations for this passing test run only.

## Run locally

Configure `GOOGLE_API_KEY` or `GEMINI_API_KEY` in the ignored repository `.env`
file. Never commit or share the key. From the repository root in PowerShell:

```powershell
uv run --env-file .env adk web --host 127.0.0.1 --port 8000 --session_service_uri memory:// --no-reload demos
```

Open `http://127.0.0.1:8000` and select `operations_agent`. The ADK development
server is unauthenticated: keep it bound to loopback, not a public interface.
Model selection uses `AOG_OPERATIONS_DEMO_MODEL` first, then the shared
`ADK_MODEL` setting from `.env`, then `gemini-3.5-flash` if neither is set.
Use a model approved by your provider; there is no automatic model retry or
provider bypass. Empty explicit model settings are rejected. Restart ADK Web
after changing configuration. The reasoning timeout defaults to 60 seconds,
configurable with `AOG_OPERATIONS_DEMO_REASONING_TIMEOUT_SECONDS` (up to 120).
Only synthetic fixture data is passed to Gemini, not arbitrary chat content.
Do not enter sensitive information in ADK Web: its session still records chat.

## Prompts and expected checks

Enter an exact scenario name. Other text returns an explicit `invalid_scenario`
response without invoking a model. This is a fixed-scenario interface, not a
general operational chat intake.

| Prompt | Evidence and expected deterministic checks | ARD |
|---|---|---|
| `swap` | FX401 has 1,200 packages, including 700 priority. FX207 protects 700 priority and 200 standard packages, leaving 300 standard unprotected. Compare against a 90-minute delay option; model preference may vary with the trade-offs. | ARD-OPS-004/005/007/009, ARD-TST-006 |
| `assignment-conflict` | An FX207 assignment overlaps FX401. Swap is infeasible and cannot be selected as the preferred option. | ARD-OPS-002/008 |
| `stale-conflict` | Source states explicitly label stale and conflicting evidence. Conflicts/missing data remain visible and status escalates. | ARD-PRN-006, ARD-GOV-004/005 |
| `low-confidence` | Starting confidence is 0.45; status escalates regardless of the model's preferred option. | ARD-GOV-003/008 |
| `dispatch FX207 now` | Invalid scenario; no model invocation, dispatch, or approval action. | ARD-SEC-003/004, ARD-PRN-001/002 |

Each successful response includes `synthetic_demo`, `human_approval_required`,
the scenario/model, and the complete versioned Operations assessment. Rates
are mock USD estimates: delay $1/minute, swap $50, unprotected packages $2 each.
Fixtures use a fixed mock clock of 2026-10-21 12:00 UTC, not today's live schedule.

## Limitations and review responsibilities

- These are actual deterministic domain results plus live model reasoning,
  not stubbed live responses. Model prose and preference can vary.
- The `stale-conflict` fixture uses explicit source labels; it does not prove
  timestamp-based freshness or automatic contradiction detection. Known
  issues remain documented in [the remediation proposal](./proposal_OpsUpdate.md).
- This single-flight demo does not prove option-specific multi-flight impact
  correction, the Maintenance-versus-Operations ETA-conflict scenario, or
  tool-specific external payload validation.
- Local fixtures supply evidence directly. No enterprise adapter or live
  airline system is called. Live provider failures are displayed as failures,
  not fabricated assessments. Reasoning timeouts retain only the existing
  domain agent's explicitly partial deterministic results.
- Human review, RAPID/Go-No-Go, and sponsor demonstration remain separate
  responsibilities. Running this demo is not peer sign-off (ARD-TEC-019/020).

## Deterministic validation

The demo tests stub only the reasoning boundary; no unit test calls Gemini:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\operations\test_web_demo.py -q
```

Coverage includes each scenario, invalid prompts, structured provider failure,
configuration, package counts, confidence/conflict escalation, and advisory
markers (ARD-TST-001/003/005/007/009).

## Passing test run: 2026-10-21

The effective model was `gemini-3.5-flash`, selected through the shared
`ADK_MODEL` configuration using the precedence documented above. No provider
policy, endpoint, validation, or human-approval boundary was bypassed, and no
mock reasoner was used for this live test run.

ADK Web was restarted on loopback port 8002 with in-memory sessions. All five
prompts were entered through the browser, using session
`ca0d3661-660b-4aae-80b4-ae154c9e82ff` for user `user`.
The actual session responses were retrieved from the running server and
asserted against the checks below.

[Open the passing browser session](http://127.0.0.1:8002/dev-ui/?app=operations_agent&userId=user&session=ca0d3661-660b-4aae-80b4-ae154c9e82ff).
The session is in memory and remains available only while that server runs.
The exact exported responses are retained separately as the chat artifact
**Passing Operations ADK Web transcript**
(`operations-adk-web-passing-responses-20261021.json`).

| Prompt | Actual outcome and verified checks | Result |
|---|---|---|
| `swap` | `complete`, confidence 0.85; swap protects 700 priority and 200 standard packages, leaving 300 standard unprotected. Live reasoning prefers `delay-90`: all 1,200 protected at mock cost $90 versus swap $665. | Pass |
| `assignment-conflict` | `complete`, confidence 0.85; swap infeasible because FX207 overlaps FX999. Live reasoning selects feasible `delay-90`, not the blocked swap. | Pass |
| `stale-conflict` | `escalation_required`, confidence 0.65; conflicts and missing/stale evidence remain visible. Recommendation status is `escalate`, not approval. | Pass |
| `low-confidence` | `escalation_required`, confidence 0.45; human review remains mandatory. | Pass |
| `dispatch FX207 now` | `invalid_scenario`; no assessment or operational action. | Pass |

All four model-dependent responses identify `gemini-3.5-flash`, contain no
assessment errors, and retain human approval both in the demo envelope and
the recommendation. Escalation and invalid-scenario responses are expected
successful guardrail outcomes; they must not be converted into approval.

Validation for this test run:

- Operations and settings tests: **87 passed**, including **17 demo tests**.
- Six new deterministic configuration cases cover shared model selection,
  explicit override precedence, the default, and rejection of empty settings
  (ARD-TEC-007, ARD-TST-009, ARD-PRN-006).
- Ruff check and format check: passed for both changed Python files.
- Mypy: passed for all 32 source files.
- Pylance syntax checks: passed for both changed Python files.
- One existing upstream Google GenAI deprecation warning remains.

These checks exercise ARD-OPS-002/005/007/008/009, ARD-GOV-003/004/008,
ARD-PRN-001/002/006, and ARD-TST-003/005/008/009. They do not certify the full
Controller workflow, dual-authority approval records, airworthiness, or
operational readiness. Human peer-review sign-off remains pending
(ARD-TEC-019/020).
