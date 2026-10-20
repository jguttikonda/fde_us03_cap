# Operations Agent Proposal Draft

This document is a detailed draft for the Operations Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Operations Agent measures how an AOG event disrupts flights and the packages that ride on them, and recommends the least harmful operational path.

## 2. Role in the System
This agent focuses on the fleet, network, and package implications of each recovery option. It looks beyond the aircraft itself to understand route disruption, schedule risk, package service commitments, and the cost of delay, rerouting, or substitution.

## 2A. Handshake with Other Agents
```text
Agent type:    top-level
Called by:     Controller (H6)
Calls:         none
Returns to:    Controller (H7)
```

## 3. Primary Responsibilities
- Evaluate flight and route impact
- Assess aircraft substitution options
- Measure schedule and customer disruption
- Recommend the least-disruptive operational path
- Prioritize recovery actions based on business effect
- Identify packages affected by disrupted flights
- Assess exposure of time-critical and priority packages
- Identify service commitments at risk and summarize the likely customer impact

## 4. Non-Deterministic Responsibilities
- Determine which disruption pattern is most damaging under uncertainty
- Assess whether a delay, reroute, or aircraft swap is the least-bad option
- Balance customer impact against recovery efficiency
- Prioritize among multiple operational options when the trade-off is ambiguous
- Interpret dynamic schedule pressure in business terms
- Decide which disruption matters most when flight delay and package service risk point in different directions
- Choose between holding packages for a delayed aircraft, moving them to another flight, or swapping the aircraft when the available metrics do not determine a clear choice
- Weigh a small number of high-priority packages against a larger number of standard packages
- Judge how much schedule slack the network has when recovery ETAs are uncertain
- Explain package and customer impacts in plain business language

## 5. Context Engineering and Memory Management
The Operations Agent maintains a network-oriented case memory focused on the live disruption, affected flights and packages, fleet constraints, and service-critical context. It keeps only the route, schedule, and package facts needed to assess whether a reroute, swap, delay, or recovery action is feasible without overloading the working context with unrelated planning detail.

- Short-term memory: affected routes and packages, aircraft availability, timing windows, and customer priority context
- Working memory: active operational options, feasibility checks, and service-impact trade-offs under evaluation
- Durable local memory: route patterns, disruption thresholds, and known fleet constraints for similar service events
- Context compression rule: retain only the flight, fleet, package, and disruption signals that materially affect the operational recommendation

## 6. LLM Role
The Operations LLM acts as the disruption and prioritization analyst. It reasons over flight schedules, fleet availability, crew planning, route dependencies, package manifests and service commitments, and operational constraints to determine the most practical recovery strategy for both flights and packages.

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
- Package manifests per affected flight, package service levels, and sort and cut-off windows
- Flight and package service priority and business impact signals

Decision rules:
- Keep only the facts that materially affect operational feasibility
- Flag missing route, crew, schedule, or package data
- Do not infer disruption severity without supporting operational signals

Return only a structured output with:
1. evidence_summary
2. missing_data
3. assumptions
4. package_impact_evidence
5. confidence_level
```

### 7.2 Prompt B — Route and Fleet Trade-Off Reasoning
```text
You are the Operations Agent for an aircraft AOG recovery workflow.

Use the grounded operational evidence from Prompt A to compare feasible recovery paths and determine the least-disruptive option.

Inputs you must assess:
- Affected routes and current fleet capacity
- Maintenance, inventory, and customer-priority constraints
- Affected package manifests, service levels, and sort and cut-off windows
- Recovery options already under consideration

Decision rules:
- Compare swap, reroute, delay, and repair paths by impact and feasibility
- Prefer the least-disruptive path that still works under operational constraints
- Use judgement to weigh flight disruption against package service risk when they point to different recovery options
- Explicitly state the trade-offs and risk assumptions

Return only a structured output with:
1. impacted_routes
2. affected_package_count
3. time_critical_package_exposure
4. service_commitments_at_risk
5. recovery_options
6. schedule_risk_minutes
7. risk_factors
8. confidence
```

### 7.3 Prompt C — Final Validation and Output Normalization
```text
You are the Operations Agent for an aircraft AOG recovery workflow.

Review the final operational recommendation and confirm it is suitable for Controller handoff and human review.

Inputs you must assess:
- Operational recommendation
- Constraint summary and risk flags
- Final impact rationale
- Package impact summary, including time-critical exposure and service commitments at risk

Decision rules:
- Ensure the recommendation is grounded and actionable
- Reject unsupported impact claims or hidden assumptions
- Explain the flight and package trade-offs in plain business language
- Normalize the result into the standard operations format

Return only a structured output with:
1. final_summary
2. operational_recommendation
3. flight_impact_summary
4. package_impact_summary
5. next_action
6. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "Operations Agent",
  "operational_impact_level": "low|medium|high|critical",
  "summary": "Short summary of the flight, package, schedule, and fleet impact",
  "affected_routes": ["Route 1", "Route 2"],
  "package_impact": {
    "affected_package_count": 0,
    "time_critical_package_count": 0,
    "service_commitments_at_risk": ["Commitment 1"],
    "summary": "Summary of package and customer impact"
  },
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

## 9A. Operational Validation and Conflict Handling
The Operations Agent should treat conflicting operational data as a decision-quality issue, not as a minor discrepancy.

