# Architecture Requirements Document

## Aircraft-On-Ground Recovery Coordinator

| Field | Value |
|---|---|
| Document ID | ARD-AOG-001 |
| Version | 1.0 |
| Status | Approved implementation baseline |
| Architecture style | Controller-led multi-agent decision support |
| Runtime language | Python |
| Agent framework | Google Agent Development Kit (ADK) |
| Data validation | Pydantic |
| Primary specification workflow | OpenSpec |

## 1. Purpose

This Architecture Requirements Document (ARD) is the authoritative engineering baseline for the Aircraft-On-Ground (AOG) Recovery Coordinator. It converts the project proposal and agent drafts into uniquely identified, testable requirements that OpenSpec proposals, designs, specifications, and tasks must follow.

The system coordinates specialized Maintenance, Inventory, Operations, and Report Creation agents through a Controller Agent. It addresses the business problem that AOG recovery information is distributed across Maintenance, Materials, Logistics, and Operations with no consolidated view. It evaluates recovery options and presents an explainable recommendation to a human decision-maker. It is an advisory system and does not execute operational actions.

## 2. Source Documents and Precedence

This ARD consolidates requirements from:

- `docs/proposal.md`
- `docs/capstone_rubric_phase_checklist.md`
- `docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md`
- `docs/agent-proposals/controller-agent-proposal.md`
- `docs/agent-proposals/maintenance-agent-proposal.md`
- `docs/agent-proposals/inventory-agent-proposal.md`
- `docs/agent-proposals/operations-agent-proposal.md`
- `docs/agent-proposals/report-creation-agent-proposal.md`

When project artifacts disagree, use this precedence:

1. Safety, security, and mandatory human-approval requirements in this ARD
2. Other requirements in this ARD
3. Accepted OpenSpec capability specifications
4. The root project proposal
5. Individual agent proposals

An OpenSpec change must explicitly identify and resolve any requested departure from this ARD. It must not silently weaken an ARD requirement.

## 3. Requirement Language

The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

Each requirement has a stable identifier:

```text
ARD-<AREA>-<NUMBER>
```

OpenSpec artifacts must cite these identifiers rather than copying requirements without traceability.

## 4. Scope

### 4.1 In Scope

- AOG case intake and validation
- Shared typed contracts for cases, evidence, tools, and agent results
- Controller-led routing and workflow coordination
- Maintenance repairability analysis
- Inventory availability and sourcing analysis
- Operations disruption and recovery analysis
- Recovery-option scoring, ranking, and explanation
- Confidence evaluation and escalation
- Human review, approval, rejection, and requests for more information
- Auditability, observability, degraded operation, and test evidence
- Local or mock integrations suitable for a capstone demonstration

### 4.2 Out of Scope

- Autonomous operational execution
- Automatic approval of maintenance work
- Automatic movement or reservation of inventory
- Automatic aircraft assignment changes
- Automatic flight delay, reroute, cancellation, or customer re-accommodation
- Production integration with live airline systems
- Replacement of certified engineering, safety, dispatch, or operational authority
- Logistics Agent and Risk Agent roles removed from the approved project scope

## 5. Architectural Context

```text
Human Operator
      |
      v
+-------------------+
| Controller Agent  |
+---------+---------+
          |
          +------------------+------------------+
          |                  |                  |
          v                  v                  v
+----------------+  +----------------+  +----------------+
| Maintenance    |  | Operations     |  | Shared Context |
| Agent          |  | Agent          |  | and Audit      |
+-------+--------+  +-------+--------+  +----------------+
        |
        v
+----------------+
| Inventory      |
| Agent          |
+-------+--------+
        |
        +------------------+------------------+
                           v
                 +----------------------+
                 | Report Creation      |
                 | Agent                |
                 +----------+-----------+
                            |
                            v
                    Human Approval
```

The Controller owns routing and shared workflow state. Maintenance may request Inventory evidence, but the Controller must retain traceable ownership of the interaction. The Report Creation Agent owns ranking and presentation; it does not own final approval.

## 5A. Technology and Supporting Frameworks

This section defines the approved implementation stack. A framework marked **Required** must be used unless an OpenSpec proposal documents and obtains approval for an ARD deviation. **Recommended** frameworks are the default choice but may be replaced by an equivalent with a documented design rationale. **Conditional** frameworks are required only when the associated capability is implemented. **Optional** frameworks must not be added without a demonstrated requirement.

