-- Question: what is the contemporaneous temperature/lice relationship on observed paired reports?
-- Grain: locality/year/week; both composite keys are unique, so joining is one-to-one.
-- Clean flags: lice_flags_json and temperature_flags_json, always supplied explicitly.
-- Raw influence sensitivity uses raw measurements on all reported pairs, without a clean flag filter.
SELECT r.locality_key, l.locality_no, r.year, r.week,
       CASE WHEN :layer='raw' THEN r.avg_adult_female_lice ELSE c.avg_adult_female_lice END AS lice,
       CASE WHEN :layer='raw' THEN t.sea_temperature ELSE tc.sea_temperature END AS temperature
FROM lice_weekly r JOIN locality l USING(locality_key)
JOIN sea_temperature_weekly t USING(locality_key,year,week)
JOIN lice_weekly_clean c USING(locality_key,year,week)
JOIN sea_temperature_weekly_clean tc USING(locality_key,year,week)
WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
  AND r.year BETWEEN :start_year AND :end_year
  AND ((:layer='raw' AND r.avg_adult_female_lice IS NOT NULL AND t.has_reported=1 AND t.sea_temperature IS NOT NULL)
    OR (:layer='clean' AND c.avg_adult_female_lice_flag IN (SELECT value FROM json_each(:lice_flags_json))
        AND tc.sea_temperature_flag IN (SELECT value FROM json_each(:temperature_flags_json))
        AND c.avg_adult_female_lice IS NOT NULL AND tc.sea_temperature IS NOT NULL))
ORDER BY l.locality_no,r.year,r.week;
