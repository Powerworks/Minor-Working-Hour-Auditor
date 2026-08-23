-- Minor Working-Hour Auditor — seed data, California, sourced 2026-08-21,
-- non-school-day figures added 2026-08-23.
-- Primary sources: 8 Cal. Code Regs. §11760 (dir.ca.gov/t8/11760.html);
-- Cal. Labor Code §1308.7 (verbatim statute text, law.onecle.com/california/labor/1308.7.html).
-- RECONCILIATION: §11760 and §1308.7 conflict for the 16-18 band on BOTH
-- school days and non-school days (work hours alone already equal the
-- reconciled 8hr Lab. Code ceiling, so the reg's own +1hr rest/recreation
-- or +3hr schooling component numerically exceeds it by 1hr). This is
-- flagged, not silently resolved — see labor_law_rules.source_citation
-- text on those rows and the Audit Report's rule_confidence field.
-- §1308.7's 12:30am non-school-night curfew extension applies to "a
-- minor" with no age qualifier in the statute text — it is NOT limited
-- to 16-17 year-olds (that age-restricted 12:30am extension belongs to
-- the separate general-employment Lab. Code §1391, which does not
-- govern the entertainment industry). Non-school-day rows below are
-- sourced for the 6-9, 9-16, and 16-18 bands, matching the bands §11760
-- explicitly splits by school-day status. The 0-0, 1-1, and 2-5 bands
-- have no school-day/non-school-day distinction in §11760 (no schooling
-- component applies to those ages), so their single existing row already
-- covers all days for work-hour purposes; the §1308.7 non-school-night
-- curfew extension technically applies to them too but is not modeled
-- as a separate row here since no demo scenario exercises it.

INSERT INTO labor_law_rules
(state, min_age, max_age, school_day, max_work_hours_per_day, max_hours_at_workplace,
 min_school_hours, max_hours_per_week, earliest_start_time, latest_end_time,
 min_rest_between_calls_hours, required_break_minutes, effective_from, effective_to, source_citation)
VALUES
('CA', 0, 0, 1, 0.33, 2.00, NULL, NULL, '05:00', '22:00', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760(a) (15 days-6mo: 2hr at-workplace, 20min work); Lab. Code §1308.7 (curfew) — no conflict, §11760 figure already < 8hr cap'),

('CA', 1, 1, 1, 2.00, 4.00, NULL, NULL, '05:00', '22:00', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (6mo-2yr: 4hr at-workplace, 2hr work); Lab. Code §1308.7 (curfew) — no conflict'),

('CA', 2, 5, 1, 3.00, 6.00, NULL, NULL, '05:00', '22:00', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (2-6yr: 6hr at-workplace, 3hr work); Lab. Code §1308.7 (curfew) — no conflict'),

('CA', 6, 8, 1, 4.00, 8.00, 3.00, NULL, '05:00', '22:00', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (6-9yr: 8hr at-workplace on school days, 4hr work, 3hr schooling); Lab. Code §1308.7 (curfew) — no conflict, already = 8hr cap'),

('CA', 9, 15, 1, 5.00, 8.00, 3.00, 48.00, '05:00', '22:00', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (9-16yr: 9hr at-workplace on school days -> CAPPED to 8hr by Lab. Code §1308.7, more-protective-governs reconciliation, unconfirmed by counsel; 5hr work, 3hr schooling, fits exactly at 8)'),

('CA', 16, 17, 1, 6.00, 8.00, 3.00, 48.00, '05:00', '22:00', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (16-18yr: 10hr at-workplace on school days -> CAPPED to 8hr by Lab. Code §1308.7, more-protective-governs reconciliation, unconfirmed by counsel; 6hr work + 3hr schooling = 9hr EXCEEDS reconciled 8hr ceiling by 1hr — UNRESOLVED, flag every audit hit on this row for human review, do not silently drop either the schooling minimum or the 8hr cap');

-- Non-school-day rows — 8 CCR §11760 gives distinct, lower schooling-free
-- hour figures for non-school days for the 6-9, 9-16, and 16-18 bands;
-- Lab. Code §1308.7 extends the curfew to 00:30 on the evening preceding
-- a non-school day (no age qualifier in the statute).
INSERT INTO labor_law_rules
(state, min_age, max_age, school_day, max_work_hours_per_day, max_hours_at_workplace,
 min_school_hours, max_hours_per_week, earliest_start_time, latest_end_time,
 min_rest_between_calls_hours, required_break_minutes, effective_from, effective_to, source_citation)
VALUES
('CA', 6, 8, 0, 6.00, 7.00, NULL, NULL, '05:00', '00:30', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (6-9yr, non-school day: 6hr work + 1hr rest/recreation = 7hr at-workplace, no schooling component); Lab. Code §1308.7 (non-school-night curfew to 00:30) — no conflict, 7hr at-workplace is under both the native 8hr band ceiling and the Lab. Code 8hr/day cap'),

('CA', 9, 15, 0, 7.00, 8.00, NULL, 48.00, '05:00', '00:30', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (9-16yr, non-school day: 7hr work + 1hr rest/recreation = 8hr at-workplace, no schooling component); Lab. Code §1308.7 (non-school-night curfew to 00:30) — no conflict, 8hr at-workplace exactly equals the Lab. Code 8hr/day cap, same as the 6-9 school-day precedent'),

('CA', 16, 17, 0, 8.00, 8.00, NULL, 48.00, '05:00', '00:30', 12.00, 30,
 '2011-01-01', NULL, '8 CCR §11760 (16-18yr, non-school day: 8hr work + 1hr rest/recreation = 9hr at-workplace native) -> CAPPED to 8hr by Lab. Code §1308.7, more-protective-governs reconciliation, unconfirmed by counsel; 8hr work alone already reaches the Lab. Code daily cap, so the reg''s own +1hr at-workplace rest/recreation time numerically EXCEEDS the reconciled 8hr ceiling by 1hr — UNRESOLVED, same ambiguity as the 16-18/school-day row, flag every audit hit on this row for human review; Lab. Code §1308.7 (non-school-night curfew to 00:30, applies to any minor per statute''s plain text, no age qualifier — that 16-17-only version belongs to the separate general-employment §1391, not the entertainment-industry §1308.7 that governs here)');