| Area | Technology or framework | Status | Intended use |
|---|---|---|---|
| Runtime | Python 3 | Required | Application, agents, tools, validation, and tests |
| Agent orchestration | Google Agent Development Kit (`google-adk`) | Required | Agent definitions, Controller coordination, sessions, tool registration, and agent execution |
| Data contracts | Pydantic 2 | Required | Versioned request, response, evidence, decision, configuration, and error models |
| Settings | `pydantic-settings` | Required | Typed environment-based configuration and secret references |
| Model integration | Google Gen AI integration supported by ADK | Required | LLM access through ADK abstractions rather than ad hoc model calls |
| Tool interoperability | Model Context Protocol Python SDK | Conditional | MCP servers or clients when tools cross a process or service boundary |
| HTTP integration | HTTPX | Recommended | Async calls from adapters to mock or future external services |
| API surface | FastAPI | Optional | Local HTTP API only when an OpenSpec capability requires one |
| Testing | pytest | Required | Unit, contract, integration, scenario, and regression tests |
| Async testing | `pytest-asyncio` | Conditional | Tests for asynchronous agents, tools, and adapters |
| Mocking | pytest fixtures and `unittest.mock` | Required | Deterministic enterprise-system adapters and failure simulation |
| Coverage | `pytest-cov` | Recommended | Test coverage evidence and identification of untested paths |
| Linting and formatting | Ruff | Required | Consistent formatting, import checks, and static linting |
| Type checking | mypy | Recommended | Static verification of typed boundaries and implementation code |
| Observability | Python `logging` with structured JSON output | Required | Case-correlated application and audit events |
| Telemetry | OpenTelemetry Python SDK | Recommended | Traces and metrics when runtime telemetry is implemented |
| Source control | Git and GitHub | Required | Inspectable iteration history, peer review, change evidence, and collaboration |
| AI-assisted development | GitHub Copilot Agent Mode in VS Code | Required for capstone evidence | Implementation assistance, review prompts, and documented human redirection |
| Project instructions | `.github/copilot-instructions.md` or `AGENTS.md` | Required | Project-specific constraints for AI-assisted development |
| Continuous integration | GitHub Actions | Recommended | Repeatable lint, type, test, coverage, and security checks |
| Static security analysis | Bandit | Recommended | Detection of common Python security defects |
| Dependency vulnerability analysis | `pip-audit` | Recommended | Detection of known vulnerabilities in Python dependencies |
| Secret detection | GitHub secret scanning or Gitleaks | Required | Detection of committed credentials and secrets |
| Serialization | Python JSON support and Pydantic serialization | Required | Structured agent, tool, audit, and test payloads |
| Configuration files | YAML | Recommended | Human-maintained non-secret configuration where structured files are needed |
| Specification | OpenSpec | Required | Proposal, design, capability specification, task, and archive workflow |
| Architecture documentation | Markdown and Mermaid | Required | Reviewable requirements, traceability, workflow diagrams, and design rationale |
| RAPID evidence | Markdown templates in `docs/` | Required | Peer review, Go/No-Go, test summary, unresolved issues, and backout evidence |
| Demonstration evidence | Markdown runbook and deterministic fixtures | Required | Rehearsable sponsor-facing scenarios and live debrief support |
| Dependency metadata | `pyproject.toml` | Required | Runtime constraints, dependencies, test tools, linting, and type-check configuration |
| Environment isolation | Python virtual environment | Required | Reproducible local development and test isolation |
| Package workflow | `uv` or standard `pip` | Recommended | Reproducible dependency installation; one workflow must be selected and documented |
| Containerization | Docker | Optional | Portable demonstration or deployment packaging when required by an OpenSpec change |

FastAPI, Docker, OpenTelemetry exporters, databases, queues, vector stores, and additional agent frameworks are not baseline requirements. They may be introduced only when an OpenSpec change demonstrates a capability need, documents operational impact, and preserves the requirements in this ARD.

### ARD-TEC-001 - Python runtime

The implementation MUST use a supported Python 3 release, declare the exact supported range in `pyproject.toml`, and use the same range in local development and continuous integration.

### ARD-TEC-002 - Google ADK

Agents, tools, sessions, and Controller orchestration MUST use Google ADK abstractions rather than a parallel custom agent framework.

### ARD-TEC-003 - Pydantic contracts

Pydantic 2 MUST define and validate configuration, inter-agent messages, tool requests and results, evidence, errors, scores, recommendations, and approval records.

### ARD-TEC-004 - Typed settings

Application settings MUST use `pydantic-settings` or an approved equivalent and MUST load secret values from the environment or an external secret provider rather than source files.

### ARD-TEC-005 - Model access boundary

LLM access MUST be configured through Google ADK-supported model interfaces. Domain components MUST NOT make ungoverned direct model-provider calls.

### ARD-TEC-006 - MCP boundary

When a tool is exposed across a process or service boundary using MCP, the implementation MUST use the supported Model Context Protocol SDK and MUST retain the typed validation, allowlisting, timeout, error, and audit requirements in this ARD.

### ARD-TEC-007 - Asynchronous I/O

Network and agent operations SHOULD use Python asynchronous interfaces where concurrency is beneficial, and asynchronous behavior MUST remain bounded by explicit timeouts and cancellation handling.

### ARD-TEC-008 - Test framework

Automated Python tests MUST use pytest. Asynchronous tests MUST use a pytest-compatible async plugin such as `pytest-asyncio`.

### ARD-TEC-009 - Code quality

The project MUST configure Ruff for formatting and linting and SHOULD configure mypy for static type checking. OpenSpec implementation changes MUST pass the configured checks before archive.

### ARD-TEC-010 - Dependency declaration

All direct runtime and development dependencies MUST be declared in `pyproject.toml`, separated by purpose where supported, and constrained to compatible version ranges.

### ARD-TEC-011 - Dependency selection

New frameworks or infrastructure dependencies MUST be introduced through an OpenSpec design decision that identifies the capability need, alternatives, security impact, maintenance cost, and verification approach.

### ARD-TEC-012 - Framework minimization

The implementation MUST NOT add a web framework, database, message broker, vector store, container platform, or second agent framework unless an approved OpenSpec requirement needs it.

### ARD-TEC-013 - Framework version verification

Before implementation, the applicable OpenSpec change MUST verify currently supported versions of Python, Google ADK, Pydantic, MCP SDK, and development tools, then record the selected compatible versions in dependency metadata.

### ARD-TEC-014 - Reproducible setup

The repository MUST document one supported environment and package installation workflow and MUST provide a reproducible command for installing runtime and development dependencies.

### ARD-TEC-015 - Version-control evidence

The project MUST use Git and GitHub in a way that preserves inspectable proposal and implementation iteration. History MUST NOT be flattened or force-pushed in a way that removes required capstone evidence.

