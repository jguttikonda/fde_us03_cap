-- Checks that the mock data produces the expected FX123 answer.

-- 1. Pump HP-2210: none at MEM, 2 at IND (6 h away) -> expect IND, qty 2, 6.0 h.
SELECT i.station, i.qty_on_hand, t.transfer_hours
FROM parts_inventory i
JOIN station_transfers t ON t.from_station = i.station AND t.to_station = 'MEM'
WHERE i.part_number = 'HP-2210' AND i.qty_on_hand > 0
ORDER BY t.transfer_hours;

-- 2. Alternate pump and supplier lead time -> expect HP-2215, 24 h.
SELECT a.alternate_part_number, s.lead_time_hours
FROM part_alternates a
JOIN supplier_stock s ON s.part_number = a.alternate_part_number
WHERE a.part_number = 'HP-2210';

-- 3. A spare aircraft of the same type at MEM -> expect FX207.
SELECT s.aircraft_id
FROM aircraft s
JOIN aircraft g ON g.aircraft_id = 'FX123' AND g.aircraft_type = s.aircraft_type
WHERE s.status = 'spare' AND s.current_station = 'MEM';

-- 4. FX123 flights that depart before it returns to service, per option.
--    Transfer part: 13:10 + 6 h + 3 h = 22:10 -> expect FX401, FX812.
--    Swap aircraft: 13:10 + 3 h = 16:10      -> expect FX401.
--    Delay flight:  13:10 + 24 h + 3 h = 16:10 next day -> expect FX401, FX812, FX955.
SELECT o.option_name, f.flight_id
FROM (VALUES
        ('Transfer Part',  TIMESTAMP '2026-10-19 22:10'),
        ('Swap Aircraft',  TIMESTAMP '2026-10-19 16:10'),
        ('Delay Flight',   TIMESTAMP '2026-10-20 16:10')
     ) AS o(option_name, back_in_service)
JOIN flights f ON f.aircraft_id = 'FX123' AND f.sched_dep < o.back_in_service
ORDER BY o.option_name, f.sched_dep;
