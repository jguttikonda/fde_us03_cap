# Maintenance Agent Proposal Draft

This document is a detailed draft for the Maintenance Agent and supplements the root system proposal in ../proposal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Maintenance Agent analyzes the failure, assesses repair feasibility, and establishes when an aircraft can return to service by combining the estimated repair duration with parts availability and lead time obtained through direct collaboration with the Materials & Logistics Agent. It also analyzes maintenance history, detects recurring failures, and recommends engineering-preferred replacement parts based on historical repairs. It then reports risk metrics based on the ETA, including ETA confidence and relevant delay, parts-dependency, and repair-complexity risks.

## 2. Role in the System
The Maintenance Agent is a top-level agent called by the Controller to determine the aircraft's return-to-service ETA. It collaborates directly with the Materials & Logistics Agent as a peer (A2A): it shares failure context, maintenance history, and any preferred replacement part, and receives availability, lead-time, and sourcing evidence in return. Every exchange is recorded in the Controller-managed case context. It combines that information with the estimated repair duration and returns the ETA, risk metrics, confidence, and assumptions to the Controller.

## 2A. Handshake with Other Agents
Agent type:    top-level, peer collaboration with the Materials & Logistics Agent
Called by:     Controller (H2: validated event and defect context; asks for repair ETA)
Collaborates:  Materials & Logistics Agent (H3: required and preferred replacement part numbers, failure history, station, and need-by time; H4: availability, lead time, and sourcing comparison)
Payload in and out: H2 event/defect context; H3/H4 replacement-strategy request and availability/lead time; H5 return-to-service ETA, risk metrics, confidence, and assumptions

## 3. Primary Responsibilities
- Failure analysis, repair feasibility, and repair duration estimation
- Historical maintenance analysis and recurring failure detection
- Identify maintenance constraints and engineering recommendations
- Recommend preferred replacement parts based on historical repairs
- Obtain parts availability and lead-time information from the Materials & Logistics Agent
- Establish the return-to-service ETA from repair duration and parts wait
- Report ETA confidence and risk metrics based on the ETA
- Recommend repair versus defer or escalate, with assumptions and constraints

## 4. Non-Deterministic Responsibilities
- Interpret partial or ambiguous maintenance history
- Judge whether a recurring failure pattern justifies recommending an upgraded or alternate replacement part
- Assess how repair-duration and parts-timing uncertainty affect the ETA and its confidence
- Estimate the return-to-service window when repair or supplier timing is uncertain
- Assess delay, parts-dependency, and repair-complexity risks based on the ETA
- Weigh technical feasibility against urgency and schedule pressure when recommending repair, defer, or escalation

## 5. Context Engineering and Memory Management
The Maintenance Agent maintains a technical case memory focused on the active aircraft defect, maintenance state, safety constraints, repair-duration estimates, parts dependencies, ETA assumptions, and risk assessment. It keeps the current evidence window compact and avoids long-term retention of noisy inspection records unless they directly affect the current recovery decision.

- Short-term memory: current aircraft condition, active defect summary, safety gate state, repair-duration estimate, parts status, and current ETA
- Working memory: technical findings, repair and parts-timing assumptions, and dependencies under consideration for the ETA and risk assessment
- Durable local memory: recurring maintenance patterns, standard rule exceptions, and known repair categories for similar defects
- Context compression rule: retain only the maintenance and parts facts that materially affect the ETA, its confidence, risk metrics, and downstream approvals

## 6. LLM Role
The Maintenance LLM acts as the technical feasibility and ETA analyst. It reasons over maintenance context, work-order task details, inspections, engineering notes, and Materials & Logistics results to estimate the repair duration and return-to-service ETA, then assesses risk metrics based on that ETA.

## 7. LLM Prompt Template
This agent should use a short sequence of prompt interactions instead of a single broad technical prompt. The split keeps fact extraction, reasoning, and final validation separate, which improves traceability and reduces context drift.

### 7.1 Prompt A — Maintenance Evidence Grounding
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Your task is to extract only the fact-backed maintenance evidence relevant to the current defect and repair decision.

Inputs you must assess:
- Aircraft defect summary
- Maintenance history and inspection data
- Work-order status and task details
- Known dependencies and technical constraints

Decision rules:
- Keep only facts that materially affect repairability
- Flag missing, stale, or contradictory maintenance evidence that affects repairability or the ETA
- Do not infer technical feasibility without supporting evidence