### ARD-TEC-016 - Copilot project instructions

The repository MUST contain a coherent, project-specific `.github/copilot-instructions.md` or `AGENTS.md` that reflects this ARD, the OpenSpec workflow, agent boundaries, human approval, testing, and security expectations.

### ARD-TEC-017 - Continuous verification

The project SHOULD use GitHub Actions to run Ruff, configured type checks, pytest, coverage, secret detection, and applicable security checks on proposed changes.

### ARD-TEC-018 - Security tooling

The implementation MUST have a documented secret-scanning mechanism and SHOULD run Bandit and `pip-audit` or approved equivalents. Findings MUST be resolved, accepted with rationale, or listed as outstanding issues in readiness evidence.

### ARD-TEC-019 - Static evidence artifacts

Rubric and RAPID evidence MUST be retained as reviewable repository artifacts that identify who, what, when, where, why, and how. A transient tool result without a retained summary or location reference is insufficient.

### ARD-TEC-020 - Framework limits

Frameworks and automation MUST support but MUST NOT be represented as replacing peer review, management or human approval, evidence-backed Go/No-Go decisions, sponsor communication, live questions and answers, or documented human judgment.

## 5B. Capstone Rubric Coverage Matrix

The rubric is pass/fail by checkbox; no category may be compensated for by strength in another category. The stack therefore combines implementation frameworks, automated verification, retained evidence, and human activities.

| Rubric category | Required capabilities | Primary frameworks or mechanisms | Required retained evidence | Human responsibility |
|---|---|---|---|---|
| 1. Agent functionality and correctness | End-to-end scenarios, Pydantic-conformant output, evidence-backed decisions, edge cases, correct tools and arguments, clear tool docstrings | Google ADK, Pydantic 2, MCP SDK when applicable, pytest, deterministic fixtures, structured logging | Scenario results, schema-validation results, tool trajectories, decision rationale, tool contract and docstring review | Confirm outputs are operationally credible and evidence is interpreted correctly |
| 2. Spec-driven design quality | Coherent proposal, implementation checklist, non-trivial design, spec deltas, models matching specs | OpenSpec, ARD IDs, Markdown, Mermaid, Pydantic 2, Git | `proposal.md`, `design.md` or justified absence, `tasks.md`, capability specs, traceability, model/spec comparison | Review design decisions, scope, impact, and ARD deviations |
| 3. Engineering quality | Tool and decision tests, partial-data behavior, tool error handling, fallbacks, guardrails, no secrets, readable code | pytest, `pytest-asyncio`, `pytest-cov`, Ruff, mypy, Pydantic, Bandit, `pip-audit`, secret scanning, structured errors | Test summary, coverage report, lint/type/security results, fallback scenarios, outstanding findings | Review maintainability, accepted risks, fallback appropriateness, and unresolved findings |
| 4. RAPID controls execution | ITC.009 peer review and ITC.004 Go/No-Go | GitHub pull request or review diff, Copilot RAPID peer-review prompt, Markdown evidence templates, Git history, CI results | `docs/rapid-peer-review.md`, `docs/go-no-go-checklist.md`, modified-file inventory, author/reviewer IDs, six Code Work Product criteria, test summary, issues, backout plan, recommendation and rationale | Qualified peer review; team Go/No-Go decision; explain alignment or divergence from agent output when applicable |
| 5. AI-assisted development practice | Project instructions, inspectable iteration, prompt/design evidence, visible proposal evolution, rejected or redirected AI output, speed and correction reflection | GitHub Copilot Agent Mode, `.github/copilot-instructions.md` or `AGENTS.md`, OpenSpec, Git/GitHub, saved prompt guide | Commit history, prompt logs or design notes, OpenSpec history, at least one redirection decision and one assistance/correction reflection | Team must explain why AI output was accepted, rejected, or corrected |
| 6. Demonstration and communication | Maximum 10-minute sponsor-oriented demonstration, design rationale, future improvements, live questions and answers | Deterministic fixtures, demo runbook, structured decision report, optional presentation tooling | Demo script/runbook, scenario inputs and outputs, risks, caveats, business outcomes, anticipated debrief notes | Deliver the presentation, frame it for sponsors, answer live questions, and defend decisions |

### ARD-RUB-001 - Checkbox completeness

Readiness MUST assess every rubric checkbox individually. A passing result in one category MUST NOT compensate for an unmet checkbox in another.

### ARD-RUB-002 - Tool selection evidence

Defined scenarios MUST retain enough trajectory evidence to verify that each agent selected an appropriate tool and supplied valid arguments, not merely that the final output looked plausible.

### ARD-RUB-003 - Tool documentation

Every agent-facing tool MUST have a concise docstring describing its purpose, when it should be selected, valid inputs, returned result, error behavior, and material limitations.

### ARD-RUB-004 - Spec implementation consistency

The final Pydantic models, OpenSpec capability requirements, implementation, and tests MUST be checked for consistency before a change is considered complete.

### ARD-RUB-005 - RAPID peer-review artifact

The project MUST produce `docs/rapid-peer-review.md` using the provided RAPID peer-review prompt and address modified-file inventory, author and reviewer identification, InfoSec alignment, Reference Architecture alignment, documentation adequacy, and behavioral scope compliance.

### ARD-RUB-006 - RAPID review recommendation

The RAPID peer-review artifact MUST conclude with approved, approved with conditions, or not approved and MUST identify the evidence supporting that conclusion.

### ARD-RUB-007 - Go/No-Go artifact

