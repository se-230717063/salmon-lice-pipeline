# Exploratory Analysis - Salmon Lice Pipeline

> Cagatay stage complete: M4 sections 2.1-2.4. Egemen's time, relationships,
> interval comparison and final synthesis remain pending. This is not a finished M4 submission.

## 1. Summary

The exploratory question is how frequently reported cohort weeks reach fixed adult-female
lice thresholds, and whether summaries, coverage and flag choices change the answer.
For the four complete years 2022-2025, 1,540 of 6,004 reports reach 0.2 lice/fish and
120 reach 0.5; these are analytical thresholds, not assigned legal limits.
Raw and primary-cleaned lice summaries agree, while excluding unusually high reports
changes the frequency substantially. Coverage varies strongly and only 71 of 160
complete farm-years meet the chosen 75% calendar coverage rule. These observed-data
results do not establish a temperature effect, a legal violation rate or predictive
ability; the interval comparison and temporal composition analysis remain for Egemen.
No measurement-cleaning bug has been found in this stage; since the M3 tag, attribution
wording was simplified without changing measurement values, flags or mapping decisions.

## 2. Raw versus cleaned

**Question:** among the selected cohort's reported weeks in complete source years,
what share has average adult-female lice **greater than or equal to** a fixed threshold?
The population is the 40 committed cohort localities, not all 2,710 registry entries.
The primary period is 2022-2025; 2026 is not a complete annual comparison period.

Both raw and clean estimates use observed reports as their denominator. Missing weeks
are not counted as clean weeks or as zero lice. There is no minimum farm-year coverage
for this pooled descriptive number; section 4 shows the consequences of adding one.
The primary clean filter retains `ok`, `unusual_high`, `unusual_low`; the strict
sensitivity uses `ok` only. Retained extremes can be genuine infestations, so they
are not automatically omitted from the headline descriptive frequency.

The following equivalent queries state the complete estimand explicitly; all values
are bound parameters, including JSON arrays of cohort IDs and accepted flags. The
executed reusable version is [m4_cagatay_key_number.sql](../sql/queries/m4_cagatay_key_number.sql),
which also computes raw values on exactly the strict-clean accepted keys.

Raw query: no M2 flags exist; all non-NULL reported lice values in the cohort/period.

```sql
SELECT COUNT(r.avg_adult_female_lice) AS n,
       SUM(CASE WHEN r.avg_adult_female_lice >= :threshold THEN 1 ELSE 0 END) AS reaching,
       AVG(CASE WHEN r.avg_adult_female_lice IS NOT NULL
                THEN CASE WHEN r.avg_adult_female_lice >= :threshold THEN 1.0 ELSE 0.0 END END) AS share
FROM lice_weekly r
JOIN locality l USING (locality_key)
WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
  AND r.year BETWEEN :start_year AND :end_year;
```

Clean query: accepted flags are explicitly supplied through `:flags_json`.

```sql
SELECT COUNT(c.avg_adult_female_lice) AS n,
       SUM(CASE WHEN c.avg_adult_female_lice >= :threshold THEN 1 ELSE 0 END) AS reaching,
       AVG(CASE WHEN c.avg_adult_female_lice IS NOT NULL
                THEN CASE WHEN c.avg_adult_female_lice >= :threshold THEN 1.0 ELSE 0.0 END END) AS share
FROM lice_weekly_clean c
JOIN locality l USING (locality_key)
WHERE l.locality_no IN (SELECT value FROM json_each(:cohort_json))
  AND c.year BETWEEN :start_year AND :end_year
  AND c.avg_adult_female_lice_flag IN (SELECT value FROM json_each(:flags_json));
```

Bindings: `start_year=2022`, `end_year=2025`, `threshold=0.2` or `0.5`;
`cohort_json` is the JSON encoding of `config/cohort.txt`. Primary `flags_json` is
`["ok","unusual_high","unusual_low"]`; strict is `["ok"]`.

