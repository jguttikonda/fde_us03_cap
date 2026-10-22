# Mock AOG Data

All records in this folder are fictional demonstration data. They do not represent
real aircraft, inventory, flights, shipment quotes, or operational approvals.

Each agent has its own JSON file because the agents have different input contracts.
The shared case identifier is `AOG-MOCK-1042` so the examples can be compared as
one incident. The Materials & Logistics file includes three part-availability
scenarios:

- `part_available_local`: the preferred replacement is at the aircraft station.
- `part_available_remote`: it is out of stock locally but available at another station.
- `part_unavailable`: current mock inventory finds no stock at either queried station.

## Files

- `maintenance_agent.json`: a Maintenance assessment input with prior similar
  failures, work-order information, engineering constraints, part dependency,
  and a remote-part readiness estimate.
- `materials_logistics_agent.json`: three assessment inputs for local, remote,
  and unavailable part scenarios.
- `operations_agent.json`: Operations requests plus mock read-only source data
  for flight schedule, fleet, package loads, alternate flights, and network status.
  The `request` object is the Operations request contract; source data must be
  wired to mock read-only adapters when running the agent.
- `controller_agent.json`: an illustrative case context and example report in
  the proposal's output style. This is **not runtime-consumable Controller input**:
  the repository does not currently define a Controller runtime input model.

## Flights available to the chatbot

The Operations source data in `operations_agent.json` holds three affected-flight cases. Each
flight is assigned to one aircraft, so use the matching tail number in the chat prompt
(a mismatch is reported as an assignment conflict):

| Flight | Aircraft | Route | Packages (priority) | Notes |
|---|---|---|---|---|
| `FX103` | `N123AB` | MIA-ORD | 1,200 (700) | Original case; limited alternate capacity |
| `FX777` | `N456CD` | MIA-ATL | 300 (80) | Departs 12:00Z, before a local-stock repair finishes (about 13:30Z); the substitute aircraft is clearly best |
| `FX909` | `N777XY` | MIA-JFK | 600 (250) | Crew coverage gap; expect a conflict and escalation |

Combine any flight with any of the three part scenarios (`part_available_local`,
`part_available_remote`, `part_unavailable`). Results from the live model can vary between runs
when evidence is thin, and degraded results are shown as warnings, never hidden.

Timestamps are ISO 8601 UTC values. Evidence IDs in payloads are synthetic
references used to keep facts traceable across the examples. All scenarios remain
advisory; human approval is required before any operational action.