The project MUST produce `docs/go-no-go-checklist.md` containing documented requirements, code-review completion, test-result summary, outstanding issues, a sufficiently actionable backout plan, and an evidence-backed decision with rationale.

### ARD-RUB-008 - AI-assistance evidence

The repository MUST retain prompts, prompt logs, or design notes and MUST preserve visible OpenSpec proposal iteration rather than backfilling planning artifacts after implementation.

### ARD-RUB-009 - Human redirection evidence

The team MUST retain and be able to explain at least one instance where it rejected or redirected Copilot output, why it did so, where Copilot accelerated work, and where human correction was required.

### ARD-RUB-010 - Demonstration constraints

The team MUST prepare and rehearse a sponsor-oriented demonstration of no more than 10 minutes that explains design choices, business value, risks, human approval, and what would be changed with more time.

### ARD-RUB-011 - Live communication

Frameworks MAY prepare deterministic evidence and debrief notes, but team members MUST answer live questions and defend design and decision choices.

### ARD-RUB-012 - Capstone scope boundary

The project SHOULD demonstrate production-readiness patterns but MUST NOT treat production deployment, visual polish, lines of code, commit count, RAPID controls beyond ITC.009 and ITC.004, or OpenSpec archival hygiene as graded capstone requirements.

## 5C. Proposal Capability Coverage Matrix

| Proposal capability | Primary implementation support | Verification support | Governing ARD areas |
|---|---|---|---|
| AOG event intake and validation | Google ADK Controller, Pydantic models and validators | pytest schema and invalid-input scenarios | ARD-DAT, ARD-CTL |
| Controller routing and shared context | Google ADK agents, sessions, callbacks, typed context | deterministic routing tests and structured trajectory logs | ARD-SYS, ARD-CTL, ARD-OBS |
| Maintenance repairability assessment | ADK Maintenance Agent, typed maintenance tools, mock maintenance adapters | domain fixtures, safety-gate and incomplete-work-order tests | ARD-MNT |
| Inventory availability and sourcing | ADK Inventory Agent, typed inventory tools, HTTPX or local adapters | availability, stale-cache, substitution, and lead-time tests | ARD-INV, ARD-RES |
| Operations disruption analysis | ADK Operations Agent, typed schedule and fleet tools | route-conflict, substitution, timeout, and customer-impact tests | ARD-OPS, ARD-RES |
| Report creation and option ranking | ADK Report Creation Agent, deterministic Python scoring, Pydantic report model | exact weight, ranking, close-score, and missing-input tests | ARD-RPT |
| Confidence and escalation | Deterministic Python policy functions and Pydantic enums | threshold boundary, conflict, and escalation tests | ARD-GOV |
| Human review and approval | Typed approval command and record; optional FastAPI only if a UI/API is specified | no-bypass and approval-record tests | ARD-GOV, ARD-SEC |
| MCP and external systems | MCP SDK when crossing process boundaries; HTTPX and typed adapters; deterministic mocks | contract, timeout, malformed-response, and structured-error tests | ARD-DAT, ARD-SYS, ARD-RES |
| Local context and memory | ADK session or state abstractions with case-scoped Pydantic state | case-isolation, retention, and context-compression tests | ARD-SYS, ARD-DAT, ARD-SEC |
| Explainability and evidence | Pydantic evidence models, structured rationale, score breakdowns, JSON logs | evidence-source, assumption, warning, and trace completeness assertions | ARD-PRN, ARD-RPT, ARD-OBS |
| Security guardrails | Tool allowlists, Pydantic validation, settings isolation, secret scanning, Bandit and dependency audit | injection, unauthorized-tool, redaction, malformed-data, and read-only tests | ARD-SEC |
| Resilience and degraded operation | Structured errors, bounded retries, timeouts, cache labeling, partial-result models | unavailable-tool, timeout, stale-data, retry, and partial-result tests | ARD-RES, ARD-NFR |
| Audit and observability | Structured Python logging; OpenTelemetry when needed | event-schema, correlation, trajectory, and audit-record tests | ARD-OBS |
| Testing and regression evidence | pytest ecosystem, deterministic fixtures, CI | unit, contract, integration, scenario, regression, security, and summarized results | ARD-TST |
| OpenSpec traceability | OpenSpec, ARD IDs, Git history | proposal/design/spec/task consistency checks | ARD-OSP, ARD-RUB |
| RAPID readiness | Git/GitHub evidence, CI outputs, Markdown control artifacts | peer-review and Go/No-Go completeness review | ARD-DEP, ARD-RUB |
| Sponsor demonstration | deterministic scenarios, demo runbook, structured human-readable report | timed rehearsal and expected-output comparison | ARD-DEP, ARD-RUB |

### ARD-CAP-001 - Capability implementation mapping

Every capability introduced by an OpenSpec change MUST identify its runtime framework, contract model, deterministic controls, external adapter or mock, observability events, security controls, and verification approach.

### ARD-CAP-002 - Unsupported capability prevention

An OpenSpec proposal MUST NOT claim a proposal capability is covered solely because a framework is installed; it MUST identify the configured component and acceptance scenario that provide the behavior.

### ARD-CAP-003 - Coverage gap handling

If a proposal or rubric capability cannot be mapped to an approved framework, repository artifact, test mechanism, or human activity, the OpenSpec proposal MUST mark it as a gap and resolve or explicitly defer it before implementation.

## 6. Architecture Principles

### ARD-PRN-001 - Human accountability

The system MUST keep a human responsible for every final operational decision.

### ARD-PRN-002 - Advisory operation

The system MUST provide decision support only and MUST NOT execute an operational recovery action.