- If route impact data is incomplete or highly time-bound, flag the recommendation as provisional
- If multiple aircraft substitutions are feasible but customer impact differs materially, present both outcomes and require human selection
- If a route conflict is detected, the recommendation should clearly describe which option is operationally preferred and why the alternative is less viable

This keeps the operational analysis grounded in measurable disruption patterns while preserving the human approval gate for difficult trade-offs.

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
- Package manifests per affected flight, including each package's service level or priority
- Package sort and cut-off windows
- Crew and operational constraints affecting feasibility
- Route disruption assumptions and schedule sensitivity

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the structured system inputs consumed by the agent before the model reasons.
- Flight operations schedule systems
- Fleet assignment and aircraft availability feeds
- Network disruption and route impact data
- Crew and station planning context
- Customer service priority or service recovery rules
- Package manifests per flight, package service levels, and sort and cut-off windows

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after evaluating the operational evidence:
- Operational impact summary
- Package impact summary, including affected package count and time-critical package exposure
- Service commitments at risk
- Recovery path comparison
- Schedule disruption estimate
- Fleet substitution recommendation
- Recommended operational action with rationale

## 13. Tool / External System Outputs
This is the downstream execution handshake: the structured operational recommendation generated after the LLM decision is accepted and converted into machine-usable dispatch actions.
- Operational impact payload sent to the Controller
- Structured package impact summary sent to the Controller
- Flight and fleet adjustment recommendation record
- Customer impact summary or package service-priority alert
- Schedule change flag for downstream planning systems
- Final decision context for approval or escalation

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This sequence preserves a clear trail from raw operational data through reasoning to the concrete schedule, package, or reroute decision.

## 13. Validation and Output Evaluation
The Operations Agent should confirm:
- whether the recommendation is consistent with fleet constraints
- whether the effect on service is properly framed
- whether the operational path is realistic under current planning conditions
- whether the decision is actionable for the human approver

## 14. Questions This Agent Seeks to Answer
- Which flights or routes are impacted by the outage?
- Which packages are affected, and how many are time-critical?
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

## 16. Use-Case Scenario and Mock Data
All scenario details, times, counts, and outcomes in this section are MOCK DATA for illustration and testing.

### Scenario 1: FX123 Hydraulic Pump Failure
**MOCK DATA — Story:** Aircraft FX123 is grounded at MEM with a hydraulic pump failure. Maintenance returns recovery ETA options to the Controller, who passes them to Operations. Operations identifies the affected flights and packages and recommends the least harmful operational path.

**MOCK DATA — Current time:** 2026-10-19 13:10

**MOCK DATA — Maintenance ETA options (via Controller):**

| Option | Estimated return to service |
|---|---|
| Transfer Part | 9 hours (2026-10-19 22:10) |
| Delay Flight | 27 hours (2026-10-20 16:10) |

**MOCK DATA — FX123 flights and package manifests:**

| Flight | Route | Departure | Packages | Priority packages |
|---|---|---|---:|---:|
| FX401 | MEM - IND | 2026-10-19 15:30 | 1,200 | 180 |
| FX812 | IND - MEM | 2026-10-19 19:00 | 900 | 140 |
| FX955 | MEM - DFW | 2026-10-20 08:00 | 700 | 60 |

**MOCK DATA — Spare aircraft:** FX207 is the same type as FX123, is at MEM, and has no flights scheduled during the recovery window.

**MOCK DATA — Package timing constraints:** FX401 package cut-off is 15:00. The sort window at IND is 17:30-18:30.

**Required Operations output for each option:** affected flights, affected package count, priority packages at risk, swap availability, recommended operational path, confidence, and assumptions.

For this example, count all manifested packages on each affected flight as affected. Count priority packages at risk using the priority-package manifest totals for those flights. Assume swapping to FX207 creates only a short delay to FX401 and prevents FX812 and FX955 from being affected. The repair ETA options do not return FX123 to service before the listed flights depart.

**MOCK DATA — Expected outcome:**

| Option | Flights affected | Affected packages | Priority packages at risk |
|---|---|---:|---:|
| Swap Aircraft (FX207) | FX401 | 1,200 | 180 (short delay) |
| Transfer Part (9 h) | FX401, FX812 | 2,100 | 320 |
| Delay Flight (27 h) | FX401, FX812, FX955 | 2,800 | 380 |

**MOCK DATA — Expected recommendation:** Swap Aircraft (FX207), because it affects the fewest flights and priority packages. This example uses the task's stated expected outcome; if the team changes the ranking rule in the open decisions, update this result to match.

### Scenario 2: Low-Confidence ETA and Priority Package Exposure
**MOCK DATA — Story and inputs:** FX123 is grounded at MEM before an early flight carrying 1,200 packages, including 700 priority packages. Maintenance estimates a 9-15 hour return-to-service window with low confidence. A same-type spare aircraft, FX207, is available at MEM, but its dispatch readiness still needs confirmation.

**Required Operations judgment:** Compare the uncertain repair window and package cut-off/service risk with the possibility of swapping to FX207. State which facts are confirmed, which assumptions remain, and how the low-confidence ETA affects the recommendation.

**MOCK DATA — Expected judgment:** If FX207's dispatch readiness is confirmed in time to protect the early flight's service commitments, recommend the swap as the lower-risk option and explain why. If readiness cannot be confirmed, flag the recommendation as provisional and present the package impact of waiting for the uncertain repair ETA for human review.

## 17. Draft Notes
This agent turns a technical recovery problem into a business recovery decision. It ensures the final recommendation is not only technically possible but also operationally sensible in real-world conditions.
