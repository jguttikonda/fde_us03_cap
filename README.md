# FDE US03 Capstone Project

## Project Overview
This repository implements an advisory-only Aircraft-On-Ground (AOG) Recovery Coordinator with Controller, Maintenance, Materials & Logistics, and Operations agent workflows. Enterprise integrations are deterministic local/mock adapters; no live airline systems or operational write actions are enabled.

The project focuses on helping airline operations teams respond to aircraft ground events faster, more consistently, and with clearer human oversight.

## Purpose
When an aircraft is grounded, Maintenance, Materials & Logistics, and Operations must act together quickly to find the recovery strategy that minimizes downtime and disruption:
- Maintenance determines the root cause, whether the aircraft can be repaired, how long it takes, and whether maintenance history points to a preferred repair or replacement part
- Materials & Logistics checks part and approved-alternate availability, internal transfer, vendor sourcing, shipping options, and delivery ETA
- Operations evaluates flight and network impact, aircraft swaps, and the redistribution of package loads (FedEx package delivery)
- The Controller coordinates the work, applies the compliance gate, ranks the options, and prepares a recommendation for human approval

The system is designed to support better decisions without replacing human accountability.

## What This Project Solves
The capstone addresses a common airline operations problem:
- aircraft are grounded unexpectedly, and every minute of downtime affects schedules, utilization, customer commitments, and cost
- recovery spans Maintenance, Materials, Logistics, and Operations, and each team holds only part of the information
- no single system provides a consolidated view, so people gather data from multiple systems and coordinate manually under time pressure
- recovery choices (repair with an original or alternate part, swap an aircraft, delay a flight, and how to source parts and redistribute package loads) must balance technical feasibility, engineering and airworthiness requirements, part availability, downstream flight, network and package impact, cost, and compliance

Because these decisions involve competing objectives, changing conditions, and distributed information, recovery planning often depends on individual experience and manual coordination. This project provides explainable decision support that helps reduce downtime while keeping humans fully in control of operational decisions.

## Core Business Idea
The system recommends the optimal recovery strategy using four agents that collaborate through Agent-to-Agent (A2A) communication:
- Controller Agent (Recovery Coordinator): orchestrates all agents, builds and evaluates candidate recovery options in parallel, applies the compliance gate, ranks options on speed, operational and package impact, risk, and cost, and produces an explainable recovery plan for human review
- Maintenance Agent: failure root cause, repair feasibility and duration, maintenance history, recurring failures, airworthiness approval, and preferred replacement parts
- Materials & Logistics Agent: inventory and approved alternate parts, part authorization and traceability, internal transfer, vendor sourcing, shipping (FedEx network and commercial carriers), and ETA; collaborates directly with the Maintenance Agent
- Operations Agent: flight and network impact, aircraft availability and swaps, schedule impact, and package load redistribution

The final recommendation is always reviewed and approved by humans (Ops lead and Maintenance/airworthiness authority) before any operational action is taken. Agents never perform operational actions.

## Ubiquitous Language
This section defines the shared terms used across the project so everyone understands the same concepts.

### Aircraft-On-Ground (AOG)
A situation where an aircraft is unable to fly because of a technical issue, defect, or operational restriction.

### Recovery Decision
The choice of how to return an aircraft to service or minimize disruption: repair with the original part, repair with a preferred or alternate part, aircraft swap, or flight delay, each combined with a sourcing method and a package load-redistribution plan.

### Maintenance
The technical work required to assess the aircraft defect, determine root cause and repair feasibility, estimate downtime, and confirm airworthiness approval.

### Materials & Logistics
The supply and delivery view of whether the required part or an approved alternate is available, authorized and traceable, and how fast it can be transferred, purchased, or shipped.

### Operations
The schedule, fleet, and package-load view that evaluates customer impact, network disruption, swap opportunities, and load redistribution.

### Controller
The coordinating agent that receives the AOG event, routes work to specialists, evaluates alternatives, ranks options, and produces the recommendation for human approval.

### Recommendation
The ranked recovery option proposed to the human approvers, based on technical, material, and operational evidence, after non-compliant options are excluded.

### Human-in-the-Loop
A governance model where AI provides decision support, but a human remains responsible for final approval and operational action.

### Confidence
The degree of trust in a recommendation based on evidence quality, completeness, and risk.

### Escalation
A decision path where the system pauses or asks for human intervention because the evidence is incomplete, conflicting, or low-confidence.

## Expected Outcomes
This project aims to:
- reduce aircraft downtime
- improve the speed and quality of recovery decisions
- provide explainable recommendations
- support coordinated decision-making across functions
- keep accountability with human operators

## Repository Structure
- [docs/proposal.md](docs/proposal.md) — detailed architecture and proposal document
- [docs/agent-proposals](docs/agent-proposals) — specialist agent design proposals

## Development Setup

The project supports Python 3.14.x (`requires-python` is `>=3.14,<3.15`) and
uses `uv.lock` for reproducible runtime and development dependencies. The
complete package export, including hashes, is available in
[envsetuprequirements.txt](envsetuprequirements.txt). Regenerate it after
dependency changes with:

```powershell
uv export --locked --all-groups --format requirements-txt --no-emit-project --output-file envsetuprequirements.txt
```

From the repository root in PowerShell, install the locked runtime and all
development tools, validate local configuration, and run the offline demo:

```powershell
uv sync --locked --all-groups
uv run python --version
uv run python -c "from aog_recovery.config import AogSettings; settings = AogSettings(); print(f'configuration valid; adapter_mode={settings.adapter_mode.value}')"
uv run python -m aog_recovery.operations.demo normal_repair --json
```