### ARD-PRN-003 - Deterministic guardrails

The system MUST use deterministic logic for validation, policy gates, calculations, schema enforcement, and repeatable routing decisions.

### ARD-PRN-004 - Bounded agent reasoning

LLM reasoning MUST be limited to contextual interpretation, trade-off analysis, prioritization, synthesis, and explanation within the agent's assigned domain.

### ARD-PRN-005 - Evidence before conclusion

Every recommendation MUST identify supporting evidence, assumptions, uncertainty, and material risks.

### ARD-PRN-006 - No silent degradation

Missing, stale, contradictory, or unavailable data MUST be visible in the result and MUST affect confidence or escalation.

### ARD-PRN-007 - Typed boundaries

All inter-agent and tool boundaries MUST use versioned, validated, structured contracts.

### ARD-PRN-008 - Traceable coordination

Every routing decision, tool invocation, agent result, scoring decision, escalation, and human decision MUST be traceable to one AOG case.

## 7. System Decomposition Requirements

### ARD-SYS-001 - Required components

The system MUST include a Controller Agent, Maintenance Agent, Inventory Agent, Operations Agent, Report Creation Agent, deterministic tool layer, shared contract layer, and human-approval boundary.

### ARD-SYS-002 - Controller ownership

The Controller MUST own case intake, shared workflow state, routing, specialist coordination, result aggregation, conflict handling, escalation, and handoff for reporting.

### ARD-SYS-003 - Domain isolation

Each specialist agent MUST reason only over its defined domain and MUST NOT assume responsibility assigned to another agent.

### ARD-SYS-004 - Inventory coordination

Maintenance MAY request Inventory evidence, but the request and response MUST pass through or be recorded in the Controller-managed case context.

### ARD-SYS-005 - Reporting ownership

The Report Creation Agent MUST own recovery-option comparison, deterministic score calculation, relative ranking, explanation, and decision-brief generation.

### ARD-SYS-006 - Approval ownership

Only the human approval boundary MAY approve, reject, or request additional information for an operational recommendation.

### ARD-SYS-007 - External system abstraction

External maintenance, inventory, operations, governance, and reporting systems MUST be accessed through typed adapters or tools rather than directly from agent reasoning code.

### ARD-SYS-008 - Capstone integration mode

The initial implementation MUST provide deterministic local or mock adapters and MUST NOT require live airline systems for tests or demonstrations.

### ARD-SYS-009 - Future integration

Mock adapters SHOULD implement the same interfaces expected of future live integrations so that replacements do not alter agent contracts.

## 8. Shared Contract and Data Requirements

### ARD-DAT-001 - Pydantic models

Python data exchanged at system boundaries MUST be represented by Pydantic models.

### ARD-DAT-002 - Case identity

Every case MUST have a unique case identifier, aircraft identifier, event type, defect summary, location, event timestamp, and creation timestamp.

### ARD-DAT-003 - Correlation

Every tool call and agent execution MUST include or inherit the case identifier and a correlation or trace identifier.

### ARD-DAT-004 - Evidence model

Evidence MUST identify its source, retrieval time, freshness or validity state, relevant content, and the claim it supports.

### ARD-DAT-005 - Fact and assumption separation

Confirmed facts, inferred conclusions, assumptions, warnings, and unknowns MUST be represented separately.

### ARD-DAT-006 - Confidence representation

Agent and recommendation confidence MUST be represented as a normalized value from 0.0 through 1.0 and mapped to the policy thresholds in this ARD.

### ARD-DAT-007 - Tool result contract

A tool result MUST indicate success or failure, returned data, source, timestamp, warnings, and a structured error when unsuccessful.

### ARD-DAT-008 - Structured failures

Tool and agent failures MUST use explicit error categories and MUST NOT be returned as success-shaped responses.

### ARD-DAT-009 - Schema rejection

Inputs and outputs that do not satisfy their required schema MUST be rejected or escalated and MUST NOT silently receive default business values.

### ARD-DAT-010 - Contract versioning

Shared request, response, and event contracts MUST expose a schema version.

### ARD-DAT-011 - Decision status

The shared decision model MUST distinguish at least recommended, provisional, requires escalation, rejected, and awaiting additional data.

### ARD-DAT-012 - Recovery options

The shared recovery-option model MUST support repair, part transfer, part substitution, aircraft swap or substitution, reroute, delay, and escalation.

## 9. Case Intake and Controller Requirements

### ARD-CTL-001 - Intake validation

The Controller MUST validate required AOG fields before specialist routing.

### ARD-CTL-002 - Invalid intake

An invalid case MUST return a structured list of missing or invalid fields and MUST NOT be routed for recommendation.

### ARD-CTL-003 - Source health

The Controller MUST record the availability and health of required specialist data sources before or during routing.

### ARD-CTL-004 - Explicit routing

The Controller MUST record which agents were selected, which were omitted, and the reason for each routing decision.

### ARD-CTL-005 - Shared context

The Controller MUST maintain a case-scoped shared context without exposing unrelated case data.

### ARD-CTL-006 - Specialist result validation

The Controller MUST validate each specialist result against its expected schema before aggregation.

### ARD-CTL-007 - Conflict detection

The Controller MUST detect material conflicts among specialist findings and MUST preserve the conflicting values and sources.

### ARD-CTL-008 - Missing result handling

The Controller MUST identify incomplete or failed specialist analyses and MUST NOT represent the aggregated package as complete.

### ARD-CTL-009 - Reporting handoff

The Controller MUST send the Report Creation Agent only validated specialist outputs plus explicit missing-data, failure, and conflict metadata.