| Threshold [lice/fish] | Layer / filter | n reports | Reaching threshold | Share |
|---:|---|---:|---:|---:|
| 0.2 | M2 raw, no flags | 6,004 | 1,540 | 25.6496% |
| 0.2 | Clean primary | 6,004 | 1,540 | 25.6496% |
| 0.2 | Clean strict | 5,881 | 1,417 | 24.0945% |
| 0.2 | Raw values on strict-clean keys | 5,881 | 1,417 | 24.0945% |
| 0.5 | M2 raw, no flags | 6,004 | 120 | 1.9987% |
| 0.5 | Clean primary | 6,004 | 120 | 1.9987% |
| 0.5 | Clean strict | 5,881 | 44 | 0.7482% |
| 0.5 | Raw values on strict-clean keys | 5,881 | 44 | 0.7482% |

The primary raw/clean difference is zero: no lice measurement was numerically rejected
in this period, and the primary filter retains flagged high values. The strict-filter
difference is a selection change, as the raw-on-strict-keys check reproduces it exactly;
123 reports, including 76 of the 120 reports reaching 0.5, are excluded. Rejecting the
196.18 C temperature does not alter this lice-only denominator because no temperature
join is part of this question; its consequence belongs to the later relationship analysis.

## 3. The question and its summary

The project ultimately asks whether future lice-limit exceedance can be predicted.
M4 addresses a descriptive precursor: **how often do reported farm weeks reach fixed
lice-count thresholds, and how do coverage and distributional choices change that answer?**
The primary summary is a share because the question concerns frequency, rather than
the average intensity of lice burden. The median answers a different question, the
typical reported count, and p95 describes the high-count tail. Neither is substituted
for the frequency merely because it gives a more striking ranking.

Comparative farm summaries include only farm-years with at least 75% of calendar weeks
reported: at least 39 of 52 in each complete study year. This leaves 3,306 reports,
71 farm-years and 37 farms. Full unrestricted rankings for all 40 farms, qualified
rankings and n for every estimate are printed in the executed notebook and saved in
[m4_cagatay_results.json](evidence/m4_cagatay_results.json). Ties receive competition
ranks rather than arbitrary ID-order ranks. Pooled farm ranks can still reflect the
different years that qualify for each farm; Egemen must check composition before
interpreting between-farm differences.

| Ranking question | Example farm | n qualified reports | Threshold share | Median [lice/fish] | p95 [lice/fish] | Share rank / median rank / p95 rank |
|---|---:|---:|---:|---:|---:|---|
| Frequent reports >=0.2 | 11800 | 102 | 57.8431% | 0.2300 | 0.4600 | 1 / 1 / 13 |
| Frequent reports >=0.2 | 36737 | 91 | 52.7473% | 0.2100 | 0.4500 | 2 / 2 / 16 |
| Frequent reports >=0.5 | 45025 | 46 | 13.0435% | 0.0000 | 3.4765 | 1 / 33 / 1 |
| Frequent reports >=0.5 | 12897 | 136 | 11.0294% | 0.1750 | 0.8600 | 2 / 5 / 3 |

Share and median ranks differ for 32/37 qualified farms at threshold 0.2 and 37/37
at 0.5, with the stated tie convention. Farm 45025 illustrates why: its qualified
reports have a zero median but a high tail, so a typical-week question and a severe-week
frequency question identify different features. These are conditional descriptions
of observed periods, not a stable ranking of intrinsic farm risk. No confidence interval
or hypothesis test is claimed for this stage's descriptive ranking.

## 4. What the data is made of

### Shape

![Overall histograms with three bin widths and ECDF](../figures/m4_cagatay_shape_overall.png)

The 6,004 primary-filter reports have median 0.0800, mean 0.1479, p95 0.4400 and
maximum 5.6833 lice/fish; 1,339 reports (22.30%) are exactly zero. The distribution has
a strong low-count concentration and a long right tail. That makes the mean an
incomplete answer to both the typical-report and threshold-frequency questions.
We compare histogram widths 0.05, 0.1 and 0.2 lice/fish. The selected 0.1 spacing
separates increments around the 0.2 and 0.5 thresholds without the especially coarse
merging of 0.2-wide bins or the jagged detail of 0.05-wide bins. The ECDF provides a
bin-free check; no log transform of zeros or smoothing is used.