Return only a structured output with:
1. evidence_summary
2. missing_data
3. assumptions
4. confidence_level
```

### 7.2 Prompt B — Technical Repair Reasoning
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Use the grounded evidence from Prompt A to assess repair feasibility and determine the likely maintenance path.

Inputs you must assess:
- Relevant aircraft condition facts
- Maintenance records and defect history
- Work-order task details and technical constraints
- Materials & Logistics availability, parts-ready ETA, replacement-part comparison, and part dependency requirements

Decision rules:
- Determine whether repair is feasible, uncertain, or not feasible
- Identify the maintenance actions and dependencies required
- Estimate repair duration and combine it with parts wait to establish the return-to-service ETA
- State ETA confidence and assess risk metrics based on the ETA
- Highlight assumptions and technical constraints clearly

Return only a structured output with:
1. repairability_status
2. required_actions
3. estimated_ground_time_hours
4. eta_hours
5. return_to_service_time
6. eta_confidence
7. risk_metrics
8. technical_risks
9. assumptions
```

### 7.3 Prompt C — Final Validation and Output Normalization
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Review the repair recommendation and ensure it is consistent with safety constraints, procedure rules, and the agent’s domain boundaries.

Inputs you must assess:
- Repairability recommendation
- Safety gate state
- Required approvals and dependencies

Decision rules:
- Reject unsupported technical conclusions
- Ensure the output is traceable and ready for downstream use
- Verify that the ETA, confidence, and risk metrics are supported by the stated evidence and assumptions
- Normalize the result into the standard maintenance contract format

