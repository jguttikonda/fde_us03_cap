# Controller Agent Proposal Draft

This document is a detailed draft for the Controller Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Controller Agent is the orchestration layer for the AOG recovery workflow. It receives the incoming aircraft ground event, determines which specialist agents are required, coordinates the information flow, and produces the final recommendation for human approval. It addresses the business problem that no single system gives a consolidated view of an AOG event: the Controller gathers the partial views held by Maintenance, Materials, Logistics, and Operations into one explainable decision package, replacing manual coordination under time pressure.

## 2. Role in the System
The Controller Agent is not a domain specialist. It is the workflow director that:
- validates the event and scope
- routes the case to the relevant agents
- aggregates intermediate outcomes
- resolves conflicts across specialist recommendations
- produces the final decision package for the human approver

## 3. Primary Responsibilities
- Event intake and validation
- Case triage and routing
- Shared context management
- Coordination across the maintenance, inventory, and operations branches
- Final recommendation synthesis
- Deterministic final report assembly (ranking, templating, confidence labelling) using fixed rules, see Section 9C
- Human handoff and escalation logic

## 4. Non-Deterministic Responsibilities
- Interpret incomplete or conflicting signals across domains
- Decide which agent output is most influential for this case
- Prioritize the response path when multiple valid options exist
- Combine technical, material, and operational findings into a coherent recommendation
- Explain uncertainty and confidence when the decision is not fully deterministic

## 5. Context Engineering and Memory Management
The Controller Agent keeps only the shared, decision-critical context needed to coordinate the AOG workflow. It maintains a compact case memory that includes the current incident state, active specialist outputs, unresolved contradictions, approval gate status, and the final synthesis state. It does not retain every raw domain payload; instead, it stores the curated summary needed for routing and final decision-making.

- Short-term memory: current case state, active specialist outputs, missing or conflicting facts, and approval status
- Working memory: the evidence set being weighed for the final recommendation
- Durable local memory: routing rules, escalation policy, and reusable coordination patterns for similar AOG cases
- Context compression rule: only retain the signals that affect the current decision and the final human review package

## 6. LLM Role
The Controller LLM acts as the coordination planner. It should not own every technical detail from each specialist domain. Instead, it reasons over the shared state and decides what matters most for the current AOG decision.

## 7. LLM Prompt Template
This agent should be implemented as a small sequence of bounded prompts rather than one large synthesis prompt. The split allows the model to first ground evidence, then coordinate decisions, and finally validate the output for approval readiness.

### 7.1 Prompt A — Context Grounding and Shared-State Extraction
```text
You are the Controller Agent for an aircraft AOG recovery workflow.

Your task is to extract only the fact-backed coordination context needed to decide which specialist analysis is still relevant.

Inputs you must assess:
- AOG event summary
- Aircraft technical context
- Current specialist outputs
- Approval and escalation status

Decision rules:
- Keep only the facts that affect the current recovery decision
- Flag contradictions, missing data, or unresolved dependencies
- Do not infer specialist conclusions that are not supported by evidence

Return only a structured output with:
1. shared_state_summary
2. missing_data
3. contradictions
4. confidence_level
```

### 7.2 Prompt B — Coordination Decision and Routing Logic
```text
You are the Controller Agent for an aircraft AOG recovery workflow.

Using the grounded case state, decide which recovery path is most credible and which specialist findings deserve priority.

Inputs you must assess:
- Maintenance findings
- Inventory readiness findings
- Operations impact assessment
- Human approval constraints

Decision rules:
- Prioritize the most relevant data for the current case
- Resolve conflicting domain outputs before selecting the recommended path
- Keep the decision explainable to a human approver

Return only a structured output with:
1. relevant_specialists
2. ranked_recovery_options
3. decision_rationale
4. key_risks
5. confidence
```