### ARD-CTL-010 - Workflow completion

The Controller MUST record a terminal workflow status of resolved, escalated, rejected, or awaiting additional data.

## 10. Maintenance Requirements

### ARD-MNT-001 - Maintenance inputs

The Maintenance Agent MUST evaluate aircraft metadata, defect information, maintenance history, work-order state, required actions, engineering constraints, safety conditions, and part dependencies when available.

### ARD-MNT-002 - Deterministic validation

Aircraft identity, required metadata, work-order completeness, standard procedure checks, and safety gates MUST be validated deterministically before final reasoning.

### ARD-MNT-003 - Repairability status

The Maintenance result MUST classify repairability as feasible, uncertain, or not feasible.

### ARD-MNT-004 - Ground-time estimate

The Maintenance result MUST provide an estimated ground time or explicitly state why an estimate cannot be supported.

### ARD-MNT-005 - Maintenance output

The result MUST include required actions, technical risks, assumptions, recommendation, confidence, reasoning, and next steps.

### ARD-MNT-006 - Safety gate

Missing safety or engineering approval MUST prevent a final feasible disposition and MUST cause an advisory or escalated result.

### ARD-MNT-007 - Incomplete work order

Missing required work-order information MUST produce a provisional result and escalation or request for additional information.

### ARD-MNT-008 - Cross-domain discrepancy

A material difference between maintenance recovery time and operations disruption time MUST be recorded as a conflict for Controller adjudication.

## 11. Inventory Requirements

### ARD-INV-001 - Inventory inputs

The Inventory Agent MUST evaluate part number, aircraft compatibility, required quantity, stock quantity, location, transfer state, substitutes, supplier constraints, and lead time when available.

### ARD-INV-002 - Deterministic validation

Stock counts, minimum thresholds, substitution compatibility, location consistency, and structured lead-time calculations MUST be deterministic.

### ARD-INV-003 - Availability status

The Inventory result MUST classify availability as available, limited, unavailable, or uncertain.

### ARD-INV-004 - Practical availability

The Inventory Agent MUST distinguish physical stock from material that is practically usable within the recovery window.

### ARD-INV-005 - Sourcing path

The result MUST identify the primary source, an alternate source when available, whether transfer is required, and expected lead time.

### ARD-INV-006 - Inventory output

The result MUST include risk factors, assumptions, recommendation, confidence, reasoning, and next steps.

### ARD-INV-007 - Stale inventory

Stale or cached inventory data MUST be labeled, MUST reduce confidence, and MUST create a warning in downstream recommendations.

### ARD-INV-008 - Substitution safety

An alternate part MUST NOT be recommended unless the deterministic compatibility rule succeeds.

## 12. Operations Requirements

### ARD-OPS-001 - Operations inputs

The Operations Agent MUST evaluate affected flights, routes, schedules, fleet assignments, candidate substitute aircraft, crew constraints, customer impact, and active disruption conditions when available.

### ARD-OPS-002 - Deterministic validation

Flight and schedule validation, assignment conflicts, fleet availability, and configured disruption thresholds MUST be evaluated deterministically.

### ARD-OPS-003 - Impact classification

The Operations result MUST classify operational impact as low, medium, high, or critical.

### ARD-OPS-004 - Recovery alternatives

The Operations Agent MUST evaluate applicable repair, aircraft swap, reroute, and delay options.

### ARD-OPS-005 - Operations output

The result MUST include affected routes, recovery options, impact estimates, risk factors, assumptions, recommendation, confidence, reasoning, and next steps.

### ARD-OPS-006 - Time-sensitive data

Incomplete or time-sensitive operational data MUST produce a provisional result unless current evidence is sufficient under an explicitly documented policy.

### ARD-OPS-007 - Material customer trade-off

When multiple feasible options have materially different customer impact, the alternatives and trade-offs MUST be shown to the human decision-maker.

### ARD-OPS-008 - Route conflict

A detected route or assignment conflict MUST identify the affected resources and explain why the preferred option is more viable than alternatives.

## 13. Recommendation and Reporting Requirements

### ARD-RPT-001 - Input-package validation

The Report Creation Agent MUST validate the presence, schema, completeness, and contradiction state of specialist outputs before ranking options.

### ARD-RPT-002 - Incomplete package

An incomplete or contradictory input package MUST be identified in the final brief and MUST affect recommendation status and confidence.

### ARD-RPT-003 - Scoring model

Each viable recovery option MUST be scored using this baseline weighting:

| Factor | Weight |
|---|---:|
| Recovery time | 30% |
| Operational impact | 25% |
| Inventory availability | 20% |
| Maintenance feasibility | 15% |
| Cost impact | 5% |
| Risk level | 5% |

### ARD-RPT-004 - Deterministic score calculation

Normalization, weight application, and score aggregation MUST be deterministic, reproducible, and independently testable.

### ARD-RPT-005 - Score transparency

The report MUST show each option's factor scores, applied weights, aggregate score, dominant evidence, assumptions, and uncertainty.

### ARD-RPT-006 - Ranked alternatives

The report MUST include feasible alternatives in relative rank order and MUST explain material trade-offs.

### ARD-RPT-007 - Close-score rule

When the top recovery options are within 2 percentage points of one another, the report MUST present both options and require human selection rather than asserting one as uniquely preferred.

### ARD-RPT-008 - Decision brief

The final brief MUST include decision status, summary, ranked options, trade-offs, risks, assumptions, warnings, confidence, required human action, and a concise recommendation narrative.

### ARD-RPT-009 - No fabricated completeness

