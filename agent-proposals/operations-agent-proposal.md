# Operations Agent Proposal Draft

This document is a detailed draft for the Operations Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Operations Agent evaluates the business and schedule impact of an AOG event and recommends the operational path that minimizes disruption while remaining feasible.

## 2. Role in the System
This agent focuses on the fleet and network implications of each recovery option. It looks beyond the aircraft itself to understand route disruption, schedule risk, and the cost of delay, rerouting, or substitution.

## 3. Primary Responsibilities
- Evaluate flight and route impact
- Assess aircraft substitution options
- Measure schedule and customer disruption
- Recommend the least-disruptive operational path
- Prioritize recovery actions based on business effect

## 4. Non-Deterministic Responsibilities
- Determine which disruption pattern is most damaging under uncertainty
- Assess whether a delay, reroute, or aircraft swap is the least-bad option
- Balance customer impact against recovery efficiency
- Prioritize among multiple operational options when the trade-off is ambiguous
- Interpret dynamic schedule pressure in business terms

## 5. Context Engineering and Memory Management
The Operations Agent maintains a network-oriented case memory focused on the live disruption, affected flights, fleet constraints, and service-critical context. It keeps only the route and schedule facts needed to assess whether a reroute, swap, delay, or recovery action is feasible without overloading the working context with unrelated planning detail.

- Short-term memory: affected routes, aircraft availability, timing windows, and customer priority context
- Working memory: active operational options, feasibility checks, and service-impact trade-offs under evaluation
- Durable local memory: route patterns, disruption thresholds, and known fleet constraints for similar service events
- Context compression rule: retain only the flight, fleet, and disruption signals that materially affect the operational recommendation

## 6. LLM Role
The Operations LLM acts as the disruption and prioritization analyst. It reasons over flight schedule, fleet availability, crew planning, route dependencies, and operational constraints to determine the most practical recovery strategy.

## 7. LLM Prompt Template
This agent should use a multi-step prompt pattern instead of a single broad operational-impact prompt. The staged structure enables evidence grounding, route trade-off analysis, and final approval-ready normalization without context overload.

### 7.1 Prompt A — Operational Evidence Grounding
```text
You are the Operations Agent for an aircraft AOG recovery workflow.

Your task is to extract only the operational facts that matter for the disruption decision.

Inputs you must assess:
- Flight schedules and route disruptions
- Fleet availability and alternative aircraft candidates
- Crew and station constraints
- Service priority and business impact signals

Decision rules:
- Keep only the facts that materially affect operational feasibility
- Flag missing route, crew, or schedule data
- Do not infer disruption severity without supporting operational signals

Return only a structured output with:
1. evidence_summary
2. missing_data
3. assumptions
4. confidence_level
```

### 7.2 Prompt B — Route and Fleet Trade-Off Reasoning
```text
You are the Operations Agent for an aircraft AOG recovery workflow.

Use the grounded operational evidence from Prompt A to compare feasible recovery paths and determine the least-disruptive option.

Inputs you must assess:
- Affected routes and current fleet capacity
- Maintenance, inventory, and customer-priority constraints
- Recovery options already under consideration

Decision rules:
- Compare swap, reroute, delay, and repair paths by impact and feasibility
- Prefer the least-disruptive path that still works under operational constraints
- Explicitly state the trade-offs and risk assumptions

Return only a structured output with:
1. impacted_routes
2. recovery_options
3. schedule_risk_minutes
4. risk_factors
5. confidence
```

