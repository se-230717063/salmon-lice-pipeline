-- Question: How does the proportion of reporting weeks with average adult female lice exceeding the 
--           statutory threshold (>= 0.2) vary across 2 °C sea temperature bands?
-- Result grain: One row per 2 °C sea temperature band.
-- Why aggregation is correct at this grain:
--   Readings from lice_weekly and sea_temperature_weekly are joined 1-to-1 on (locality_key, year, week),
--   so no join fan-out or Cartesian multiplication occurs. Rows are aggregated into discrete 2 °C bands.
--   Unreported weeks (has_reported = 0) and missing values (NULL) are excluded so AVG and SUM reflect true measurements.

SELECT
    CAST(FLOOR(t.sea_temperature / 2.0) * 2 AS INTEGER) || ' to ' ||
    CAST(FLOOR(t.sea_temperature / 2.0) * 2 + 2 AS INTEGER) || ' °C' AS temperature_band,
    COUNT(*) AS total_reporting_weeks,
    SUM(CASE WHEN l.avg_adult_female_lice >= 0.2 THEN 1 ELSE 0 END) AS exceedance_weeks,
    ROUND(100.0 * SUM(CASE WHEN l.avg_adult_female_lice >= 0.2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS exceedance_rate_pct,
    ROUND(AVG(l.avg_adult_female_lice), 3) AS mean_avg_female_lice
FROM lice_weekly l
JOIN sea_temperature_weekly t
    ON l.locality_key = t.locality_key
    AND l.year = t.year
    AND l.week = t.week
WHERE t.has_reported = 1
  AND t.sea_temperature IS NOT NULL
  AND l.avg_adult_female_lice IS NOT NULL
GROUP BY FLOOR(t.sea_temperature / 2.0)
ORDER BY FLOOR(t.sea_temperature / 2.0);