The Report Creation Agent MUST NOT invent missing specialist findings or conceal contradictory evidence to complete a report.

### ARD-RPT-010 - Human-readable explanation

The final brief MUST be understandable to a non-technical operational sponsor while retaining enough evidence for technical review.

## 14. Confidence, Escalation, and Approval Requirements

### ARD-GOV-001 - High-confidence threshold

A confidence of 0.70 or greater MAY identify a preferred path, but it MUST still be presented for human approval.

### ARD-GOV-002 - Provisional threshold

A confidence from 0.50 through 0.69 MUST be marked provisional and MUST require human review before action.

### ARD-GOV-003 - Low-confidence threshold

A confidence below 0.50 MUST cause escalation for additional data or explicit human override.

### ARD-GOV-004 - Conflicting evidence

Materially conflicting specialist evidence MUST defer approval and require human adjudication regardless of numeric confidence.

### ARD-GOV-005 - Missing required input

Missing required input MUST produce a missing-data list and MUST NOT be replaced by an unstated assumption.

### ARD-GOV-006 - Human actions

The approval workflow MUST support approve, reject, escalate, and request more information.

### ARD-GOV-007 - Approval record

A human decision record MUST include case ID, selected action, selected option when applicable, reviewer identity or test identity, timestamp, rationale, and the recommendation version reviewed.

### ARD-GOV-008 - Policy enforcement

No confidence score, agent output, test mode, or degraded mode MAY bypass the human-approval boundary.

## 15. Resilience and Failure Requirements

### ARD-RES-001 - Inventory outage

If the Inventory API is unavailable, the workflow MAY use explicitly labeled cached data, MUST reduce confidence, and MUST mark the recommendation as risk-adjusted.

### ARD-RES-002 - Operations timeout

If the Operations service times out, the workflow MAY continue with available evidence but MUST include a warning, identify the missing analysis, and apply the confidence or escalation policy.

### ARD-RES-003 - Agent failure

An agent failure MUST be recorded as a structured failure with the failing component, error category, retryability, and impact on the case.

### ARD-RES-004 - Partial recommendation

A partial recommendation MUST identify which conclusions remain supported and which cannot be established.

### ARD-RES-005 - Retry safety

Retries MUST be bounded and idempotent for the same request identifier.

### ARD-RES-006 - No silent fallback

Fallback data or behavior MUST be visible in agent outputs, the final brief, and the audit trail.

### ARD-RES-007 - Case isolation

A failure in one case MUST NOT corrupt or expose another case's context.

## 16. Security and Safety Requirements

### ARD-SEC-001 - Least privilege

Tools and adapters MUST use the minimum permissions required for their documented function.

### ARD-SEC-002 - Read-only default

External-system adapters MUST be read-only unless a future OpenSpec change explicitly introduces and governs a write operation.

### ARD-SEC-003 - Tool allowlisting

Each agent MUST be limited to an explicit allowlist of tools appropriate to its role.

### ARD-SEC-004 - Input boundary

External data and tool responses MUST be treated as untrusted input and validated before use.

### ARD-SEC-005 - Prompt-injection resistance

Content retrieved from tools MUST NOT be allowed to redefine system policy, authorize tools, weaken human approval, or override the agent's assigned role.

### ARD-SEC-006 - Secret handling

Secrets MUST NOT be committed to source control, embedded in prompts, written to logs, or returned in agent output.

### ARD-SEC-007 - Sensitive logging

Logs MUST avoid unnecessary sensitive operational data and MUST support redaction at defined boundaries.

### ARD-SEC-008 - Safety claims

The system MUST NOT claim that an aircraft is safe or airworthy; it may report the state of documented approvals and evidence.

### ARD-SEC-009 - Audit integrity

Audit records MUST be append-oriented and MUST preserve the recommendation and evidence version presented to the human reviewer.

## 17. Observability Requirements

### ARD-OBS-001 - Structured events

The implementation MUST emit structured events for case intake, validation, routing, tool invocation, agent completion, conflict, fallback, scoring, escalation, and human decision.

### ARD-OBS-002 - Required event fields

Events MUST include timestamp, event type, case ID, trace or correlation ID, component, status, and schema version.

### ARD-OBS-003 - Explainable trajectory

The system MUST preserve the externally observable execution trajectory needed to explain how the final decision was produced.

### ARD-OBS-004 - No hidden reasoning requirement

Traceability MUST rely on inputs, outputs, evidence, decisions, rules, scores, and concise rationale; it MUST NOT require storage or disclosure of private chain-of-thought.

### ARD-OBS-005 - Metrics

The implementation SHOULD expose counts and durations for case processing, tool failures, agent failures, fallbacks, conflicts, and escalations.

## 18. Performance and Operational Requirements

### ARD-NFR-001 - Configurable timeouts

External tool and agent execution timeouts MUST be configurable and MUST have documented defaults.

### ARD-NFR-002 - Bounded execution

Agent loops, retries, and tool calls MUST be bounded to prevent non-terminating workflows.

### ARD-NFR-003 - Deterministic reproducibility

Given identical validated deterministic inputs, scoring and policy gates MUST produce identical results.

### ARD-NFR-004 - Maintainability

Shared contracts, domain logic, adapters, orchestration, reporting, and tests SHOULD remain separate modules with clear ownership.

### ARD-NFR-005 - Portability

The capstone implementation SHOULD run in a documented local development environment without proprietary airline infrastructure.

### ARD-NFR-006 - Configuration

Thresholds, adapter selection, timeouts, and non-secret environment settings MUST be externalized from source code.

### ARD-NFR-007 - Dependency declaration

