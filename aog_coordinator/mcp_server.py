"""MCP server: the single front desk between the AOG agents and PostgreSQL.

Read tools run as database role agent_reader; the two write tools run as agent_writer.
Connection string comes from AOG_DATABASE_URL.
"""

import functools
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from mcp.server.mcpserver import MCPServer
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

mcp = MCPServer("aog-data")
AUDIT_LOG = Path(os.environ.get("AOG_AUDIT_LOG", "audit.jsonl"))


@contextmanager
def _db(role: str):
    with psycopg.connect(os.environ["AOG_DATABASE_URL"], row_factory=dict_row) as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        yield conn


def _clean(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def _read(query: str, params=None) -> list[dict]:
    with _db("agent_reader") as conn:
        return _clean(conn.execute(query, params).fetchall())


def audited(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "tool": fn.__name__, "args": kwargs}
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return fn(*args, **kwargs)

    return wrapper


# ---- Controller -----------------------------------------------------------

@mcp.tool()
@audited
def create_aog_event(aircraft_id: str, fault_description: str, station: str, fault_code: str | None = None) -> dict:
    """Open a new AOG case and return its event_id. This is a write."""
    with _db("agent_writer") as conn:
        row = conn.execute(
            "INSERT INTO aog_events (aircraft_id, fault_code, fault_description, station) "
            "VALUES (%s, %s, %s, %s) RETURNING event_id",
            (aircraft_id, fault_code, fault_description, station),
        ).fetchone()
    return row


@mcp.tool()
@audited
def get_aog_event(event_id: str) -> dict:
    """Return the details of an AOG case."""
    rows = _read("SELECT * FROM aog_events WHERE event_id = %s", (event_id,))
    return rows[0] if rows else {}


# ---- Maintenance ----------------------------------------------------------

@mcp.tool()
@audited
def get_open_work_orders(aircraft_id: str) -> list[dict]:
    """Open work orders for an aircraft."""
    return _read("SELECT * FROM work_orders WHERE aircraft_id = %s AND status = 'open' ORDER BY opened_at", (aircraft_id,))


@mcp.tool()
@audited
def get_maintenance_history(aircraft_id: str, system: str | None = None) -> list[dict]:
    """Past repairs for an aircraft, optionally limited to one system (e.g. 'hydraulic')."""
    return _read(
        "SELECT * FROM maintenance_history WHERE aircraft_id = %s AND (%s::text IS NULL OR system = %s) "
        "ORDER BY performed_on DESC",
        (aircraft_id, system, system),
    )


@mcp.tool()
@audited
def get_repair_standard(fault_code: str | None = None) -> list[dict]:
    """Standard repair hours and required part for a fault code. Omit fault_code to list all standards."""
    return _read(
        "SELECT * FROM repair_standards WHERE (%s::text IS NULL OR fault_code = %s) ORDER BY fault_code",
        (fault_code, fault_code),
    )


# ---- Inventory ------------------------------------------------------------

@mcp.tool()
@audited
def check_part_stock(part_number: str, station: str) -> list[dict]:
    """Stock of a part at every station, with transfer hours to `station` (0 if already there)."""
    return _read(
        "SELECT i.station, i.qty_on_hand, i.updated_at, "
        "       CASE WHEN i.station = %(s)s THEN 0 ELSE t.transfer_hours END AS transfer_hours "
        "FROM parts_inventory i "
        "LEFT JOIN station_transfers t ON t.from_station = i.station AND t.to_station = %(s)s "
        "WHERE i.part_number = %(p)s "
        "ORDER BY (i.station = %(s)s) DESC, t.transfer_hours NULLS LAST",
        {"p": part_number, "s": station},
    )


@mcp.tool()
@audited
def find_alternate_parts(part_number: str) -> list[dict]:
    """Approved substitute part numbers."""
    return _read(
        "SELECT a.alternate_part_number, p.description FROM part_alternates a "
        "JOIN parts p ON p.part_number = a.alternate_part_number WHERE a.part_number = %s",
        (part_number,),
    )


@mcp.tool()
@audited
def get_supplier_availability(part_number: str) -> list[dict]:
    """Supplier stock and lead time for a part."""
    return _read("SELECT * FROM supplier_stock WHERE part_number = %s ORDER BY lead_time_hours", (part_number,))


# ---- Operations -----------------------------------------------------------

@mcp.tool()
@audited
def get_flight_schedule(aircraft_id: str, from_time: str, to_time: str) -> list[dict]:
    """Flights of an aircraft departing in [from_time, to_time). Times are 'YYYY-MM-DD HH:MM'."""
    return _read(
        "SELECT * FROM flights WHERE aircraft_id = %s AND sched_dep >= %s::timestamp AND sched_dep < %s::timestamp "
        "ORDER BY sched_dep",
        (aircraft_id, from_time, to_time),
    )


@mcp.tool()
@audited
def find_substitute_aircraft(grounded_aircraft_id: str, station: str, from_time: str, to_time: str) -> list[dict]:
    """Spare aircraft of the same type at `station` with no flights in the window."""
    return _read(
        "SELECT s.aircraft_id, s.aircraft_type, s.current_station FROM aircraft s "
        "JOIN aircraft g ON g.aircraft_id = %(g)s AND g.aircraft_type = s.aircraft_type "
        "WHERE s.status = 'spare' AND s.current_station = %(st)s AND NOT EXISTS ("
        "  SELECT 1 FROM flights f WHERE f.aircraft_id = s.aircraft_id "
        "  AND f.sched_dep < %(to)s::timestamp AND f.sched_arr > %(from)s::timestamp)",
        {"g": grounded_aircraft_id, "st": station, "from": from_time, "to": to_time},
    )


@mcp.tool()
@audited
def get_downstream_flights(flight_id: str, delay_hours: float) -> list[dict]:
    """Later flights on the same aircraft that depart before it could be ready after a delay of this flight."""
    return _read(
        "SELECT f2.* FROM flights f1 "
        "JOIN flights f2 ON f2.aircraft_id = f1.aircraft_id AND f2.rotation_seq > f1.rotation_seq "
        "WHERE f1.flight_id = %s AND f2.sched_dep < f1.sched_arr + (%s::float8 * interval '1 hour') "
        "ORDER BY f2.sched_dep",
        (flight_id, delay_hours),
    )


# ---- Report Creation ------------------------------------------------------

@mcp.tool()
@audited
def save_recommendation_report(event_id: str, report_json: str) -> dict:
    """Save the final recommendation report for a case. report_json is a JSON object as text. This is a write."""
    report = json.loads(report_json)
    if not isinstance(report, dict):
        raise ValueError("report_json must be a JSON object")
    with _db("agent_writer") as conn:
        row = conn.execute(
            "INSERT INTO recommendation_reports (event_id, report) VALUES (%s, %s) RETURNING report_id",
            (event_id, Jsonb(report)),
        ).fetchone()
    return row


if __name__ == "__main__":
    mcp.run()
