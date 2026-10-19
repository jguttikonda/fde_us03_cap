-- AOG Recovery Coordinator: mock data for the FX123 hydraulic pump scenario.
-- All values are invented. "Now" in the demo is 2026-10-19 13:10.
-- aog_events and recommendation_reports start empty; agents create those rows.

INSERT INTO aircraft (aircraft_id, aircraft_type, current_station, status) VALUES
    ('FX123', 'B757-200F', 'MEM', 'in_service'),
    ('FX207', 'B757-200F', 'MEM', 'spare'),
    ('FX310', 'MD-11F',    'DFW', 'in_service');

INSERT INTO parts (part_number, description, system) VALUES
    ('HP-2210', 'Hydraulic pump, main',                  'hydraulic'),
    ('HP-2215', 'Hydraulic pump, approved alternate',    'hydraulic'),
    ('HF-1100', 'Hydraulic filter element',              'hydraulic'),
    ('TR-0770', 'Main wheel tire',                       'landing_gear');

INSERT INTO repair_standards (fault_code, system, description, estimated_hours, required_part_number) VALUES
    ('HYD-PUMP-FAIL',   'hydraulic', 'Replace main hydraulic pump and leak-check', 3.0, 'HP-2210'),
    ('HYD-FILTER-CLOG', 'hydraulic', 'Replace hydraulic filter element',           1.0, 'HF-1100');

INSERT INTO work_orders (work_order_id, aircraft_id, system, description, status, opened_at) VALUES
    ('WO-5001', 'FX123', 'hydraulic', 'Low hydraulic pressure, main pump HP-2210 suspected', 'open',   '2026-10-19 12:40'),
    ('WO-4890', 'FX123', 'landing_gear', 'Tire wear check',                                   'closed', '2026-10-02 09:00');

INSERT INTO maintenance_history (aircraft_id, system, description, part_number, performed_on) VALUES
    ('FX123', 'hydraulic', 'Hydraulic filter replaced',      'HF-1100', '2026-08-02'),
    ('FX123', 'hydraulic', 'Main pump inspected, no fault',  'HP-2210', '2026-03-14'),
    ('FX207', 'hydraulic', 'Hydraulic filter replaced',      'HF-1100', '2026-09-11');

-- HP-2210 is out of stock at MEM but 2 are at IND; ANC is a slower fallback.
INSERT INTO parts_inventory (part_number, station, qty_on_hand, updated_at) VALUES
    ('HP-2210', 'MEM', 0,  '2026-10-19 13:10'),
    ('HP-2210', 'IND', 2,  '2026-10-19 13:10'),
    ('HP-2210', 'DFW', 0,  '2026-10-19 13:10'),
    ('HP-2210', 'ANC', 1,  '2026-10-19 13:10'),
    ('HP-2215', 'MEM', 0,  '2026-10-19 13:10'),
    ('HP-2215', 'IND', 0,  '2026-10-19 13:10'),
    ('HF-1100', 'MEM', 12, '2026-10-19 13:10'),
    ('HF-1100', 'IND', 8,  '2026-10-19 13:10'),
    ('TR-0770', 'MEM', 6,  '2026-10-19 13:10');

INSERT INTO part_alternates (part_number, alternate_part_number) VALUES
    ('HP-2210', 'HP-2215');

INSERT INTO supplier_stock (part_number, supplier, qty_available, lead_time_hours) VALUES
    ('HP-2210', 'Acme Aero Supply', 4, 48),
    ('HP-2215', 'Acme Aero Supply', 3, 24),
    ('HF-1100', 'Acme Aero Supply', 50, 12);

INSERT INTO station_transfers (from_station, to_station, transfer_hours) VALUES
    ('IND', 'MEM', 6.0),
    ('DFW', 'MEM', 4.0),
    ('ANC', 'MEM', 11.0);

-- FX123 rotation: FX401 -> FX812 today, FX955 tomorrow morning.
INSERT INTO flights (flight_id, aircraft_id, origin, destination, sched_dep, sched_arr, rotation_seq) VALUES
    ('FX401', 'FX123', 'MEM', 'IND', '2026-10-19 15:30', '2026-10-19 17:00', 1),
    ('FX812', 'FX123', 'IND', 'MEM', '2026-10-19 19:00', '2026-10-19 20:30', 2),
    ('FX955', 'FX123', 'MEM', 'DFW', '2026-10-20 08:00', '2026-10-20 09:30', 3),
    ('FX220', 'FX310', 'DFW', 'ANC', '2026-10-19 16:00', '2026-10-19 20:00', 1);
