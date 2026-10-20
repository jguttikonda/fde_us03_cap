# Inventory Agent Proposal Draft

This document is a detailed draft for the Inventory Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Inventory Agent determines whether the required parts and material are available to support the AOG recovery plan and whether alternate sourcing is realistic.

## 2. Role in the System
This agent supports the maintenance path by validating physical and logistical availability. It determines not just whether a part exists, but whether it can be obtained in time and with acceptable material risk.

## 3. Primary Responsibilities
- Part availability checking
- Alternate sourcing evaluation
- Supplier and station feasibility review
- Material readiness assessment
- Part substitution recommendation

## 4. Non-Deterministic Responsibilities
- Interpret stale or incomplete inventory data
- Judge whether alternate parts are operationally acceptable
- Assess supplier reliability and timing risk under uncertainty
- Recommend a path when inventory status is incomplete but time-sensitive
- Balance speed of availability against long-term recovery risk

## 5. Context Engineering and Memory Management
The Inventory Agent keeps a localized, materials-specific memory of the active AOG case. It retains the current part requirements, validation state, supplier constraints, location assumptions, and live risk signals needed for fast material decisions. It does not carry unrelated fleet or maintenance context into its current reasoning window; instead it maintains only the evidence needed to evaluate availability, lead time, and recovery feasibility.

- Short-term memory: part requirements, available stock snapshots, transfer assumptions, and urgent sourcing constraints
- Working memory: list of viable source options, substitution outcomes, and risk flags that are currently being evaluated
- Durable local memory: warehouse rules, known supplier behaviors, and recurring part-compatibility patterns for this domain
- Context compression rule: keep only the part-level facts that affect supply availability, risk, and actionable recommendation

## 6. LLM Role
The Inventory LLM acts as the materials readiness specialist. It interprets inventory data, stock locations, transfer rules, supplier constraints, and likely lead times to assess material readiness.

## 7. LLM Prompt Template
This agent should use a staged prompt model instead of one large material-readiness prompt. The separation keeps evidence extraction, source evaluation, and final validation distinct and makes the recommendation easier to audit.

### 7.1 Prompt A — Inventory Evidence Grounding
```text
You are the Inventory Agent for an aircraft AOG recovery workflow.

Your task is to extract the fact-backed inventory evidence relevant to the current material decision.

Inputs you must assess:
- Part number and stock status
- Location-level availability and transfer constraints
- Supplier and station readiness data
- Alternate-part compatibility facts

Decision rules:
- Keep only the facts that affect material availability and urgency
- Flag missing inventory records, stale stock, or conflicting locational data
- Do not infer supply certainty without evidence

Return only a structured output with:
1. evidence_summary
2. missing_data
3. assumptions
4. confidence_level
```

### 7.2 Prompt B — Sourcing and Availability Reasoning
```text
You are the Inventory Agent for an aircraft AOG recovery workflow.

Use the grounded supply evidence from Prompt A to determine whether the required part can be secured in time and which sourcing path is most realistic.

Inputs you must assess:
- Part availability and transfer constraints
- Supplier readiness and lead times
- Alternate-part compatibility rules
- Urgency and operational timing pressure

Decision rules:
- Distinguish confirmed availability from uncertain or theoretical supply
- Compare primary, alternate, and transfer options clearly
- Recommend the realistic supply path with risk stated explicitly

Return only a structured output with:
1. availability_status
2. sourcing_path
3. lead_time_hours
4. risk_factors
5. confidence
```

