-- Question: what share of reported cohort weeks reaches a fixed analytical threshold?
-- Grain: one result for one layer/flag filter/threshold over the configured complete years.
-- Raw has no flags; raw_matched applies the selected clean-key filter to raw values.
-- Clean uses exactly flags_json. Available reports are the denominator, never missing weeks.
WITH observations AS (
    SELECT CASE WHEN :layer IN ('raw', 'raw_matched') THEN r.avg_adult_female_lice
                ELSE c.avg_adult_female_lice END AS value
    FROM lice_weekly r
    JOIN locality l USING (locality_key)
    JOIN lice_weekly_clean c USING (locality_key, year, week)
    WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
      AND r.year BETWEEN :start_year AND :end_year
      AND (:layer = 'raw' OR c.avg_adult_female_lice_flag IN (SELECT value FROM json_each(:flags_json)))
)
SELECT COUNT(value) AS n,
       COALESCE(SUM(CASE WHEN value >= :threshold THEN 1 ELSE 0 END), 0) AS reaching_threshold,
       AVG(CASE WHEN value IS NOT NULL THEN CASE WHEN value >= :threshold THEN 1.0 ELSE 0.0 END END) AS share,
       AVG(value) AS mean_lice
FROM observations;
