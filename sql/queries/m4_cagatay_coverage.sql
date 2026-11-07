-- Grain: locality/year. Filtered reported weeks, not farm production-status opportunities.
-- Flag filter: flags_json; NULL lice excluded. Last coverage year stops at coverage_end_week.
-- Python creates the full cohort/calendar reporting-opportunity grid, without inserting DB rows.
SELECT l.locality_no, c.year, COUNT(*) AS n,
       SUM(CASE WHEN c.avg_adult_female_lice >= :threshold THEN 1 ELSE 0 END) AS reaching_threshold
FROM lice_weekly_clean c
JOIN locality l USING (locality_key)
WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
  AND c.year BETWEEN :start_year AND :coverage_end_year
  AND (c.year < :coverage_end_year OR c.week <= :coverage_end_week)
  AND c.avg_adult_female_lice_flag IN (SELECT value FROM json_each(:flags_json))
  AND c.avg_adult_female_lice IS NOT NULL
GROUP BY l.locality_no, c.year
ORDER BY l.locality_no, c.year;