### 7.3 Prompt C — Approval-Ready Finalization
```text
You are the Controller Agent for an aircraft AOG recovery workflow.

Review the recommended recovery path and ensure it is suitable for human approval and downstream routing.

Inputs you must assess:
- Final recommendation
- Ranked options produced by the deterministic report builder (Section 9C)
- Approval and governance constraints
- Known assumptions and unresolved risks

Decision rules:
- Do not change the ranking produced by the deterministic report builder; only explain it
- Ensure the recommendation is traceable and reviewable
- Keep the final message concise and decision-ready
- Normalize the output into the standard controller format

Return only a structured output with:
1. case_status
2. final_recommendation
3. next_action
4. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "Controller Agent",
  "case_status": "active|resolved|escalated",
  "summary": "Short narrative of the current AOG decision context",
  "relevant_agents": ["Maintenance Agent", "Inventory Agent", "Operations Agent"],
  "key_findings": [
    "Finding 1",
    "Finding 2"
  ],
  "ranked_options": [
    {
      "rank": 1,
      "option": "repair|substitute|transfer|delay|escalate",
      "return_to_service_hours": 0.0,
      "affected_flights": ["Flight 1"],
      "affected_packages": {"total": 0, "priority": 0},
      "risk_metrics": ["Metric 1"],
      "trade_off": "One sentence built from the fields above"
    }
  ],
  "recommended_recovery_path": {
    "option": "repair|substitute|transfer|delay|escalate",
    "confidence": 0.0,
    "rationale": "Why this option is preferred",
    "assumptions": ["Assumption 1", "Assumption 2"],
    "risks": ["Risk 1", "Risk 2"]
  },
  "human_approval_required": true,
  "next_action": "What the human decision-maker should do next"
}
```

## 9. Deterministic Responsibilities
- Validate that an AOG event contains the required fields
- Check whether required data sources are available
- Apply workflow routing rules
- Enforce escalation thresholds and approval gates
- Standardize output schema and final summary structure
- Check that the Maintenance output (ETA and risk metrics) and the Operations output are both present before a report is built
- Rank the recovery options with a written, fixed scoring rule (Section 9C)
- Apply the final report template: option, time back in service, affected flights and packages, risk metrics, trade-off, assumptions, confidence label
- Assign status categories (feasible, high-risk, deferred) and apply the confidence thresholds in Section 9A

## 9A. Confidence Thresholds and Escalation Rules
The Controller Agent is responsible for translating specialist findings into a final decision posture. It must stop the workflow from auto-approving low-confidence recommendations.

- Confidence >= 70%: proceed with the recommended path and present the rationale to the human approver
- Confidence 50% to 69%: mark the recommendation as provisional and require human review before action
- Confidence < 50%: escalate for additional data collection or manual override
- Conflicting inputs across specialists: defer approval, surface the conflict, and require the human decision-maker to adjudicate

This policy ensures the final decision remains explainable, auditable, and operationally safe even when one domain signal is uncertain.

## 9B. Fallback Handling for Partial Agent Failures
When one of the specialist agents cannot complete its analysis, the Controller should keep the case moving without pretending the result is fully complete.

- Inventory API unavailable: use cached inventory data, reduce confidence, and mark the recommendation as risk-adjusted
- Operations API timeout: continue with the remaining agents and include a clear warning in the final brief
- Maintenance and Operations disagree materially: escalate the case because the conflict affects the overall recommendation
- Missing required inputs: do not assume a route; return the case to the human approver with the missing-data list

The Controller should always preserve a traceable explanation of what was missing, what was substituted, and what remains uncertain.

## 9C. Deterministic Final Report Assembly
The Controller builds the final recovery recommendation report itself. There is no separate Report Creation Agent. Assembly is rule-based and repeatable: the same inputs always produce the same ranked report.