![Common-scale yearly histograms and ECDFs](../figures/m4_cagatay_shape_years.png)

| Year | n reports | Median [lice/fish] | p95 [lice/fish] |
|---:|---:|---:|---:|
| 2022 | 1,503 | 0.0700 | 0.4500 |
| 2023 | 1,550 | 0.0700 | 0.3700 |
| 2024 | 1,352 | 0.1000 | 0.4445 |
| 2025 | 1,599 | 0.1000 | 0.4600 |

Yearly panels use identical axes and 0.1-wide bins. Histogram heights are fractions
of each year's n, while ECDFs show cumulative report shares. The lower typical counts
and upper tail occur in each year; differences between yearly curves may reflect
composition and reporting as well as conditions. These shapes use all available
primary-filter reports with no minimum coverage, making that denominator explicit.

### Coverage rule and sensitivity

![Calendar reporting coverage by farm and year](../figures/m4_cagatay_coverage.png)

The notebook prints a complete 40-by-5 farm/year table, including zero-report cells.
Calendar opportunities are a transparent common denominator, not a claim that stock
was present or reporting legally required in every week. No missing week is inserted
into the database. For 2026, the latest complete week at the October 10 retrieval is
week 40, giving 40 calendar opportunities per farm; the incomplete week 41 is excluded.
The source's ISO interpretation and further edge/calendar analysis remain for Egemen.

| Year | n reported lice weeks | Calendar opportunities | Coverage | Farm-years meeting 75% |
|---:|---:|---:|---:|---:|
| 2022 | 1,503 | 2,080 | 72.26% | 15/40 |
| 2023 | 1,550 | 2,080 | 74.52% | 21/40 |
| 2024 | 1,352 | 2,080 | 65.00% | 14/40 |
| 2025 | 1,599 | 2,080 | 76.88% | 21/40 |
| 2026, weeks 1-40 only | 946 | 1,600 | 59.13% | 13/40 |

The 75% rule demands three quarters of the full annual reporting grid for comparative
farm summaries. It is a documented pragmatic screen, not a guarantee of unbiased
coverage: the missing quarter can still be seasonally concentrated. We therefore
show both versions and do not silently discard the other 89 complete farm-years.

| Threshold | Coverage rule, primary flags | Farm-years | n reports | Reaching | Share |
|---:|---|---:|---:|---:|---:|
| 0.2 | Available reports, no minimum | 160 | 6,004 | 1,540 | 25.6496% |
| 0.2 | At least 75% per farm-year | 71 | 3,306 | 879 | 26.5880% |
| 0.5 | Available reports, no minimum | 160 | 6,004 | 120 | 1.9987% |
| 0.5 | At least 75% per farm-year | 71 | 3,306 | 61 | 1.8451% |

The effect is not simply that a stricter rule always raises the rate: it raises the
0.2 share and lowers the 0.5 share in this snapshot. This demonstrates estimand and
composition sensitivity, not a causal coverage effect. Filter sensitivity is shown
separately in section 2. Every estimate identifies its threshold, flag filter, period
and n; neither sample size nor a high apparent reporting share establishes national
representativeness for this deliberately selected cohort.

## 5. Time

Pending Egemen: justify the source clock, inspect edges, show two time scales and
check documented calendar windows. Do not infer geographic legal regimes from unverified codes.

## 6. Relationships

Pending Egemen: plot temperature versus lice before Pearson/Spearman; inspect drivers,
flag sensitivity and shared farm/time structure. No relationship result is asserted here.

## 7. The comparison

Pending Egemen: define temperature regimes, report the paired/clustered difference and
95% interval, check seasonal/farm composition and show subgroup results or insufficient
overlap. Repeated farm-years are not independent farms.