Runtime and test dependencies MUST be declared and reproducibly installable.

## 19. Verification Requirements

### ARD-TST-001 - Requirement traceability

Every implemented ARD requirement MUST map to at least one OpenSpec scenario, implementation task, or explicit justified deferral.

### ARD-TST-002 - Contract tests

Shared models and every tool adapter MUST have valid-input, invalid-input, and structured-failure tests.

### ARD-TST-003 - Agent tests

Each agent MUST have tests for normal evidence, partial evidence, missing required fields, conflicting evidence, and low confidence.

### ARD-TST-004 - Scoring tests

Tests MUST verify exact score weights, normalization, aggregation, ranking, and the 2-percentage-point close-score rule.

### ARD-TST-005 - Human gate tests

Tests MUST demonstrate that no workflow state or confidence level bypasses human approval.

### ARD-TST-006 - Required functional scenarios

End-to-end validation MUST include:

1. Part and technician available with no schedule conflict produces a repair recommendation for human approval.
2. Required part unavailable with a feasible alternate aircraft produces an aircraft-swap candidate.
3. Inventory unavailable uses labeled cached data, reduces confidence, and displays a warning.
4. Top options within 2 percentage points are both presented for human selection.
5. Conflicting maintenance and operations time estimates produce a provisional or escalated recommendation.

### ARD-TST-007 - Security tests

Tests MUST cover unauthorized tools, malformed external data, prompt-injection content, secret redaction, and read-only adapter behavior.

### ARD-TST-008 - Regression evidence

Known-good scenarios MUST remain executable as regression tests, and validation results MUST be summarized in project artifacts.

### ARD-TST-009 - Test determinism

Mock adapters and fixtures MUST produce deterministic results unless a test explicitly verifies uncertainty or failure behavior.

## 20. Deployment and Readiness Requirements

### ARD-DEP-001 - Environment documentation

The project MUST document supported runtime versions, dependency installation, configuration, required environment variables, and startup commands.

### ARD-DEP-002 - No committed credentials

Deployment and demonstration instructions MUST use placeholders or environment-based secret configuration.

### ARD-DEP-003 - Health verification

The running system MUST provide a documented way to verify readiness of the application and configured adapters.

### ARD-DEP-004 - Backout plan

The project MUST document how to return to the previous known-good version or disable a newly introduced capability.

### ARD-DEP-005 - Readiness evidence

Release readiness MUST include test results, unresolved issues, security considerations, decision rationale, and a RAPID Go/No-Go outcome.

### ARD-DEP-006 - Demonstration readiness

The project MUST include sponsor-facing scenarios that demonstrate business value, explainability, degraded behavior, and human accountability.

## 21. OpenSpec Conformance

### ARD-OSP-001 - Proposal traceability

Every OpenSpec proposal MUST list the ARD requirement IDs it addresses and identify any explicitly out-of-scope ARD requirements.

### ARD-OSP-002 - Design conformance

Every OpenSpec design MUST explain how its architecture satisfies applicable ARD requirements and MUST document any trade-off or deviation.

### ARD-OSP-003 - Specification scenarios

OpenSpec capability specifications MUST use testable scenarios to cover applicable ARD requirements.

### ARD-OSP-004 - Task traceability

Every implementation task MUST cite the OpenSpec requirement or ARD requirement it implements or verifies.

### ARD-OSP-005 - No silent requirement removal

An OpenSpec change MUST NOT remove, weaken, or contradict an ARD requirement without explicitly proposing the ARD change and documenting impact.

### ARD-OSP-006 - Change boundaries

OpenSpec changes SHOULD follow the dependency sequence in `docs/openspec-proposal-prompts.md` unless a proposal justifies a different boundary.

### ARD-OSP-007 - Archive gate

A change SHOULD be archived only after its applicable ARD requirements and OpenSpec scenarios have verification evidence or documented deferrals.

## 22. Capability-to-Requirement Map

| OpenSpec capability area | Primary ARD sections |
|---|---|
| Technology foundation | ARD-TEC, ARD-NFR, ARD-DEP |
| AOG case intake | ARD-DAT, ARD-CTL |
| Shared agent contracts | ARD-DAT |
| Tool contracts | ARD-DAT, ARD-SEC, ARD-RES |
| Decision confidence | ARD-GOV |
| Maintenance assessment | ARD-MNT |
| Inventory sourcing | ARD-INV |
| Maintenance-inventory coordination | ARD-SYS, ARD-MNT, ARD-INV |
| Operations impact analysis | ARD-OPS |
| Recovery orchestration | ARD-CTL, ARD-RES |
| Agent routing | ARD-CTL |
| Case escalation | ARD-GOV |
| Recovery recommendation | ARD-RPT |
| Human approval | ARD-GOV |
| Decision reporting | ARD-RPT, ARD-OBS |
| Workflow resilience | ARD-RES |
| Security and audit | ARD-SEC, ARD-OBS |
| Deployment readiness | ARD-DEP |
| Capstone demonstration | ARD-TST, ARD-DEP |

## 23. Definition of Done

The architecture baseline is satisfied when:

1. OpenSpec specifications cover the applicable ARD requirements.
2. Implemented capabilities conform to versioned typed contracts.
3. Deterministic rules, confidence gates, and scoring are independently tested.
4. All required agents operate through Controller-managed, traceable workflows.
5. Failures, stale data, missing data, and conflicts remain visible.
6. No operational action can occur without human approval.
7. Security, resilience, observability, deployment, and required end-to-end scenarios have verification evidence.
8. The project can demonstrate an explainable recommendation and human decision using deterministic local or mock integrations.