Steps:
1. Completeness check: the Maintenance output (return-to-service ETA, risk metrics, confidence) and the Operations output (affected flights, affected packages when provided, swap options) must both be present. If one is missing, apply Section 9B and mark the report provisional.
2. Build the options: for each recovery option (Repair Now, Transfer Part, Swap Aircraft, Delay Flight) collect time back in service, affected flights, affected packages, risk metrics and confidence.
3. Rank with a fixed rule. Default rule: fewest affected flights first, then fastest return to service, then fewest priority packages at risk. If two options are within 2% of each other on the ranking measure, present both with their trade-offs and require the human to choose. The rule is a team decision and is changed here only.
4. Label: assign a status (feasible, high-risk, deferred) and a confidence label using the thresholds in Section 9A.
5. Fill the report template (below). Every sentence comes from template fields; the Controller LLM explains the result but does not re-rank it.
6. Approval gate: the report is advisory only, requires human approval before any action, and is stored with an audit record.

Report template:
```text
Recovery options for <aircraft_id> (<event_id>)

<rank>. <option>   (RECOMMENDED on rank 1)
   - Back in service: <time> (about <hours> hours)
   - Affected flights: <list or none>
   - Affected packages: <total / priority, when provided by Operations>
   - Risk metrics: <from Maintenance>
   - Trade-off: <sentence built from the fields above>

Assumptions: <list>
Confidence: <label>    Status: <feasible|high-risk|deferred>
Advisory only. Human approval is required before any action.
```

### 8.1 MCP Configuration for Deterministic Validation
The Controller Agent relies on a narrow MCP tool layer to carry out the deterministic checks that must happen before reasoning begins. These tools are configured as reusable validation adapters and are not used to replace domain judgment.

- `validate_case_schema`: verifies required event fields, aircraft identifiers, and incident metadata before a case is routed
- `check_required_sources`: confirms the connected sources for maintenance, inventory, and operations are available and healthy
- `route_case_policy`: applies the deterministic routing rules to decide which specialist agents are required
- `enforce_approval_gate`: checks escalation thresholds and human-approval constraints before finalization
- `standardize_case_output`: converts validated results into the shared controller result schema used across the workflow

### 8.2 Domain APIs Reached through MCP Tools
These deterministic checks are executed through MCP-connected tools that call the relevant domain APIs in a controlled and auditable way:

- AOG Event Intake API: receives the aircraft incident payload and validates required case metadata
- Maintenance Status API: confirms aircraft and work-order data is present before routing the case
- Inventory Availability API: verifies whether part-source data is connected and complete enough to support downstream analysis
- Flight Operations API: checks whether schedule and fleet inputs are present for risk and disruption evaluation
- Governance / Approval API: enforces approval gating, escalation thresholds, and policy enforcement rules

### 8.3 Tool Interaction Contract (JSON)
Each tool call includes an explicit payload shape for both the request sent to the API and the response returned to the agent. This keeps validation fully deterministic and auditable.

#### 8.3.1 `validate_case_schema`
Request JSON:
```json
{
  "case_id": "AOG-2026-1001",
  "aircraft_tail_number": "N123AB",
  "event_type": "AOG",
  "required_fields": ["aircraft_id", "defect_summary", "location", "timestamp"],
  "payload": {
    "defect_summary": "Hydraulic leak",
    "location": "MIA",
    "timestamp": "2026-10-20T15:40:00Z"
  }
}
```

Response JSON:
```json
{
  "status": "valid",
  "missing_fields": [],
  "schema_version": "v1",
  "validated_at": "2026-10-20T15:41:00Z"
}
```

#### 8.3.2 `check_required_sources`
Request JSON:
```json
{
  "case_id": "AOG-2026-1001",
  "source_types": ["maintenance", "inventory", "operations", "approval"],
  "required_status": "healthy"
}
```

Response JSON:
```json
{
  "source_status": {
    "maintenance": "healthy",
    "inventory": "healthy",
    "operations": "healthy",
    "approval": "healthy"
  },
  "missing_sources": [],
  "all_available": true
}
```

#### 8.3.3 `route_case_policy`
Request JSON:
```json
{
  "case_id": "AOG-2026-1001",
  "event_type": "AOG",
  "domain_signals": {
    "maintenance": true,
    "inventory": true,
    "operations": true
  }
}
```

