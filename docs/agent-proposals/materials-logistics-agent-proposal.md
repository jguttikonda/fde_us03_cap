# Materials & Logistics Agent Proposal Draft

This document is a detailed draft for the Materials & Logistics Agent and supplements the root system proposal in ../proposal.md. This agent merges the former Inventory Agent and Logistics scope into one agent (see ADR-001 in ../proposal.md); the two MAY be split into independent agents in a future release.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Materials & Logistics Agent determines whether required parts and material are available, evaluates alternate and approved substitute parts, plans realistic sourcing (internal transfer or vendor purchase) and shipping, and calculates the parts-ready ETA. It answers whether the part is available locally, at another station, or through a supplier; whether it should be transferred, borrowed, purchased, or expedited; and which approved alternate or engineering-authorized replacements and transport options exist, within inventory, logistics, and approved-part constraints. It collaborates directly with the Maintenance Agent as a peer so that the question is not only "Do we have the part?" but "What is the most appropriate replacement strategy given maintenance history and part availability?"

## 2. Role in the System
The Materials & Logistics Agent is a top-level specialist agent called by the Controller and a direct collaboration peer of the Maintenance Agent. Maintenance shares failure context, maintenance history, and any preferred replacement part; this agent evaluates the original and the preferred replacement part (availability, lead time, inventory locations, transfer options, shipping) before responding. Every exchange with Maintenance is recorded in the Controller-managed case context. It does not communicate with the Operations Agent directly.

## 2A. Handshake with Other Agents
Agent type:    top-level specialist, peer of Maintenance
Called by:     Controller (routing and workflow) and Maintenance (A2A replacement-strategy request, H3)
Calls:         none (reads inventory, supplier, and logistics data through its tools)
Returns to:    Maintenance (H4, A2A response) and Controller (consolidated result via the case context)

## 3. Primary Responsibilities
- Inventory lookup and part availability checking
- Alternate part and approved substitute lookup
- Internal transfer analysis
- Vendor sourcing and procurement evaluation
- Shipping analysis and logistics planning
- ETA calculation
- Supplier and station feasibility review
- Material readiness assessment
- Part substitution and replacement-strategy recommendation

## 4. Non-Deterministic Responsibilities
- Interpret stale or incomplete inventory data
- Judge whether alternate, substitute, or upgraded parts are operationally acceptable
- Assess supplier and carrier reliability and timing risk under uncertainty
- Recommend the best sourcing strategy (transfer, purchase, borrow, expedite) when status is incomplete but time-sensitive
- Balance speed of availability against long-term recovery risk, including recurring-failure history provided by Maintenance

## 5. Context Engineering and Memory Management
The Materials & Logistics Agent keeps a localized, materials-specific memory of the active AOG case. It retains the current part requirements, the maintenance findings and preferred replacement shared by Maintenance, validation state, supplier and carrier constraints, location assumptions, and live risk signals needed for fast material decisions. It does not carry unrelated fleet or maintenance context into its current reasoning window; instead it maintains only the evidence needed to evaluate availability, lead time, shipping, and recovery feasibility.

- Short-term memory: part requirements, available stock snapshots, transfer assumptions, and urgent sourcing constraints
- Working memory: list of viable source options, substitution outcomes, and risk flags that are currently being evaluated
- Durable local memory: warehouse rules, known supplier behaviors, and recurring part-compatibility patterns for this domain
- Context compression rule: keep only the part-level facts that affect supply availability, risk, and actionable recommendation

## 6. LLM Role
The Materials & Logistics LLM acts as the materials and sourcing specialist. It interprets inventory data, stock locations, transfer rules, supplier and vendor constraints, shipping options, and likely lead times, together with the maintenance history shared by the Maintenance Agent, to assess material readiness and the most appropriate replacement strategy.

