-- AOG Recovery Coordinator: mock database schema (PostgreSQL).
-- Times are plain timestamps on one common demo clock, not real time zones.

CREATE SEQUENCE aog_event_seq START 1;

CREATE TABLE aircraft (
    aircraft_id     TEXT PRIMARY KEY,
    aircraft_type   TEXT NOT NULL,
    current_station TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('in_service', 'spare', 'grounded'))
);

CREATE TABLE aog_events (
    event_id          TEXT PRIMARY KEY
                      DEFAULT 'AOG-' || lpad(nextval('aog_event_seq')::text, 4, '0'),
    aircraft_id       TEXT NOT NULL REFERENCES aircraft (aircraft_id),
    fault_code        TEXT,
    fault_description TEXT NOT NULL,
    station           TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at        TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE work_orders (
    work_order_id TEXT PRIMARY KEY,
    aircraft_id   TEXT NOT NULL REFERENCES aircraft (aircraft_id),
    system        TEXT NOT NULL,
    description   TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    opened_at     TIMESTAMP NOT NULL
);

CREATE TABLE maintenance_history (
    history_id   SERIAL PRIMARY KEY,
    aircraft_id  TEXT NOT NULL REFERENCES aircraft (aircraft_id),
    system       TEXT NOT NULL,
    description  TEXT NOT NULL,
    part_number  TEXT,
    performed_on DATE NOT NULL
);

CREATE TABLE parts (
    part_number TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    system      TEXT NOT NULL
);

CREATE TABLE repair_standards (
    fault_code           TEXT PRIMARY KEY,
    system               TEXT NOT NULL,
    description          TEXT NOT NULL,
    estimated_hours      NUMERIC(4, 1) NOT NULL,
    required_part_number TEXT REFERENCES parts (part_number)
);

CREATE TABLE parts_inventory (
    part_number TEXT NOT NULL REFERENCES parts (part_number),
    station     TEXT NOT NULL,
    qty_on_hand INTEGER NOT NULL CHECK (qty_on_hand >= 0),
    updated_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (part_number, station)
);

CREATE TABLE part_alternates (
    part_number           TEXT NOT NULL REFERENCES parts (part_number),
    alternate_part_number TEXT NOT NULL REFERENCES parts (part_number),
    PRIMARY KEY (part_number, alternate_part_number)
);

CREATE TABLE supplier_stock (
    part_number     TEXT NOT NULL REFERENCES parts (part_number),
    supplier        TEXT NOT NULL,
    qty_available   INTEGER NOT NULL CHECK (qty_available >= 0),
    lead_time_hours INTEGER NOT NULL,
    PRIMARY KEY (part_number, supplier)
);

CREATE TABLE station_transfers (
    from_station   TEXT NOT NULL,
    to_station     TEXT NOT NULL,
    transfer_hours NUMERIC(4, 1) NOT NULL,
    PRIMARY KEY (from_station, to_station)
);

CREATE TABLE flights (
    flight_id    TEXT PRIMARY KEY,
    aircraft_id  TEXT NOT NULL REFERENCES aircraft (aircraft_id),
    origin       TEXT NOT NULL,
    destination  TEXT NOT NULL,
    sched_dep    TIMESTAMP NOT NULL,
    sched_arr    TIMESTAMP NOT NULL,
    rotation_seq INTEGER NOT NULL
);

CREATE TABLE recommendation_reports (
    report_id  SERIAL PRIMARY KEY,
    event_id   TEXT NOT NULL REFERENCES aog_events (event_id),
    report     JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Agents connect as a read-only user; only the MCP write tools use the writer.
CREATE ROLE agent_reader NOLOGIN;
CREATE ROLE agent_writer NOLOGIN;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_reader;
GRANT agent_reader TO agent_writer;
GRANT INSERT ON aog_events, recommendation_reports TO agent_writer;
GRANT USAGE ON SEQUENCE aog_event_seq, recommendation_reports_report_id_seq TO agent_writer;