## 8. Findings

| ID | Finding | Evidence | Label | What would change it | Explored by |
|---|---|---|---|---|---|
| F-01 | Primary raw and clean lice frequencies agree at both fixed thresholds in 2022-2025 | Section 2; key-number SQL | Confirmed by arithmetic within this extract | Different values, period or accepted flags | Cagatay Oruk |
| F-02 | Excluding unusual lice reports lowers the 0.5 reported-week share from 1.9987% to 0.7482% | Section 2; raw-matched-key check | Confirmed filter/composition arithmetic | A different filter or source revision | Cagatay Oruk |
| F-03 | Typical-count and threshold-frequency farm rankings need not agree | Section 3; 45025 has median zero but highest qualified >=0.5 share | Exploratory | Common-period comparison, more years or coverage revision | Cagatay Oruk |
| F-04 | Only 71/160 complete farm-years meet 75% reporting coverage, and enforcing it changes threshold shares in different directions | Coverage table and figure | Confirmed arithmetic; broader interpretation exploratory | Another coverage threshold, production-status denominators or new data | Cagatay Oruk |
| F-05 | Reported lice counts show a low-count concentration and long upper tail in each complete year | Overall/yearly histogram and ECDF; n=6004 | Exploratory | New periods, an alternative cohort or source corrections | Cagatay Oruk |

Egemen's F-10 onward entries are pending; IDs are reserved ranges, not a required count.
The [look log](evidence/m4_look_log.json) records 19 Cagatay configuration looks:
eight layer/threshold estimates, two ranking comparisons, three histogram widths,
four annual shapes and two coverage comparisons. These are not 19 independent tests.
Egemen must append every later comparison before selecting the final interval result.

### Back to cleaning

No new measurement-cleaning defect was found in Cagatay's sections 2.1-2.4. Existing
high lice flags are deliberately retained, not errors to remove. Existing M3 coverage,
unknown reporting mechanisms and temperature suspicions remain limitations. A layout
issue found during figure review was corrected in plotting code, not in source data.
Egemen must revisit this list after his analyses and record any real cleaning correction
in clean.py and the M3 issues register, preserving the original m3 tag.

### Forward to modelling

Pending Egemen's final synthesis. Preliminary cautions: calendar-aligned lags rather
than row shifts, missing reports not zero, temporally separated evaluation, seasonality,
thin groups and treatment fields whose availability may follow the outcome.

## 9. What we can't say

Pending final synthesis after Egemen. Current results describe available cohort reports,
not all Norwegian farms, unobserved stock status or farm-specific statutory compliance.
The notebook does not fit a predictive model, estimate causal temperature effects or
supply an independence-based interval for its descriptive farm rankings.

### Cagatay-stage execution evidence

[Fresh-build verification](evidence/m4_cagatay_verification.json) records exit code 0,
unchanged before/after contents of all 17 tables, two rejected write attempts through
the read-only connection, identical fresh/workspace results and identical SHA-256
digests for the three regenerated PNGs. The notebook is committed with actual Jupyter
outputs, and [the hash manifest](evidence/m4_readonly_hashes.json) records every table.
These checks cover the current stage; they must run again after Egemen's integration.

| Figure check | Overall shape | Yearly shape | Coverage |
|---|---|---|---|
| Finding title + question subtitle | Yes | Yes | Yes, 71/160 |
| Units / source-clock context / n / flag filter / coverage rule | Yes | Yes, n per panel | Yes, n/expected per cell |
| Zero-based bars / common scales | Counts start at zero; common histogram axes | Fractions start at zero; common axes by row | Common 0-1 colour scale |
| Missing periods not bridged / no dual y-axis | No temporal lines; no dual axis | Separate groups; no temporal interpolation | Zero coverage explicitly shown; no interpolation |
| Relevant reference | Analytical 0.2 and 0.5 | Analytical 0.2 and 0.5 | 75% reference on colour scale |
