"""End-to-end scripted demo of the AOG Recovery Coordinator.

Real parts: PostgreSQL (in a throwaway Docker container) with the mock data, the MCP server, the MCP tool calls.
Scripted part: the agents' reasoning (plain Python) stands in for Gemini.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from database import DB_DIR, DockerPostgres, load_mock_data
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
AUDIT_LOG = HERE / "audit.jsonl"

NOW = datetime(2026, 10, 19, 13, 10)  # the demo clock matches the mock data
SWAP_PREP_HOURS = 3.0  # demo assumption: time to get the spare ready for the rotation
FAULT_CODES = {"hydraulic pump": "HYD-PUMP-FAIL", "hydraulic filter": "HYD-FILTER-CLOG"}


def fmt(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M")


def heading(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


# ---- Database -------------------------------------------------------------

def start_database():
    server = DockerPostgres()
    return server, server.start()


def load_and_verify(uri: str) -> None:
    load_mock_data(uri)
    with psycopg.connect(uri, autocommit=True) as conn:
        print("\n  Data check (verify.sql):")
        cur = conn.execute((DB_DIR / "verify.sql").read_text(encoding="utf-8"))
        n = 0
        while True:
            if cur.description:
                n += 1
                cols = [c.name for c in cur.description]
                for row in cur.fetchall():
                    print(f"    q{n}: " + ", ".join(f"{c}={v}" for c, v in zip(cols, row)))
            if not cur.nextset():
                break


# ---- MCP client helper ----------------------------------------------------

class Tools:
    def __init__(self, session: ClientSession, who: str):
        self.session, self.who = session, who

    async def __call__(self, tool: str, **args):
        shown = ", ".join(f"{k}={v!r}" for k, v in args.items() if k != "report_json")
        result = await self.session.call_tool(tool, args)
        if result.is_error:
            raise RuntimeError(f"{tool} failed: {result.content[0].text}")
        data = result.structured_content
        if data is None:
            data = json.loads(result.content[0].text)
        elif set(data) == {"result"}:
            data = data["result"]
        size = f"{len(data)} row(s)" if isinstance(data, list) else "ok"
        print(f"    [{self.who}] {tool}({shown}) -> {size}")
        return data


# ---- Agents (scripted stand-ins for Gemini) ---------------------------------

async def controller_open_case(tools: Tools, message: str) -> dict:
    aircraft = re.search(r"\bFX\d+\b", message).group(0)
    station = re.search(r"\bat ([A-Z]{3})\b", message).group(1)
    code = next((c for k, c in FAULT_CODES.items() if k in message.lower()), None)
    created = await tools("create_aog_event", aircraft_id=aircraft, fault_description=message,
                          station=station, fault_code=code)
    return await tools("get_aog_event", event_id=created["event_id"])


async def maintenance_agent(tools: Tools, event: dict) -> dict:
    orders = await tools("get_open_work_orders", aircraft_id=event["aircraft_id"])
    standard = (await tools("get_repair_standard", fault_code=event["fault_code"]))[0]
    history = await tools("get_maintenance_history", aircraft_id=event["aircraft_id"], system=standard["system"])
    return {
        "repair_feasible": True,
        "estimated_repair_hours": standard["estimated_hours"],
        "required_parts": [standard["required_part_number"]],
        "blocking_issues": [],
        "open_work_orders": [o["work_order_id"] for o in orders],
        "prior_repairs_on_system": len(history),
    }


async def inventory_agent(tools: Tools, event: dict, maintenance: dict) -> dict:
    part = maintenance["required_parts"][0]
    stock = await tools("check_part_stock", part_number=part, station=event["station"])
    alternates = await tools("find_alternate_parts", part_number=part)
    suppliers = list(await tools("get_supplier_availability", part_number=part))
    for alt in alternates:
        suppliers += await tools("get_supplier_availability", part_number=alt["alternate_part_number"])

    at_station = next((s["qty_on_hand"] for s in stock if s["station"] == event["station"]), 0)
    elsewhere = [s for s in stock if s["station"] != event["station"] and s["qty_on_hand"] > 0]
    supplier = min((s for s in suppliers if s["qty_available"] > 0), key=lambda s: s["lead_time_hours"], default=None)
    return {
        "part": part,
        "available_at_station": at_station,
        "available_elsewhere": elsewhere,
        "alternates": [a["alternate_part_number"] for a in alternates],
        "fastest_supplier": supplier,
        "readiness": "ready" if at_station else ("transfer needed" if elsewhere else "order needed"),
        "data_as_of": max(s["updated_at"] for s in stock),
    }


async def operations_agent(tools: Tools, event: dict, candidates: list[dict]) -> dict:
    window_end = fmt(NOW + timedelta(hours=24))
    spares = await tools("find_substitute_aircraft", grounded_aircraft_id=event["aircraft_id"],
                         station=event["station"], from_time=fmt(NOW), to_time=window_end)
    if spares:
        candidates = candidates + [{"option": "Swap Aircraft", "hours": SWAP_PREP_HOURS, "spare": spares[0]["aircraft_id"]}]

    options = []
    for c in candidates:
        back = NOW + timedelta(hours=c["hours"])
        affected = {f["flight_id"]: f for f in await tools(
            "get_flight_schedule", aircraft_id=event["aircraft_id"], from_time=fmt(NOW), to_time=fmt(back))}
        if affected:
            first = min(affected.values(), key=lambda f: f["sched_dep"])
            delay = (back - datetime.fromisoformat(first["sched_dep"])).total_seconds() / 3600
            for f in await tools("get_downstream_flights", flight_id=first["flight_id"], delay_hours=round(delay, 2)):
                affected.setdefault(f["flight_id"], f)
        options.append({**c, "back_in_service": fmt(back),
                        "affected_flights": sorted(affected, key=lambda k: affected[k]["sched_dep"])})
    return {"options": options, "spares": [s["aircraft_id"] for s in spares]}


async def report_agent(tools: Tools, event: dict, maint: dict, inv: dict, ops: dict) -> dict:
    # Ranking rule: fewest affected flights first, then fastest return to service.
    ranked = sorted(ops["options"], key=lambda o: (len(o["affected_flights"]), o["hours"]))
    for i, o in enumerate(ranked, 1):
        o["rank"] = i
    report = {
        "event_id": event["event_id"],
        "aircraft_id": event["aircraft_id"],
        "ranking_rule": "fewest affected flights, then fastest return to service",
        "options": ranked,
        "assumptions": [f"stock data as of {inv['data_as_of']}", "repair estimate from the standard repair guide",
                        f"swap needs {SWAP_PREP_HOURS:g} h to ready the spare and it covers the aircraft's rotation"],
        "advisory_only": True,
    }
    saved = await tools("save_recommendation_report", event_id=event["event_id"], report_json=json.dumps(report))
    report["report_id"] = saved["report_id"]
    return report


# ---- Presentation ---------------------------------------------------------

def trade_off(o: dict) -> str:
    n = len(o["affected_flights"])
    if o["option"] == "Swap Aircraft":
        return f"fastest, but uses up the spare {o['spare']}"
    if o["option"] == "Transfer Part":
        return f"{n} flight(s) delayed, no spare aircraft needed"
    if o["option"] == "Repair Now":
        return "no parts delay"
    return "slowest option, waits on the supplier"


def show_report(event: dict, report: dict, inv: dict) -> None:
    print(f"\nRecovery options for {event['aircraft_id']} ({event['event_id']})\n")
    for o in report["options"]:
        tag = "   (RECOMMENDED)" if o["rank"] == 1 else ""
        print(f"{o['rank']}. {o['option']}{tag}")
        print(f"   - Back in service: {o['back_in_service']} (about {o['hours']:g} hours)")
        print(f"   - Affected flights: {', '.join(o['affected_flights']) or 'none'}")
        print(f"   - Trade-off: {trade_off(o)}")
        print()
    print("Assumptions: " + "; ".join(report["assumptions"]) + ".")
    print(f"Ranking rule: {report['ranking_rule']}.")
    print(f"Saved as report #{report['report_id']}. These are suggestions only. Please review and approve before any action.")


def guardrail_check(uri: str) -> None:
    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute("SET ROLE agent_reader")
        try:
            conn.execute("INSERT INTO aog_events (aircraft_id, fault_description, station) VALUES ('FX123', 'x', 'MEM')")
            print("  read-only role could write: FAIL")
        except psycopg.errors.InsufficientPrivilege:
            print("  read-only role tried to write -> blocked by the database (good)")
    calls = [json.loads(line) for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines()]
    print(f"  audit log recorded {len(calls)} tool calls in {AUDIT_LOG.name}")


# ---- Main -----------------------------------------------------------------

async def run(uri: str) -> None:
    AUDIT_LOG.unlink(missing_ok=True)
    env = {**os.environ, "AOG_DATABASE_URL": uri, "AOG_AUDIT_LOG": str(AUDIT_LOG)}
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "mcp_server.py")], env=env)

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = await session.list_tools()
        print(f"  MCP server up with {len(listed.tools)} tools: " + ", ".join(t.name for t in listed.tools))

        message = "FX123 is grounded at MEM, hydraulic pump failure."
        heading("Step 3: chat with the Controller")
        print(f"\nYou:        {message}\n")

        event = await controller_open_case(Tools(session, "Controller"), message)
        print(f"\nController: Case {event['event_id']} opened. Asking my team...\n")

        maint = await maintenance_agent(Tools(session, "Maintenance"), event)
        inv = await inventory_agent(Tools(session, "Inventory"), event, maint)

        candidates = []
        hours = maint["estimated_repair_hours"]
        if inv["available_at_station"]:
            candidates.append({"option": "Repair Now", "hours": hours})
        if inv["available_elsewhere"]:
            best = min(inv["available_elsewhere"], key=lambda s: s["transfer_hours"])
            candidates.append({"option": "Transfer Part", "hours": best["transfer_hours"] + hours, "from": best["station"]})
        if inv["fastest_supplier"]:
            candidates.append({"option": "Delay Flight", "hours": inv["fastest_supplier"]["lead_time_hours"] + hours})

        ops = await operations_agent(Tools(session, "Operations"), event, candidates)
        report = await report_agent(Tools(session, "Report"), event, maint, inv, ops)

        heading("What the human sees in the chat")
        show_report(event, report, inv)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    heading("Step 1: start PostgreSQL and load the mock data")
    server, uri = start_database()
    try:
        load_and_verify(uri)
        heading("Step 2: start the MCP server (the front desk)")
        asyncio.run(run(uri))
        heading("Guardrail check")
        guardrail_check(uri)
    finally:
        server.cleanup()


if __name__ == "__main__":
    main()