## 7. LLM Prompt Template
This agent should use a staged prompt model instead of one large material-readiness prompt. The separation keeps evidence extraction, source evaluation, and final validation distinct and makes the recommendation easier to audit.

### 7.1 Prompt A — Materials Evidence Grounding
```text
You are the Materials & Logistics Agent for an aircraft AOG recovery workflow.

Your task is to extract the fact-backed inventory and logistics evidence relevant to the current material decision.

Inputs you must assess:
- Part number and stock status, for the failed part and any preferred replacement shared by Maintenance
- Location-level availability and transfer constraints
- Supplier, vendor, and station readiness data
- Alternate and approved-substitute compatibility facts

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
You are the Materials & Logistics Agent for an aircraft AOG recovery workflow.

Use the grounded supply evidence from Prompt A to determine whether the required part, or the preferred replacement part proposed by Maintenance, can be secured in time and which sourcing and shipping path is most realistic.

Inputs you must assess:
- Part availability and transfer constraints
- Supplier readiness, shipping options, and lead times
- Alternate-part and approved-substitute compatibility rules
- Urgency and operational timing pressure

Decision rules:
- Distinguish confirmed availability from uncertain or theoretical supply
- Compare primary, alternate, replacement, transfer, and vendor options clearly
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
You are the Materials & Logistics Agent for an aircraft AOG recovery workflow.

Review the supply recommendation and confirm it aligns with compatibility rules, sourcing constraints, and the output contract expected by Maintenance and the Controller.

Inputs you must assess:
- Material recommendation
- Final lead-time and risk profile
- Upstream inventory and location assumptions

Decision rules:
- Ensure the output is grounded in evidence and clearly bounded
- Reject unsupported assumptions or hidden supplier promises
- Normalize the result into the standard materials and logistics format

Return only a structured output with:
1. final_summary
2. final_recommendation
3. next_action
4. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "Materials & Logistics Agent",
  "availability_status": "available|limited|unavailable|uncertain",
  "summary": "Short summary of current material readiness",
  "sourcing_path": {
    "primary": "Primary source or stock location",
    "alternate": "Alternate or backup option",
    "method": "internal_transfer|vendor_purchase|borrow|expedite",
    "shipping_source": "fedex_network_priority_freight|fedex_network_courier|commercial_carrier",
    "estimated_cost_usd": 0,
    "eta_hours": 0,
    "transfer_required": true
  },
  "part_authorization": {
    "authorized": true,
    "traceability_verified": true,
    "checked_by_role": "Materials Inventory Specialist"
  },
  "replacement_comparison": [
    {
      "part_number": "P-110",
      "role": "failed_part",
      "available_quantity": 0,
      "lead_time_hours": 0
    },
    {
      "part_number": "P-120",
      "role": "preferred_replacement",
      "available_quantity": 0,
      "lead_time_hours": 0
    }
  ],
  "stock_per_station": [
    {
      "station": "MIA",
      "available_quantity": 0
    }
  ],
  "transfer_hours": 0,
  "alternates": ["P/N-2047A"],
  "supplier_lead_time_hours": 0,
  "parts_ready_eta": "ISO-8601 timestamp or stated time window",
  "lead_time_hours": 0,
  "confidence": 0.0,
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
- Calculate expected lead times, shipping transit times, and ETA from structured data
- Compare the failed part and any preferred replacement part on availability, lead time, and location
- Verify part authorization and traceability (Materials Inventory Specialist check); an unauthorized part makes the option non-compliant
- Price each sourcing method and shipping source (FedEx network priority freight/courier and commercial carriers, mock cost and ETA) as estimated_cost in USD
### 8.1 MCP Configuration for Deterministic Validation
The Materials & Logistics Agent uses MCP-connected, read-only tools to perform deterministic validation of stock, sourcing, and shipping data before the model interprets anything.

- `lookup_part_availability`: checks current stock counts, location-level availability, and part status
- `validate_minimum_thresholds`: compares available inventory against configured minimum service thresholds
- `apply_substitution_rules`: ensures compatibility rules and alternate-part logic are evaluated deterministically
- `check_location_consistency`: detects missing inventory records, duplicate locations, or mismatched station data
- `calculate_lead_time`: computes expected delivery windows, including shipping transit time, from structured stock and transfer data

### 8.2 Domain APIs Reached through MCP Tools
The Materials & Logistics Agent depends on read-only APIs that provide reliable material facts and constraint data:

- Inventory Management API: returns stock quantities, station stock, and current part availability
- Warehouse / Transfer API: provides transfer records, movement status, and location consistency details
- Alternate Parts Catalog API: validates substitution options and compatibility metadata
- Supplier / Procurement API: returns vendor lead times, shipment constraints, and source readiness information
- Logistics Routing API: determines the realistic shipping and sourcing path for urgent material fulfillment

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
- Failure context, recurring-failure history, and preferred replacement part shared by Maintenance
- Stock quantity, location, and current availability
- Alternate and approved-substitute part mappings and suitability
- Supplier, vendor, or station readiness notes and constraints
- Lead time, shipping, and transfer assumptions for the shipment path

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the machine-readable inventory, supply, and logistics facts collected through MCP tools and domain APIs before the model reasons.
- Inventory and warehouse service data
- Stock movement and transfer records
- Supplier, vendor, and station availability feeds
- Alternate-part catalog and compatibility metadata
- Procurement, shipping, and logistics workflow data

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after it has evaluated the curated data:
- Part availability status
- Alternate, substitute, or replacement sourcing recommendation
- Lead-time and ETA estimate and supply risk summary
- Material readiness verdict
- Recommended sourcing and shipping path under urgency constraints

## 13. Tool / External System Outputs
This is the downstream handoff to Maintenance and the Controller: the structured result generated after the recommendation is accepted and translated into machine-usable material-readiness information.
- Material readiness status payload
- Procurement or transfer task recommendation (advisory only; no operational action is performed)
- Supplier escalation record if necessary
- Risk flag for missing or uncertain inventory data
- Decision summary, including parts-ready ETA and confidence, returned to Maintenance and recorded in the case context

### Handshake Chain
Maintenance (H3) <-> Materials & Logistics Agent (H4), recorded in the Controller case context

Worked example: Maintenance reports that Hydraulic Pump P-110 failed, that a similar failure occurred 3 times in 90 days, and that engineering notes recommend the upgraded P-120. The Materials & Logistics Agent evaluates P-110 availability, P-120 availability, lead times, inventory locations, and transfer options before responding with a replacement-strategy comparison. Maintenance combines the parts-ready ETA with repair duration.

## 13. Validation and Output Evaluation
The Materials & Logistics Agent should confirm:
- whether the part is truly available or only theoretically available
- whether alternate, substitute, or preferred replacement parts are acceptable for the aircraft configuration
- whether the part can be delivered within the needed time window
- whether the recommendation is realistic under operational pressure

## 14. Questions This Agent Seeks to Answer
- Do we have the part?
- Are there approved alternatives, and where are the parts?
- Can inventory be transferred?
- How fast can it be delivered?
- What is the best sourcing strategy?
- Which material path best supports the preferred recovery option?

## 15. Acceptance Criteria
The Materials & Logistics Agent is successful when it:
- distinguishes actual availability from theoretical availability
- provides a practical sourcing, shipping, and ETA plan for the required materials
- evaluates both the failed part and the preferred replacement when Maintenance supplies one
- identifies risk or delay early enough for decision-making
- supports a realistic recovery plan instead of a purely ideal one

## 16. Draft Notes
This agent is essential when the aircraft is technically repairable but the part is the bottleneck. Its value is in materially grounded decision support for urgent recovery actions. It combines the former Inventory and Logistics scope per ADR-001; if scale requires it, these can be separated into independent agents in a future release.
