"""Real Google ADK agents for the AOG Recovery Coordinator.

Run from the fde_us03_cap folder (parent of this package):
    python aog_coordinator/setup_db.py        # starts PostgreSQL and loads the mock data
    adk web                                   # then pick "aog_coordinator" in the browser

Needs GOOGLE_API_KEY (see .env.example). Every agent reaches data only through the MCP server's whitelisted tools.
"""

import os
import sys
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

HERE = Path(__file__).resolve().parent
MODEL = os.environ.get("AOG_MODEL", "gemini-2.5-pro")
DEFAULT_DB_URL = "postgresql://postgres:aog@localhost:55432/postgres"
DEMO_NOW = "2026-10-19 13:10"  # matches the mock data timestamps
SWAP_PREP_HOURS = 3


def _mcp_tools(tool_names: list[str]) -> McpToolset:
    """A connection to the MCP server that exposes only the listed tools."""
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(HERE / "mcp_server.py")],
        env={
            "AOG_DATABASE_URL": os.environ.get("AOG_DATABASE_URL", DEFAULT_DB_URL),
            "AOG_AUDIT_LOG": os.environ.get("AOG_AUDIT_LOG", str(HERE / "audit.jsonl")),
        },
    )
    return McpToolset(connection_params=StdioConnectionParams(server_params=server, timeout=30), tool_filter=tool_names)


COMMON_RULES = """
Rules:
- Use only facts returned by your tools. Never invent part numbers, stock, flights or times.
- If a tool returns nothing, say so and lower your confidence.
- Reply with one JSON object only, always including: findings, confidence (low/medium/high), assumptions (list), data_as_of.
"""

maintenance_agent = Agent(
    name="maintenance_agent",
    model=MODEL,
    description="Assesses whether an aircraft fault can be repaired, how long it takes, and which part is needed.",
    instruction=f"""You are the Maintenance Agent in an aircraft-on-ground (AOG) recovery.
You receive aircraft_id, the fault description, and possibly a fault_code.
Steps:
1. Call get_open_work_orders and get_maintenance_history (system matching the fault) for the aircraft.
2. Call get_repair_standard. If you have no fault_code, call it with no arguments and pick the standard that fits the fault; state which one you picked.
Return: repair_feasible (yes/no/conditional), estimated_repair_hours, required_parts (list of part numbers), blocking_issues, open_work_orders.
{COMMON_RULES}""",
    tools=[_mcp_tools(["get_open_work_orders", "get_maintenance_history", "get_repair_standard"])],
)

inventory_agent = Agent(
    name="inventory_agent",
    model=MODEL,
    description="Finds where a required part is in stock, approved alternates, and supplier lead times.",
    instruction=f"""You are the Inventory Agent in an aircraft-on-ground (AOG) recovery.
You receive required part numbers and the station where the aircraft is grounded.
Steps for each part:
1. check_part_stock (it returns stock at every station with transfer hours to the grounded station).
2. find_alternate_parts, then get_supplier_availability for the part and for each alternate.
Return per part: available_at_station (qty), available_elsewhere (station, qty, transfer_hours; only stations with qty > 0),
alternates, fastest_supplier (supplier, part_number, lead_time_hours, choosing the shortest lead time among the part and its alternates with stock),
readiness (ready / transfer needed / order needed).
{COMMON_RULES}""",
    tools=[_mcp_tools(["check_part_stock", "find_alternate_parts", "get_supplier_availability"])],
)

operations_agent = Agent(
    name="operations_agent",
    model=MODEL,
    description="Lists the flights affected by each recovery option and finds spare aircraft for a swap.",
    instruction=f"""You are the Operations Agent in an aircraft-on-ground (AOG) recovery.
You receive aircraft_id, station, the current time, and candidate recovery options, each with hours_to_return.
Steps:
1. Call find_substitute_aircraft (grounded_aircraft_id, station, from now to now + 24 hours). If a spare is found, add the option
   "Swap Aircraft" with hours_to_return = {SWAP_PREP_HOURS} (assumption: time to ready the spare, which then covers the aircraft's rotation).
2. For each option, back_in_service = now + hours_to_return. Call get_flight_schedule from now to back_in_service for the aircraft;
   those flights are affected.
3. For the earliest affected flight, call get_downstream_flights with delay_hours = back_in_service minus that flight's departure (in hours)
   and add any extra flights returned.
Times are 'YYYY-MM-DD HH:MM'. Do not estimate costs; only list flights.
Return per option: option, back_in_service, affected_flights (flight ids in departure order), spare_aircraft (if any).
{COMMON_RULES}""",
    tools=[_mcp_tools(["get_flight_schedule", "find_substitute_aircraft", "get_downstream_flights"])],
)

report_agent = Agent(
    name="report_agent",
    model=MODEL,
    description="Ranks the recovery options, saves the report, and writes the advisory summary for the human.",
    instruction="""You are the Report Creation Agent in an aircraft-on-ground (AOG) recovery.
You receive the event_id and the findings of the Maintenance, Inventory and Operations agents with the options.
Ranking rule: fewest affected flights first, then fastest return to service. Rank 1 is RECOMMENDED.
Steps:
1. Build a report JSON object: event_id, aircraft_id, ranking_rule, options (rank, option, hours, back_in_service,
   affected_flights, trade_off), assumptions, advisory_only: true.
2. Call save_recommendation_report with event_id and the report as JSON text (report_json).
3. Reply to the human in this layout, one block per option in rank order:
   "<rank>. <option>   (RECOMMENDED on rank 1)
      - Back in service: <time> (about <hours> hours)
      - Affected flights: <flights or none>
      - Trade-off: <short plain sentence>"
   Then: Assumptions, the ranking rule, "Saved as report #<id>", and finish with:
   "These are suggestions only. Please review and approve before any action."
You are advisory only: never say an action was taken, and never approve on the human's behalf.""",
    tools=[_mcp_tools(["save_recommendation_report"])],
)

root_agent = Agent(
    name="recovery_coordinator",
    model=MODEL,
    description="Controller: opens an AOG case from the human's chat message and coordinates the specialist agents.",
    instruction=f"""You are the Controller of the AOG Recovery Coordinator. The human is an airline controller talking to you in a chat.
The current time for this demo is {DEMO_NOW}.
Workflow:
1. From the message, get aircraft_id (e.g. FX123), station (3-letter code) and the fault. If any is missing, ask one short follow-up question and wait.
2. Call create_aog_event, then get_aog_event. Tell the human the case id and that you are asking your team.
3. Call maintenance_agent with aircraft_id, fault description and event_id.
4. Call inventory_agent with the required parts from step 3 and the station.
5. Build candidate options with hours_to_return:
   - "Repair Now": estimated_repair_hours, only if the part is in stock at the station.
   - "Transfer Part": transfer_hours of the nearest station that has stock + estimated_repair_hours.
   - "Delay Flight": fastest_supplier lead_time_hours + estimated_repair_hours.
6. Call operations_agent with aircraft_id, station, the current time and the candidate options.
7. Call report_agent with event_id, aircraft_id and all findings. Show its answer to the human unchanged.
Never decide for the human and never claim an operational action happened. If an agent reports an error, say so plainly instead of guessing.""",
    tools=[
        _mcp_tools(["create_aog_event", "get_aog_event"]),
        AgentTool(agent=maintenance_agent),
        AgentTool(agent=inventory_agent),
        AgentTool(agent=operations_agent),
        AgentTool(agent=report_agent),
    ],
)
