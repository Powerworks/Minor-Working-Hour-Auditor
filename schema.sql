-- Minor Working-Hour Auditor — ClickHouse schema (draft, 2026-08-21)
-- Two tables: who's on set, and what the law says for their state/age.
-- Deliberately minimal for a hackathon window — no ingestion-log/audit-trail
-- table, no production-metadata table beyond what's needed to join.

CREATE TABLE IF NOT EXISTS cast_members
(
    cast_id         String,
    production_id   String,
    name            String,
    date_of_birth   Date,
    production_state String,   -- state whose labor law jurisdiction applies
    role            String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (production_id, cast_id);

-- One row per (state, age_band, school_day) rule variant. Age-banded and
-- school-day-vs-non-school-day rules are both real, common axes in child
-- labor law (e.g. CA Labor Code §1308 tiers by age; hours differ on school
-- days vs. non-school days/vacation).
CREATE TABLE IF NOT EXISTS labor_law_rules
(
    state                       String,
    min_age                     UInt8,
    max_age                     UInt8,          -- inclusive upper bound of the band
    school_day                  UInt8,          -- 0 = non-school day/vacation, 1 = school day
    max_work_hours_per_day      Decimal32(2),   -- actual work time only
    max_hours_at_workplace      Decimal32(2),   -- total time present (work + schooling + rest)
    min_school_hours            Nullable(Decimal32(2)),
    max_hours_per_week          Nullable(Decimal32(2)),
    earliest_start_time         String,         -- "HH:MM", 24h
    latest_end_time             String,         -- "HH:MM", 24h
    min_rest_between_calls_hours Decimal32(2),
    required_break_minutes      UInt16,
    effective_from              Date,
    effective_to                Nullable(Date),  -- null = still in force
    source_citation             String           -- e.g. "CA Labor Code §1308.7"
)
ENGINE = MergeTree
ORDER BY (state, min_age, effective_from);

-- Daily Schedule for shoot days / scenes
CREATE TABLE IF NOT EXISTS daily_schedule
(
    scene_number    String,
    cast_id         String,
    shoot_date      Date,
    start_time      DateTime,
    end_time        DateTime,
    location_state  String
)
ENGINE = MergeTree
ORDER BY (shoot_date, scene_number, cast_id);

-- Demo Cast Members (minor actors across California jurisdictions)
INSERT INTO cast_members (cast_id, production_id, name, date_of_birth, production_state, role) VALUES
    ('cast_001', 'prod_demo', 'Maya Lin', '2019-09-15', 'CA', 'Supporting (Age 6)'),
    ('cast_002', 'prod_demo', 'Jacob Tremblay', '2014-10-05', 'CA', 'Lead (Age 11)'),
    ('cast_003', 'prod_demo', 'Kiernan Shipka', '2009-11-10', 'CA', 'Lead Teen (Age 16)');

-- Demo Daily Schedule for end-to-end audit query verification
INSERT INTO daily_schedule (scene_number, cast_id, shoot_date, start_time, end_time, location_state) VALUES
    ('Sc_101', 'cast_001', '2026-08-25', '2026-08-25 09:00:00', '2026-08-25 13:00:00', 'CA'),
    ('Sc_102', 'cast_002', '2026-08-25', '2026-08-25 08:30:00', '2026-08-25 15:30:00', 'CA'),
    ('Sc_103', 'cast_003', '2026-08-25', '2026-08-25 08:00:00', '2026-08-25 16:00:00', 'CA');
