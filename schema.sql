-- Cast Roster
CREATE TABLE IF NOT EXISTS cast_members (
    actor_id String,
    full_name String,
    age UInt8,
    role_type String
) ENGINE = MergeTree()
ORDER BY actor_id;

INSERT INTO cast_members VALUES 
    ('A1', 'Tom Hanks', 67, 'Lead'),
    ('A2', 'Kiernan Shipka', 12, 'Supporting'),
    ('A3', 'Jacob Tremblay', 9, 'Lead');

-- Labor Laws
CREATE TABLE IF NOT EXISTS labor_laws (
    state String,
    min_age UInt8,
    max_age UInt8,
    max_daily_hours UInt8,
    latest_wrap_hour UInt8 
) ENGINE = MergeTree()
ORDER BY state;

INSERT INTO labor_laws VALUES 
    ('CA', 8, 11, 6, 19),
    ('CA', 12, 15, 8, 20),
    ('NY', 8, 15, 8, 22);

-- Daily Schedule
CREATE TABLE IF NOT EXISTS daily_schedule (
    scene_number String,
    actor_id String,
    shoot_date Date,
    start_time DateTime,
    end_time DateTime,
    location_state String
) ENGINE = MergeTree()
ORDER BY (shoot_date, scene_number);

INSERT INTO daily_schedule VALUES 
    ('Sc_01', 'A1', '2026-08-25', '2026-08-25 08:00:00', '2026-08-25 18:00:00', 'CA'),
    ('Sc_01', 'A3', '2026-08-25', '2026-08-25 08:00:00', '2026-08-25 18:00:00', 'CA'),
    ('Sc_02', 'A2', '2026-08-25', '2026-08-25 14:00:00', '2026-08-25 19:30:00', 'CA');
