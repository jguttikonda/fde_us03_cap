# Controller Chat Demo Evidence

Date: 2026-10-22

## Verification

- Full test suite: `uv run pytest` passed, 423 tests.
- Lint: `uv run ruff check .` passed.
- Formatting: `uv run ruff format --check .` passed.
- Types: `uv run mypy src` passed for 62 source files.
- Synthetic Controller pipeline: remote-stock fixture passed through candidate
  generation, Maintenance and Materials & Logistics results, recorded peer
  exchange, Operations assessment, compliance, scoring, brief assembly, and
  deterministic chat rendering.
- Scenario and guardrail tests cover local/remote/unavailable stock, missing
  estimates, failed specialists, stale/conflicting evidence, compliance
  exclusions, confidence bands, close scores, and mandatory human approval.
- ADK Web returned HTTP 200 at `http://127.0.0.1:8000`; `/list-apps` returned
  `controller_agent` and `operations_agent`.

## Limitations and Open Items

- `GOOGLE_API_KEY` was not configured in the environment during verification.
  The ADK Web page starts, but an interactive model-backed chat turn has not
  been verified. Configure the key in the ignored local `.env` file and restart
  ADK Web before the sponsor demonstration.
- All business inputs and estimates are synthetic. There are no live airline
  integrations, production authentication, or operational write tools.
- ADK Web exposes unauthenticated local-development endpoints; the server is
  bound to `127.0.0.1` and must not be exposed to an untrusted network.
- RAPID peer review, operational Go/No-Go, and sponsor approval remain human
  activities and are not represented as complete by these automated checks.

## Human Gate

All recommendations are advisory. No tool performs an operational action.
Human approval remains required regardless of confidence, test mode, or
evidence quality; missing and conflicting evidence remains visible and may
cause provisional status or escalation.