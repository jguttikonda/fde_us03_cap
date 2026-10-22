# Controller Chat Demo

This is a local ADK Web demonstration using fictional records from
`incidents/mock_data/`. It is not connected to live airline systems and does
not perform operational actions.

## Preflight

- Confirm `GOOGLE_API_KEY` is configured in the ignored local `.env` file.
- From the repository root, start the UI with `uv run --env-file .env adk web adk_agents`.
- Open the local URL printed by ADK Web and select `aog_controller`.
- Explain that the system provides advice only; authorized people make and
  approve every operational decision.

## Prompts

### Remote stock

```text
Assess synthetic case AOG-MOCK-1042. Aircraft N123AB is at MIA with hydraulic
pump P-110 failed. Affected flight: FX103. Need-by time: 2026-10-22 18:00 UTC.
Use the part_available_remote scenario (P-120 is in DFW). Return the options,
scores, evidence gaps, and required human approvals. Do not execute any action.
```

Expected: P-120 transfer timing is identified as estimated; Maintenance,
Materials & Logistics, and Operations findings are summarized. The assistant
must not claim a plan is approved or executed.

### Local stock

```text
Assess the same synthetic AOG case, but use part_available_local. P-120 is at
MIA. Compare the repair path with an aircraft swap and show evidence, trade-offs,
confidence, and required human approvals.
```

Expected: the report identifies local P-120 stock and does not reuse the remote
transfer ETA.

### No stock found

```text
Assess the same synthetic AOG case with part_unavailable. No replacement stock
is confirmed at MIA or DFW. Explain what remains unknown, whether an aircraft
swap is viable, and what human review is required. Do not invent a part ETA.
```

Expected: missing vendor/ETA data remains visible; no repair ETA is fabricated;
the result is partial or escalated as the evidence requires.

## Caveats

- The sample maintenance evidence is aligned to the remote-stock scenario. For
  local/no-stock runs, any readiness estimate tied to the remote quote must be
  called out as mismatched rather than reused.
- ADK Web is an unauthenticated local development interface. Keep it bound to
  localhost and do not expose it to a public or untrusted network.
- If the API key is missing, the UI may open but model-backed chat replies will
  fail. Do not paste credentials into source files, prompts, logs, or chat.
- Scores and cost estimates are mock decision-support values. Human approval
  remains mandatory at every confidence level.