-- Grain: one lice-report locality/year/week. No temperature or treatment join changes the grain.
-- Flag filter: flags_json, explicitly supplied by each caller; NULL measurements excluded.
-- Clock: stored source year/week; ISO Monday display convention documented in m4_calendar_sources.md.
SELECT l.locality_no, c.year, c.week, c.avg_adult_female_lice AS value,
       c.avg_adult_female_lice_flag AS flag
FROM lice_weekly_clean c
JOIN locality l USING (locality_key)
WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
  AND c.year BETWEEN :start_year AND :end_year
  AND c.avg_adult_female_lice_flag IN (SELECT value FROM json_each(:flags_json))
  AND c.avg_adult_female_lice IS NOT NULL
ORDER BY l.locality_no, c.year, c.week;
