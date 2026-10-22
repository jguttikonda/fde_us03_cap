# FDE US03 Capstone Project

## Project Overview
This repository contains the design and proposal for an Aircraft-On-Ground (AOG) Recovery Coordinator built as a multi-agent decision support system using Google ADK.

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

The complete locked runtime and development package export, including hashes,
is available in [envsetuprequirements.txt](envsetuprequirements.txt). It is
generated from `uv.lock`; regenerate it after dependency changes with:

```powershell
uv export --locked --all-groups --format requirements-txt --no-emit-project --output-file envsetuprequirements.txt
```

For the standard project environment, use `uv sync`; it reads dependencies from
`pyproject.toml` and `uv.lock` rather than from the export file.

The project requires Python 3.14 and uses `uv` to create an isolated environment
and install the Google ADK, Pydantic, and development tools declared in
`pyproject.toml`.

From the repository root in PowerShell:

```powershell
uv sync --all-groups --locked
uv run python --version
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

### Gemini API key

The local `.env` file is ignored by Git. Add your Google AI Studio key to its
`GOOGLE_API_KEY` entry; do not commit or share this file. For a fresh checkout,
copy `.env.example` to `.env` first. The project uses `GOOGLE_GENAI_USE_VERTEXAI=FALSE`
for API-key authentication. To pass the key to a command, use:

```powershell
uv run --env-file .env <command>
```

VS Code Python terminals are configured to load `.env` when opened. Restart
existing terminals after changing the file. Never paste the API key into source,
tests, logs, or chat.

VS Code is configured to use `.venv` and discover pytest tests. If its Python
extension was already open when `.venv` was created, select the workspace
interpreter at `.venv\Scripts\python.exe` or reload the window.

### Local ADK Web AOG chat demo

The Controller chat uses the synthetic inputs in `incidents/mock_data/` and
does not connect to live airline systems. From the repository root in
PowerShell, configure `GOOGLE_API_KEY` in your local, ignored `.env` file, then
start ADK Web:

```powershell
uv sync --all-groups --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Add your key to GOOGLE_API_KEY in .env using your editor.
uv run --env-file .env adk web adk_agents
```

Open the local URL printed by ADK Web and choose `aog_controller`. Example prompt:

```text
Assess synthetic case AOG-MOCK-1042. Aircraft N123AB is at MIA with hydraulic
pump P-110 failed. Affected flight: FX103. Need-by time: 2026-10-22 18:00 UTC.
Use the part_available_remote scenario (P-120 is in DFW). Return the options,
scores, evidence gaps, and required human approvals. Do not execute any action.
```

For local or no-stock behavior, replace the scenario with `part_available_local`
or `part_unavailable`. The assistant asks for missing intake fields instead of
assuming them. If Google API credentials are unavailable, the ADK Web page can
open, but model-backed replies will fail until `GOOGLE_API_KEY` is configured.
All results use synthetic data and are advisory; no operation is performed.
This is a local development demo, not a production UI. See
[docs/controller-chat-demo.md](docs/controller-chat-demo.md) for additional
scenario prompts and expected outcomes.

## Project Status
This repository is currently in the proposal and architecture design phase for an enterprise AOG decision-support system.

## Summary
This capstone project is not just an AI demo. It is a structured operational decision-support concept for airline recovery planning, designed to combine specialist reasoning, policy guardrails, and human oversight into a practical AOG workflow.
