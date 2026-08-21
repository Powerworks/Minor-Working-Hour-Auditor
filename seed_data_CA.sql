-- Minor Working-Hour Auditor — seed data, California, sourced 2026-08-21
-- Primary sources: 8 Cal. Code Regs. §11760, §11761, §11763; Cal. Labor Code §1308.7.
-- RECONCILIATION: §11760 and §1308.7 conflict for the 16-18/school-day band
-- (work 6hr + schooling 3hr = 9hr exceeds the reconciled 8hr ceiling by 1hr).
-- This is flagged, not silently resolved — see labor_law_rules.source_citation
-- text on that row and the Audit Report's rule_confidence field (built in a
-- later slice). Non-school-day hour figures are PLACEHOLDER, not sourced yet.

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

-- Non-school-night curfew extension — Lab. Code §1308.7's own text
-- (curfew to 00:30), hour figures carried over as PLACEHOLDER pending
-- real non-school-day sourcing.
INSERT INTO labor_law_rules
(state, min_age, max_age, school_day, max_work_hours_per_day, max_hours_at_workplace,
 min_school_hours, max_hours_per_week, earliest_start_time, latest_end_time,
 min_rest_between_calls_hours, required_break_minutes, effective_from, effective_to, source_citation)
VALUES
('CA', 16, 17, 0, 6.00, 8.00, NULL, 48.00, '05:00', '00:30', 12.00, 30,
 '2011-01-01', NULL, 'Lab. Code §1308.7 (non-school-night curfew to 00:30) — PLACEHOLDER hour figures, not independently sourced for non-school days');
