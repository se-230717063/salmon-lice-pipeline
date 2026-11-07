-- Question: how does the frequency of reported lice reaching the analytical threshold vary over time?
-- Grain: source year/week, one report per locality/week before aggregation (no join fan-out).
-- Flag filter: flags_json. Available reports only; minimum farm count is applied visibly by the notebook.
SELECT c.year, c.week, COUNT(*) AS n, SUM(c.avg_adult_female_lice) AS sum_lice,
       SUM(CASE WHEN c.avg_adult_female_lice >= :threshold THEN 1 ELSE 0 END) AS reaching_threshold
FROM lice_weekly_clean c JOIN locality l USING(locality_key)
WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
  AND c.year BETWEEN :start_year AND :end_year
  AND c.avg_adult_female_lice_flag IN (SELECT value FROM json_each(:flags_json))
  AND c.avg_adult_female_lice IS NOT NULL
GROUP BY c.year,c.week ORDER BY c.year,c.week;