### 7.3 Prompt C — Final Validation and Output Normalization
```text
You are the Operations Agent for an aircraft AOG recovery workflow.

Review the final operational recommendation and confirm it is suitable for Controller handoff and human review.

Inputs you must assess:
- Operational recommendation
- Constraint summary and risk flags
- Final impact rationale

Decision rules:
- Ensure the recommendation is grounded and actionable
- Reject unsupported impact claims or hidden assumptions
- Normalize the result into the standard operations format

Return only a structured output with:
1. final_summary
2. operational_recommendation
3. next_action
4. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "Operations Agent",
  "operational_impact_level": "low|medium|high|critical",
  "summary": "Short summary of the schedule and fleet impact",
  "affected_routes": ["Route 1", "Route 2"],
  "recovery_options": [
    {
      "option": "repair|swap|reroute|delay",
      "estimated_impact": "Low / Medium / High",
      "rationale": "Why this option is plausible"
    }
  ],
  "risk_factors": [
    "Risk 1",
    "Risk 2"
  ],
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "recommendation": {
    "decision": "repair|swap|reroute|delay|escalate",
    "confidence": 0.0,
    "reasoning": "Why this operational path is preferred",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 9. Deterministic Responsibilities
- Validate flight and schedule data
- Detect route conflicts and aircraft assignment issues
- Apply standard substitution rules and disruption thresholds
- Compute basic impact categories and priority logic
- Maintain structured outputs for route and fleet implications

### 8.1 MCP Configuration for Deterministic Validation
Operational validation is performed through a deterministic MCP tool layer before the LLM evaluates disruption and trade-offs.

- `validate_flight_schedule`: ensures route and flight data are complete and structurally valid
- `detect_route_conflicts`: checks overlapping assignments, cancellations, and disruption patterns against the live schedule
- `check_fleet_availability`: validates candidate replacement aircraft and current availability windows
- `apply_disruption_thresholds`: converts schedule and deviation data into standard impact levels
- `format_impact_payload`: produces the structured operational output used for final comparison and decisioning

### 8.2 Domain APIs Reached through MCP Tools
These validation functions are backed by operational data APIs and service feeds:

- Flight Operations API: provides schedule, network, and disruption data for route validation
- Fleet Assignment API: returns aircraft availability and swap feasibility across the network
- Crew Planning API: validates crew availability and station constraints for viable recovery options
- Customer Service Priority API: supplies service-critical route and impact weighting information
- Disruption / Network API: identifies active weather, outage, and route disruption conditions affecting the case

### 8.3 Tool Interaction Contract (JSON)
The deterministic tool layer produces structured operational facts that are then interpreted by the LLM for trade-off reasoning.

#### 8.3.1 `validate_flight_schedule`
Request JSON:
```json
{
  "flight_number": "FX103",
  "route": "MIA-ORD",
  "flight_date": "2026-10-20",
  "include_disruption_context": true
}
```

Response JSON:
```json
{
  "flight_status": "affected",
  "route_status": "disrupted",
  "delay_minutes": 420,
  "affected_segments": ["MIA-ORD"],
  "disruption_reason": "aircraft_AOG"
}
```

#### 8.3.2 `check_fleet_availability`
Request JSON:
```json
{
  "origin": "MIA",
  "destination": "ORD",
  "aircraft_type": "A320",
  "availability_window_hours": 12
}
```

Response JSON:
```json
{
  "aircraft_available": true,
  "candidate_aircraft": ["N980FX"],
  "swap_window_hours": 8,
  "crew_coverage": "available"
}
```

#### 8.3.3 `apply_disruption_thresholds`
Request JSON:
```json
{
  "route_impact_minutes": 420,
  "customer_priority": "high",
  "fleet_capacity_gap": 1
}
```

Response JSON:
```json
{
  "impact_level": "critical",
  "threshold_rule_applied": "customer_critical_plus_delay",
  "priority_score": 92,
  "recommended_action": "reroute_or_swap"
}
```

#### 8.3.4 `detect_route_conflicts`
Request JSON:
```json
{
  "aircraft_id": "N123AB",
  "route": "MIA-ORD",
  "schedule_window": "2026-10-20T12:00:00Z/2026-10-20T22:00:00Z",
  "network_constraints": ["crew_coverage", "slot_availability"]
}
```

Response JSON:
```json
{
  "conflicts_detected": ["crew_coverage_gap", "slot_capacity_shortfall"],
  "conflict_count": 2,
  "route_status": "conflicted"
}
```

#### 8.3.5 `format_impact_payload`
Request JSON:
```json
{
  "affected_routes": ["MIA-ORD"],
  "impact_level": "critical",
  "candidate_actions": ["repair", "swap", "reroute"],
  "summary": "Aircraft AOG creates 7-hour disruption on high-priority route"
}
```

Response JSON:
```json
{
  "structured_impact": {
    "operational_impact_level": "critical",
    "affected_routes": ["MIA-ORD"],
    "recommended_action": "reroute_or_swap",
    "summary": "Aircraft AOG creates 7-hour disruption on high-priority route"
  },
  "format_version": "v1"
}
```

## 10. LLM-Facing Inputs
These are the curated, validated facts the LLM should reason over to assess operational impact. This is the operational interpretation derived from tool-fed schedule and disruption evidence.
- Flight schedules and route dependencies
- Fleet availability and substitute aircraft candidates
- Customer or service-critical flight context
- Crew and operational constraints affecting feasibility
- Route disruption assumptions and schedule sensitivity

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the structured system inputs consumed by the agent before the model reasons.
- Flight operations schedule systems
- Fleet assignment and aircraft availability feeds
- Network disruption and route impact data
- Crew and station planning context
- Customer service priority or service recovery rules

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after evaluating the operational evidence:
- Operational impact summary
- Recovery path comparison
- Schedule disruption estimate
- Fleet substitution recommendation
- Recommended operational action with rationale

## 13. Tool / External System Outputs
This is the downstream execution handshake: the structured operational recommendation generated after the LLM decision is accepted and converted into machine-usable dispatch actions.
- Operational impact payload sent to the Controller
- Flight and fleet adjustment recommendation record
- Customer impact summary or service-priority alert
- Schedule change flag for downstream planning systems
- Final decision context for approval or escalation

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This sequence preserves a clear trail from raw operational data through reasoning to the concrete schedule or reroute decision.

## 13. Validation and Output Evaluation
The Operations Agent should confirm:
- whether the recommendation is consistent with fleet constraints
- whether the effect on service is properly framed
- whether the operational path is realistic under current planning conditions
- whether the decision is actionable for the human approver

## 14. Questions This Agent Seeks to Answer
- Which flights or routes are impacted by the outage?
- Is substitution or rerouting feasible?
- What is the cost of delay, reroute, or alternate recovery?
- Which recovery option minimizes disruption while staying realistic?
- What is the operational impact on schedule reliability and customer commitments?

## 15. Acceptance Criteria
The Operations Agent is successful when it:
- provides a credible operational impact analysis
- highlights schedule trade-offs clearly
- supports the Controller with an operational recommendation that makes sense under disruption
- helps choose the least expensive and least disruptive practical path

## 16. Draft Notes
This agent turns a technical recovery problem into a business recovery decision. It ensures the final recommendation is not only technically possible but also operationally sensible in real-world conditions.