Return only a structured output with:
1. final_summary
2. final_recommendation
3. eta_hours
4. return_to_service_time
5. eta_confidence
6. risk_metrics
7. assumptions
8. required_approvals
9. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "Maintenance Agent",
  "repairability_status": "feasible|uncertain|not_feasible",
  "summary": "Short technical assessment of the aircraft condition",
  "required_actions": [
    "Action 1",
    "Action 2"
  ],
  "recurring_failure": {
    "detected": true,
    "occurrences": 3,
    "window_days": 90
  },
  "preferred_replacement_part": {
    "failed_part": "P-110",
    "preferred_part": "P-120",
    "basis": "Engineering notes and historical repairs"
  },
  "estimated_ground_time_hours": 0,
  "eta_hours": 0,
  "return_to_service_time": "ISO-8601 timestamp or stated time window",
  "eta_confidence": 0.0,
  "risk_metrics": {
    "delay_risk": "low|medium|high",
    "parts_dependency_risk": "low|medium|high",
    "repair_complexity_risk": "low|medium|high"
  },
  "technical_risks": [
    "Risk 1",
    "Risk 2"
  ],
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "recommendation": {
    "decision": "repair|defer|escalate|uncertain",
    "confidence": 0.0,
    "reasoning": "Why this recommendation is most credible",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 9. Deterministic Responsibilities
- Validate aircraft condition metadata
- Check required maintenance actions against standard procedures
- Detect missing aircraft identity or defect metadata and obvious data inconsistencies
- Apply safety and approval gates
- Map technical findings into structured repair categories

## 9A. Domain Validation and Conflict Handling
The Maintenance Agent must identify when the technical signal is not consistent enough to support a confident recommendation.

- If maintenance estimates a 3-hour repair but operations indicates a 7-hour disruption, the case is flagged as internally inconsistent
- If defect or maintenance evidence needed to estimate the repair duration is missing, the ETA should be provisional and the missing evidence stated
- If safety or engineering approval is not present, the maintenance recommendation must remain advisory until approved

This ensures the Maintenance Agent contributes technically grounded evidence without overstating confidence.

### 8.1 MCP Configuration for Deterministic Validation
This agent uses MCP-hosted tools to perform deterministic validation steps. The purpose is to ensure the LLM reasons over trustworthy technical inputs.

- `validate_aircraft_metadata`: checks aircraft identity, defect status, and required maintenance context before analysis
- `check_standard_maintenance_rules`: applies maintenance procedure checks and rule-based repair mapping
- `check_safety_gate`: validates whether the technical path is compliant with configured safety restrictions and approval conditions
- `map_repair_category`: converts the technical findings into a standard repair classification used by downstream agents

### 8.2 Domain APIs Reached through MCP Tools
The deterministic validation layer calls the domain APIs that own the source technical facts:

- Aircraft Maintenance API: returns defect history, aircraft status, and technical metadata
- Work Order / Task API: returns repair tasks and required maintenance actions
- Engineering Rules API: provides standard procedures, maintenance constraints, and repair classification logic
- Safety / Approval API: enforces gate checks and returns compliance or exception states
- Part Dependency API: verifies which components and spare dependencies are required for the proposed repair path

### 8.3 Tool Interaction Contract (JSON)
Each tool call captures the exact request/response contract that feeds the deterministic maintenance validation layer.

#### 8.3.1 `validate_aircraft_metadata`
Request JSON:
```json
{
  "aircraft_tail_number": "N123AB",
  "required_fields": ["aircraft_id", "status", "defect_summary", "maintenance_history"],
  "include_history": true
}
```

Response JSON:
```json
{
  "status": "validated",
  "aircraft_id": "N123AB",
  "current_status": "AOG",
  "missing_fields": [],
  "defect_summary": "Hydraulic leak",
  "maintenance_history_count": 7
}
```

#### 8.3.2 `check_standard_maintenance_rules`
Request JSON:
```json
{
  "aircraft_type": "A320",
  "defect_code": "HYD-LEAK",
  "maintenance_context": {
    "station": "MIA",
    "mro_capability": "line-maintenance"
  }
}
```

Response JSON:
```json
{
  "rule_check": "passed",
  "repair_category": "line_repair_supported",
  "required_approvals": ["engineering_approval"],
  "warnings": []
}
```

#### 8.3.3 `check_safety_gate`
Request JSON:
```json
{
  "aircraft_id": "N123AB",
  "defect_code": "HYD-LEAK",
  "repair_plan": {
    "action": "replace_hydraulic_pump",
    "station": "MIA"
  },
  "safety_constraints": ["engineering_approval", "aircraft_grounding_check"]
}
```

Response JSON:
```json
{
  "safety_gate": "passed",
  "approval_required": true,
  "exceptions": [],
  "compliance_status": "ready_for_technical_review"
}
```

#### 8.3.4 `map_repair_category`
Request JSON:
```json
{
  "repair_findings": [
    "hydraulic_pump_failure",
    "seal_kit_required"
  ],
  "aircraft_type": "A320",
  "station_capability": "line-maintenance"
}
```

Response JSON:
```json
{
  "repair_category": "line_repair_supported",
  "ground_time_hours": 8,
  "category_reason": "defect is within line-maintenance capability and replacement parts are available",
  "classification_confidence": 0.91
}
```

## 10. LLM-Facing Inputs
These are the curated, validated facts the LLM should reason over to assess technical repairability. This is the cleaned evidence set produced by the deterministic checks and not a raw maintenance dump.
- Aircraft defect summary and current technical status
- Maintenance history and prior inspections
- Work-order context and repair constraints
- Materials & Logistics availability, parts-ready ETA, replacement-part comparison, and part dependency information relevant to the repair
- Repair-duration estimate and ETA assumptions
- Technical notes, assumptions, and uncertainty in the aircraft record

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the structured system inputs consumed by the agent before the model reasons.
- Aircraft maintenance records and defect logs
- Work-order and task management systems
- Engineering and inspection APIs
- Parts dependency metadata from maintenance systems
- Safety and approval rule sources used for validation

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after evaluating the validated evidence:
- Repair feasibility assessment
- Estimated repair duration and return-to-service ETA
- ETA confidence and risk metrics based on the ETA, including delay, parts-dependency, and repair-complexity risk
- Required maintenance actions and dependencies
- Technical risk and constraint summary
- Recommendation to repair, defer, or escalate

## 13. Tool / External System Outputs
This is the downstream execution handshake: the structured system artifacts generated after the accepted guidance is converted into machine-usable maintenance actions.
- Structured maintenance recommendation payload
- Repair work package summary for operations and planning teams
- Technical risk flags for downstream systems
- Escalation or exception record when confidence is low
- Decision record used by the Controller for final synthesis

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This flow ensures the technical decision is based on verified aircraft evidence and that the resulting maintenance recommendation is traceable to the same facts.

## 13. Validation and Output Evaluation
The Maintenance Agent should validate its output by checking:
- whether the evidence supports the repair conclusion
- whether the recommended actions are technically coherent
- whether there are hidden dependencies not captured in the current context
- whether the ETA reflects both estimated repair duration and Materials & Logistics parts timing
- whether ETA confidence and risk metrics are explicit and supported by the stated assumptions
- whether the output is sufficiently explicit for downstream decision-making

## 14. Questions This Agent Seeks to Answer
- Is the aircraft repairable under the current conditions?
- What failed, and has it happened before?
- Which repair strategy worked previously, and are alternate or upgraded parts recommended?
- What is the estimated repair duration, parts wait, and return-to-service ETA?
- How confident is the ETA, and what risks follow from it?
- What actions, parts, and expertise are required?
- Which technical constraints could prevent the repair path?
- What assumptions support the ETA and recommendation?

## 15. Acceptance Criteria
The Maintenance Agent is successful when it:
- makes a technically credible repair assessment
- establishes the return-to-service ETA from repair duration and parts timing
- reports ETA confidence and risk metrics based on the ETA
- clearly states assumptions and risks
- distinguishes between confirmed feasible and uncertain repair paths
- supports the Controller with actionable maintenance evidence

## 16. Draft Notes
This agent is the technical decision anchor for the aircraft recovery process. It should help determine whether a repair path is realistic, safe, and operationally defensible.