### 7.3 Prompt C — Final Validation and Output Normalization
```text
You are the Inventory Agent for an aircraft AOG recovery workflow.

Review the supply recommendation and confirm it aligns with compatibility rules, sourcing constraints, and the output contract expected by the Controller.

Inputs you must assess:
- Material recommendation
- Final lead-time and risk profile
- Upstream inventory and location assumptions

Decision rules:
- Ensure the output is grounded in evidence and clearly bounded
- Reject unsupported assumptions or hidden supplier promises
- Normalize the result into the standard inventory format

Return only a structured output with:
1. final_summary
2. final_recommendation
3. next_action
4. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "Inventory Agent",
  "availability_status": "available|limited|unavailable|uncertain",
  "summary": "Short summary of current material readiness",
  "sourcing_path": {
    "primary": "Primary source or stock location",
    "alternate": "Alternate or backup option",
    "transfer_required": true
  },
  "lead_time_hours": 0,
  "risk_factors": [
    "Risk 1",
    "Risk 2"
  ],
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "recommendation": {
    "decision": "source|transfer|substitute|escalate|delay",
    "confidence": 0.0,
    "reasoning": "Why this source path is most credible",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 9. Deterministic Responsibilities
- Validate stock counts and part-level metadata
- Check minimum availability thresholds
- Apply part substitution and sourcing rules
- Detect missing inventory or location inconsistencies
- Calculate expected lead times from structured data

### 8.1 MCP Configuration for Deterministic Validation
The Inventory Agent uses MCP-connected tools to perform deterministic validation of stock and sourcing data before the model interprets anything.

- `lookup_part_availability`: checks current stock counts, location-level availability, and part status
- `validate_minimum_thresholds`: compares available inventory against configured minimum service thresholds
- `apply_substitution_rules`: ensures compatibility rules and alternate-part logic are evaluated deterministically
- `check_location_consistency`: detects missing inventory records, duplicate locations, or mismatched station data
- `calculate_lead_time`: computes expected delivery windows from structured stock and transfer data

### 8.2 Domain APIs Reached through MCP Tools
The Inventory Agent depends on APIs that provide reliable material facts and constraint data:

- Inventory Management API: returns stock quantities, station stock, and current part availability
- Warehouse / Transfer API: provides transfer records, movement status, and location consistency details
- Alternate Parts Catalog API: validates substitution options and compatibility metadata
- Supplier / Procurement API: returns lead times, shipment constraints, and source readiness information
- Logistics Routing API: helps determine the realistic sourcing path for urgent material fulfillment

### 8.3 Tool Interaction Contract (JSON)
Each tool call performs a deterministic validation step and returns a structured material fact set that can be safely passed to the LLM.

#### 8.3.1 `lookup_part_availability`
Request JSON:
```json
{
  "part_number": "P/N-2047",
  "aircraft_type": "A320",
  "locations": ["MIA", "ATL", "ORD"],
  "include_transfer_status": true
}
```

Response JSON:
```json
{
  "part_number": "P/N-2047",
  "status": "limited",
  "available_quantity": 1,
  "locations": [
    { "location": "MIA", "quantity": 1, "status": "available" },
    { "location": "ATL", "quantity": 0, "status": "unavailable" }
  ],
  "transfer_required": true
}
```

#### 8.3.2 `validate_minimum_thresholds`
Request JSON:
```json
{
  "part_number": "P/N-2047",
  "required_minimum": 2,
  "available_quantity": 1,
  "station": "MIA"
}
```

Response JSON:
```json
{
  "threshold_check": "failed",
  "required_minimum": 2,
  "available_quantity": 1,
  "gap": 1,
  "action_required": "source_or_transfer"
}
```

#### 8.3.3 `apply_substitution_rules`
Request JSON:
```json
{
  "part_number": "P/N-2047",
  "aircraft_type": "A320",
  "alternate_parts": ["P/N-2047A", "P/N-2047B"],
  "compatibility_rules": ["aircraft_model_match", "spec_match"]
}
```

Response JSON:
```json
{
  "substitution_result": {
    "valid_alternates": ["P/N-2047A"],
    "invalid_alternates": ["P/N-2047B"],
    "compatibility_status": "conditionally_valid"
  }
}
```

#### 8.3.4 `check_location_consistency`
Request JSON:
```json
{
  "part_number": "P/N-2047",
  "locations": ["MIA", "ATL", "ORD"],
  "validate_duplicates": true,
  "validate_station_records": true
}
```

Response JSON:
```json
{
  "consistency_status": "warning",
  "duplicate_records": [],
  "missing_station_records": ["ORD"],
  "location_quality": "partial"
}
```

#### 8.3.5 `calculate_lead_time`
Request JSON:
```json
{
  "part_number": "P/N-2047",
  "source_location": "ATL",
  "destination_location": "MIA",
  "shipment_mode": "air_freight",
  "supplier_priority": "preferred"
}
```

Response JSON:
```json
{
  "estimated_lead_time_hours": 14,
  "confidence": 0.82,
  "source_ready": true,
  "eta_window": "2026-10-21T06:00:00Z"
}
```

## 10. LLM-Facing Inputs
These are the curated, validated facts the LLM should reason over to evaluate material readiness. This is the evidence set derived from the deterministic tool checks and not a raw system dump.
- Part number, specification, and usage context
- Stock quantity, location, and current availability
- Alternate part mappings and substitution suitability
- Supplier or station readiness notes and constraints
- Lead time and transfer assumptions for the shipment path

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the machine-readable inventory and supply facts collected through MCP tools and domain APIs before the model reasons.
- Inventory and warehouse service data
- Stock movement and transfer records
- Supplier and station availability feeds
- Alternate-part catalog and compatibility metadata
- Procurement or logistics workflow data

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after it has evaluated the curated data:
- Part availability status
- Alternate sourcing recommendation
- Lead-time estimate and supply risk summary
- Material readiness verdict
- Recommended sourcing path under urgency constraints

## 13. Tool / External System Outputs
This is the downstream execution handshake: the structured result generated after the recommendation is accepted and translated into machine-usable artifacts for the Controller, procurement system, or operational workflow.
- Material readiness status payload
- Procurement or transfer task recommendation
- Supplier escalation record if necessary
- Risk flag for missing or uncertain inventory data
- Decision summary passed to the Controller and Maintenance Agent

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This sequence ensures the model reasons from verified inventory evidence and that every downstream action remains traceable to the same case context.

## 13. Validation and Output Evaluation
The Inventory Agent should confirm:
- whether the part is truly available or only theoretically available
- whether alternate sources are acceptable for the aircraft configuration
- whether the part can be delivered within the needed time window
- whether the recommendation is realistic under operational pressure

## 14. Questions This Agent Seeks to Answer
- Is the required part available right now?
- Can it be transferred or sourced elsewhere?
- How long will that take?
- Is an alternate replacement feasible without increasing risk?
- Which material path best supports the preferred recovery option?

## 15. Acceptance Criteria
The Inventory Agent is successful when it:
- distinguishes actual availability from theoretical availability
- provides a practical sourcing path for the required materials
- identifies risk or delay early enough for decision-making
- supports a realistic recovery plan instead of a purely ideal one

## 16. Draft Notes
This agent is essential when the aircraft is technically repairable but the part is the bottleneck. Its value is in materially grounded decision support for urgent recovery actions.