The default adapter mode is `local`; `AOG_*` settings have validated defaults.
Run the deterministic tests and code checks with:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

### Optional ADK model configuration

The offline demo and tests do not require a model credential. The optional
model-backed ADK configuration uses the provider-specific variable names shown
in `.env.example` (including `GEMINI_API_KEY` and `ADK_MODEL`). For a model-backed
run, copy `.env.example` to `.env` and replace placeholders using the approved
secret source for your environment. The `.env` file is ignored by Git; never
commit it, put a real key in documentation or tests, or print it to logs.
`OperationsSettings` treats `GEMINI_API_KEY` as secret-typed and excludes it
from representations and serialization. The model-backed Operations ADK web
entry point fails fast when the key is absent or still the example placeholder.
This local check does not contact the provider; a non-placeholder key's
authenticity remains unverified until an authorized model-backed request.

#### Controller ADK Web demo

The Controller ADK Web root exposes only the four named synthetic scenarios.
After configuring a non-placeholder `GEMINI_API_KEY` in the ignored `.env` file,
launch it from the repository root with:

```powershell
uv run --env-file .env adk web adk_agents/controller_agent
```

The browser conversation uses the model provider to interpret the request and
explain the result. The selected case, specialist findings, evidence, and
Operations data are fixed synthetic values; no live enterprise records or
operational writes are available. Startup rejects a missing or template key;
this local check does not validate the key with the provider. ADK Web is an
unauthenticated local development server; keep its
default loopback binding and do not expose it to an untrusted network.

To load the optional model configuration for a command:

```powershell
uv run --env-file .env <command>
```

The local readiness check does not require `.env`; a missing or invalid model
credential must not be replaced with a fabricated value. Restart VS Code
terminals after changing local environment configuration.

### Startup and local readiness

There is no always-on Controller web service or HTTP health endpoint in this
capstone implementation. A local ADK Web demonstration is available under
`adk_agents/controller_agent`; it is not a deployed or authenticated service.
Run the Operations synthetic smoke demo with
`uv run python -m aog_recovery.operations.demo`; it uses deterministic local
adapters and makes no model, network, or operational calls. The configuration
check and `uv run pytest` above are the local readiness checks. They verify the
environment and mock workflows only; they do not prove live enterprise
connectivity, production deployment readiness, airworthiness, or operational
approval. The optional ADK web entry point under `adk_agents/operations_agent`
remains an Operations-only demonstration.

VS Code is configured to use `.venv` and discover pytest tests. If its Python
extension was already open when `.venv` was created, select the workspace
interpreter at `.venv\Scripts\python.exe` or reload the window.

### Operations analysis settings

For an interactive peer-review demo using synthetic fixtures and live Gemini
reasoning, see [the ADK Web runbook](docs/operations-adk-web-peer-review.md).

Operations settings use the `AOG_` environment prefix and are validated by
`AogSettings`. Defaults are for deterministic local/mock analysis only; mock
costs are illustrative and are not estimates of real operating expenses.

| Setting | Default | Purpose |
|---|---:|---|
| `AOG_TOOL_TIMEOUT_SECONDS` | `10` | Timeout for each read-only adapter call |
| `AOG_AGENT_TIMEOUT_SECONDS` | `30` | Timeout for bounded Operations reasoning |
| `AOG_OPERATIONS_MAX_READ_RETRIES` | `1` | Maximum retries for retryable idempotent reads |
| `AOG_OPERATIONS_SOURCE_FRESHNESS_SECONDS` | `900` | Maximum source age before evidence is treated as stale |
| `AOG_OPERATIONS_MEDIUM_DELAY_MINUTES` | `30` | Lower bound for medium operational impact |
| `AOG_OPERATIONS_HIGH_DELAY_MINUTES` | `120` | Lower bound for high operational impact |
| `AOG_OPERATIONS_CRITICAL_DELAY_MINUTES` | `300` | Lower bound for critical operational impact |
| `AOG_OPERATIONS_SERVICE_LEVEL_ORDER` | `["priority","standard"]` | Stable package-allocation priority, encoded as JSON |
| `AOG_OPERATIONS_CONFIDENCE_DEGRADATION_PER_ISSUE` | `0.10` | Confidence reduction for each distinct missing/degraded issue |
| `AOG_OPERATIONS_MOCK_COST_CURRENCY` | `USD` | Currency for mock line items |
| `AOG_OPERATIONS_MOCK_DELAY_COST_PER_MINUTE` | `1.00` | Illustrative delay cost rate |
| `AOG_OPERATIONS_MOCK_SWAP_FLAT_COST` | `500.00` | Illustrative aircraft-swap cost |
| `AOG_OPERATIONS_MOCK_UNPROTECTED_PACKAGE_EXPOSURE` | `2.00` | Illustrative exposure per unprotected package |

Impact thresholds must be strictly increasing, and the service-level order must
be non-empty with no duplicate names. An unset optional cost rate makes the
corresponding estimate unavailable; it is not silently treated as zero.

## Project Status
The four-agent advisory workflow and deterministic local/mock adapters are
implemented, and automated readiness verification is recorded. Live enterprise
integration and production deployment are out of scope; qualified peer review,
team Go/No-Go, sponsor rehearsal/presentation, and all operational approvals
remain human responsibilities.

## Summary
This capstone implementation combines specialist analysis, deterministic
compliance and ranking, evidence traceability, and a mandatory human decision
gate in a reproducible local AOG workflow. It remains advisory and does not
execute operational actions.