Response JSON:
```json
{
  "routing_decision": {
    "required_agents": ["Maintenance Agent", "Inventory Agent", "Operations Agent"],
    "priority": "high",
    "reason": "technical, material, and operational analysis required"
  }
}
```

#### 8.3.4 `enforce_approval_gate`
Request JSON:
```json
{
  "case_id": "AOG-2026-1001",
  "severity": "high",
  "approval_threshold": "ops_lead_required",
  "current_decision_state": "pending"
}
```

Response JSON:
```json
{
  "approval_status": "required",
  "gate_passed": false,
  "approver_role": "ops_lead",
  "required_action": "human_approval"
}
```

#### 8.3.5 `standardize_case_output`
Request JSON:
```json
{
  "case_id": "AOG-2026-1001",
  "routing_decision": {
    "required_agents": ["Maintenance Agent", "Inventory Agent", "Operations Agent"]
  },
  "summary": "Hydraulic leak with part constraint and schedule disruption"
}
```

Response JSON:
```json
{
  "case_status": "active",
  "controller_output": {
    "case_id": "AOG-2026-1001",
    "summary": "Hydraulic leak with part constraint and schedule disruption",
    "relevant_agents": ["Maintenance Agent", "Inventory Agent", "Operations Agent"]
  },
  "schema_version": "v1"
}
```

## 10. LLM-Facing Inputs
These are the curated, validated facts the LLM should reason over to make coordination decisions. This is the assembled controller view after deterministic checks and specialist outputs have been filtered for relevance.
- AOG event details and recovery objective
- Aircraft status and current maintenance context
- Inventory availability and readiness signals
- Operational disruption and schedule impact summaries
- Inter-agent findings and unresolved contradictions
- Human approval constraints and escalation policy

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the structured inputs the agent receives from MCP tools or system integrations before the LLM reasons over the case.
- Event payload from operations or monitoring systems
- Maintenance work-order and aircraft status APIs
- Inventory service data for parts and stock status
- Flight schedule and fleet disruption feeds
- Audit, approval, or governance system metadata

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as final reasoning and recommendation artifacts after evaluating the assembled case evidence:
- Routing plan for the active AOG case
- Consolidated interpretation of specialist outputs
- Plain-language explanation of the ranked options and the recommended path, based on the fields of the deterministic report (Section 9C)
- Flags for ambiguity, risk, and required escalation

## 13. Tool / External System Outputs
This is the downstream execution handshake: the structured system artifacts generated after the accepted recommendation is converted into machine-usable control-plane actions.
- Structured case status updates
- Coordinator summary payload passed to downstream services
- Ranked recommendation report produced by the deterministic ranking rule and template (Section 9C)
- Human review package or decision brief
- Approval workflow trigger and escalation actions
- Audit record of reasoning, data sources, and final recommendation

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This sequence keeps the controller logic grounded in validated context and makes every downstream orchestration action traceable to the original case evidence.

## 13. Validation and Output Evaluation
Before sending the final recommendation downstream, the Controller should evaluate:
- completeness of specialist inputs
- consistency across specialist outputs
- missing assumptions or contradictions
- confidence level of the recommended path
- readability and traceability of the final report

## 14. Questions This Agent Seeks to Answer
- What is the real decision problem in this AOG case?
- Which specialist agents are relevant?
- Which findings should be considered high priority?
- What is the best-recommended recovery path?
- What should be presented to the human approver for final decision-making?

## 15. Acceptance Criteria
The Controller Agent is successful when it:
- routes the case correctly
- preserves shared context across agents
- brings together the right domain outputs
- produces a recommendation that is explainable and reviewable
- assembles a complete, repeatable, rule-based ranked report without a separate report agent
- supports human approval rather than bypassing it

## 16. Draft Notes
This agent is the coordination layer, not the technical decision-maker. Its core value is structured orchestration and clear, rule-based reporting: the final ranked report is assembled deterministically by the Controller (Section 9C), not by a separate Report Creation Agent.
