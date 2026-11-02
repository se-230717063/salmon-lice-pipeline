# Cleaning Report - Salmon Lice Pipeline

> Working report: Cagatay's measurement investigation and sections 1-5 are complete.
> Egemen must finish the category/identity investigation, sections 6-8, validate.py,
> README and final integration before this is an M3 submission. Counts below describe
> the measurement stage, not a fully validated M3 pipeline.

## 1. Summary

We profiled the M2 database for the 40-locality, 2022-2026 cohort using an executed,
read-only [notebook](../notebooks/m3_profile.ipynb). The measurement tables contain
6,951 lice reports and 10,440 temperature reporting-status rows, while the registry
contains 2,710 localities, not 2,710 time-series subjects. The most important findings
are historical non-reporting, future temperature placeholders, one screened-invalid
temperature, and several suspicious sequences whose causes remain unknown.
The measurement cleaned layer preserves every key, row, raw measurement and retrieval
timestamp, leaves missing values unfilled, replaces only the screened-invalid
temperature with NULL, and retains statistically unusual and sequentially suspect
measurements. Hashes of all seven M2 tables match before and after cleaning, and a
fresh rebuild from landed raw data matches the existing M2 database. No M2 loader or
schema correction was needed; the shared connect helper gained a backwards-compatible
read-only option for profiling. Category/identity decisions and full validation remain
for Egemen, and measurement causes cannot be established from these reports alone.

## 2. Profile highlights

Reproduction: `python src/load.py`, then run every cell of
[`notebooks/m3_profile.ipynb`](../notebooks/m3_profile.ipynb). The notebook requires
only the Python standard library and the M2 database, not clean tables. A machine-readable
equivalent is available through `python notebooks/profile_quick.py`.

| Table | Rows | Localities | Explicit NULL measurements | Interpretation |
|---|---:|---:|---:|---|
| lice_weekly | 6,951 | 40 | 0 | Missing reports appear as absent weeks, not NULL rows |
| sea_temperature_weekly | 10,440 | 40 | 3,234 | 2,754 historical non-reports plus 480 future placeholders |

| Year | Lice rows | Temperature rows | Temperature NULLs, including future placeholders |
|---|---:|---:|---:|
| 2022 | 1,503 | 2,080 | 504 |
| 2023 | 1,550 | 2,080 | 475 |
| 2024 | 1,352 | 2,080 | 653 |
| 2025 | 1,599 | 2,080 | 441 |
| 2026 | 947 | 2,120 | 1,161 |

The notebook lists count, NULL share, minimum, median, maximum, modes and first/last
period for each locality, as well as consecutive-week jumps and repeated runs. Within
each locality's first-to-last lice reporting span there are 2,487 absent weeks in total.
This is a bounded coverage statistic: it excludes leading/trailing gaps and is not the
number of missing lice rows across a newly invented complete panel. Historical
temperature non-reporting ranges from 24/249 weeks (9.64%) to 119/249 (47.79%) across
localities, so complete-case comparisons have unequal coverage.

| Historical temperature status | Lice report present | Lice report absent |
|---|---:|---:|
| has_reported = 0 | 0 | 2,754 |
| has_reported = 1 | 6,951 | 255 |

Historical periods are selected by comparing the ISO week's Monday with the row's
retrieval date. The currently incomplete retrieval week is allowed; later weeks are
not treated as elapsed reporting opportunities. The strong overlap of missing series
is evidence of a shared reporting process, not proof of farm closure or sensor failure.

## 3. Issues register

Counts are observations or flags at this stage; overlapping investigations do not imply
additional rows. Cause labels distinguish evidence from interpretation.

| ID | Family | Table.column | What / where / how many | Evidence and cause | Decision | Flag | Investigated by |
|---|---|---|---|---|---|---|---|
| I-01 | Missing | sea_temperature_weekly.sea_temperature | 2,754 historical NULLs; all 40 localities affected unequally | Raw has_reported=0 and NULL agree; confirmed recorded non-reporting, underlying reason unknown | Keep NULL; distinguish from future weeks | missing_not_reported | Cagatay Oruk |
| I-02 | Missing / time | sea_temperature_weekly | 480 rows, 2026 weeks 42-53, 12 per locality | Retrieval on 2026-10-10 precedes these ISO weeks; confirmed temporal relationship | Retain every placeholder, exclude from elapsed-period denominators | future_placeholder | Cagatay Oruk |
| I-03 | Missing | lice_weekly | 2,487 absent weeks within individual observed spans | Notebook first/last-week accounting; cause unknown | Do not add or impute rows; require explicit M4 coverage handling | No stored flag: there is no source row | Cagatay Oruk |
| I-04 | Invalid | sea_temperature_weekly.sea_temperature | Locality 13229, 2025-W24, 196.18 C | Neighbours 11.45 and 14.8 C; outside broad -5..40 C screening envelope; inferred measurement/entry problem, exact cause unknown | Raw retained; cleaned NULL; no guessed decimal correction | invalid_range | Cagatay Oruk |
| I-05 | Across rows | sea_temperature_weekly.sea_temperature | Four exact runs, 31 rows: locality 10324 (8+8), 13870 (6+9) | Consecutive ISO weeks, unchanged numeric value; cause unknown, rounding is possible | Flag for review and retain value | suspect_stuck | Cagatay Oruk |
| I-06 | Across rows | sea_temperature_weekly.sea_temperature | Five isolated spikes, including 34.29 C at 22095, 2025-W51 | Both week-to-week differences >=8 C, neighbours within 2 C; cause unknown | Retain values; do not call confirmed faults | suspect_spike | Cagatay Oruk |
| I-07 | Unusual | lice_weekly.avg_adult_female_lice | 138 high values relative to each locality | Valid-data outer IQR fences; no evidence these are errors | Preserve every value | unusual_high | Cagatay Oruk |
| I-08 | Unusual | sea_temperature_weekly.sea_temperature | Five low values, locality 11922 | Per-locality outer IQR fence; zero not established as a sentinel | Preserve every value | unusual_low | Cagatay Oruk |
| I-09 | Across rows | lice_weekly.avg_adult_female_lice | Long exact runs are zero; longest 42 consecutive weeks at 13226 | Zero is a possible count; repetition alone cannot identify malfunction | Keep zero; do not apply temperature stuck rule to lice | ok, unless another rule applies | Cagatay Oruk |
| I-10 | Across rows / units | sea_temperature_weekly.sea_temperature | Seven candidate boundaries in localities 11922 and 13870 | Adjacent four-week medians differ >=8 C; six boundaries surround a zero interval at 11922, not six independent events | Unknown cause; no unit conversion or automatic deletion | Existing value flags only; diagnostic in notebook | Cagatay Oruk |

### Checked and not found

| Family | Check | Result / scope |
|---|---|---|
| Invalid | Numeric lice value < 0 | 0; no negative lice values |
| Invalid | date.fromisocalendar(year, week, 1) | 0 invalid ISO measurement weeks |
| Across fields | has_reported=0 with value, or has_reported=1 with NULL | 0 contradictions |
| Invalid / time | Non-NULL measurements in weeks after retrieval | 0 |
| Identity / references | PRAGMA foreign_key_check; measurement locality coverage | No orphan FK; all 40 cohort localities present; this is not proof against re-registration |
| Text/categories/units | repr() inventories of registry names/versions and treatment vocabularies | Inventories executed; decisions and semantic unit/identity review assigned to Egemen, not claimed complete |

## 4. Missing values

**Future placeholders.** Their temporal cause is confirmed by dates, not inferred from
NULL alone. They are structural missingness: the measurement week had not happened.
An MCAR interpretation is inappropriate. If a statistical mechanism must be attached
to this pattern, observability is determined by observed calendar/retrieval variables
(a deterministic MAR-like selection rule), rather than a random equipment outage.
They remain in the source-grain clean table but must not inflate M4 historical missing
rates. Freshness should be measured against the latest expected retrieval period,
not blindly against the date an analyst opens this snapshot.

**Historical non-reporting.** Every one of the 2,754 non-reported temperature weeks
also lacks a lice report; another 255 reported-temperature weeks lack lice reports.
This pattern and the large between-locality coverage differences do not support
assuming independent random loss. Our working hypothesis is activity/reporting-dependent
selection, potentially MNAR if unobserved production status or lice conditions affect
whether reporting occurs. This is inferred and weak: the data do not identify stock
presence, maintenance or reporting obligations in each week, so MAR conditional on
locality/calendar cannot be distinguished from MNAR. We explicitly do not claim a
proven missingness mechanism. M4 should stratify coverage by locality and period,
show denominators and test whether its conclusions depend on high-coverage subsets.

**Absent lice weeks.** Zero explicit NULLs does not imply complete coverage. An absent
week is not a recorded zero and is not inserted into the cleaned table. The within-span
gap count understates total unobserved cohort-calendar coverage by design. Calendar
lags in later analyses must join on actual weeks rather than shift consecutive rows.
No averaging, forward filling, interpolation, or replacement with zero occurs in M3.
No missing flag states a cause such as maintenance or saturation without evidence.

## 5. Flags and rules

The raw measurement columns copy M2 values exactly. Each measurement has one mutually
exclusive TEXT NOT NULL flag constrained by CHECK. First matching rule wins. Rules
are applied after any established identity/unit resolution; at this handoff no identity
merge or unit conversion is established, so current grouping is by M2 locality_key.
If Egemen finds an identity split, he must update grouping before statistical flags
and rerun this notebook, the cleaner and evidence.

| Order | Flag | Rule | Cleaned value | Lice count | Temperature count |
|---|---|---|---|---:|---:|
| 1 | invalid_iso_week | ISO calendar rejects year/week | NULL | 0 | 0 |
| 2 | future_placeholder | Future week, NULL temperature, has_reported=0 | NULL | 0 | 480 |
| 2 | future_observation | Other row whose week starts after retrieval | NULL | 0 | 0 |
| 3 | reporting_conflict | Reported status contradicts temperature presence | NULL | 0 | 0 |
| 4 | missing_not_reported | Historical temperature, has_reported=0 | NULL | 0 | 2,754 |
| 4 | missing_unknown | Other NULL measurement | NULL | 0 | 0 |
| 5 | invalid_negative | Lice count <0 | NULL | 0 | 0 |
| 5 | invalid_range | Nonfinite number, or temperature outside -5..40 C | NULL | 0 | 1 |
| 6 | suspect_stuck | Temperature identical for >=6 consecutive ISO weeks | Raw value | 0 | 31 |
| 7 | suspect_spike | Isolated temperature jump with agreeing neighbours | Raw value | 0 | 5 |
| 8 | unusual_low | Valid observation below locality's Q1-3*IQR | Raw value | 0 | 5 |
| 8 | unusual_high | Valid observation above locality's Q3+3*IQR | Raw value | 138 | 0 |
| 9 | ok | No preceding rule applies | Raw value | 6,813 | 7,164 |
| | **Total** | | | **6,951** | **10,440** |

IQR statistics exclude invalid, missing and future observations. They use all otherwise
eligible observations before sequence-marker precedence is assigned. Quantiles use
linear interpolation at (n-1)*p. We do not use mean +/- three standard deviations.
We inspected the flagged sequence examples and locality flag counts in the notebook;
no unusual value was discarded merely for being extreme. A positive bit-count spike
can be a real infestation, and a repeated rounded temperature need not be a broken sensor.

### Constants and sensitivity

All cleaner constants are in [clean_config.py](../src/clean_config.py).

| Constant | Value | Reason and sensitivity |
|---|---:|---|
| TEMP_MIN_C | -5 | A deliberately broad screening margin below ordinary ocean freezing temperatures; no observations approach it in this snapshot |
| TEMP_MAX_C | 40 | Broad margin above NOAA's approximately 36 C global surface extreme, not a provider specification or a salmon welfare limit; rejects 196.18 but retains 34.29 |
| IQR_MULTIPLIER | 3 | Conservative outer fence, used as a review flag only; lice unusual counts are 327, 138 and 81 at multipliers 1.5, 3 and 4 |
| MIN_IQR_OBSERVATIONS | 20 | Require approximately half a year of weekly information before estimating fences; a pragmatic threshold, not statistically optimal; all current localities qualify |
| STUCK_RUN_WEEKS | 6 | Six identical weekly values warrant review; this heuristic flags four temperature runs and does not diagnose their cause; lowering it would flag more rounded plateaus |
| TEMP_SPIKE_DELTA_C | 8 | Large one-week departure in this dataset; applied only when both neighbours agree, so seasonal changes are not automatically errors; heuristic, values are retained |
| TEMP_SPIKE_NEIGHBOUR_C | 2 | Restricts isolated spikes to similar neighbouring temperatures; wider tolerance would admit more ambiguous changes |

The bounds are an inferred operational decision. [NOAA's ocean-layer reference](https://www.noaa.gov/jetstream/ocean/layers-of-ocean)
describes surface temperatures around -2 to 36 C; it does not prescribe our -5..40 C
screen or explain the anomalous report. Sensitivity screens reject two observations
at -3..30 C and one at both -5..40 and -10..50 C. We choose the broader middle screen
to avoid silently discarding the 34.29 C candidate. Temperature IQR multipliers 1.5,
3 and 4 flag six, five and zero low observations respectively, after sequence precedence.
Zero-width IQR disables the statistical rule rather than flagging every departure.

Two additional **profiling-only** constants in profile_quick.py compare adjacent
four-week medians and flag differences of at least 8 C. Four weeks seek persistence
beyond a single spike; 8 C is a broad candidate threshold matching the spike review
scale. They do not change any clean value or add a cleaner rule, and seasonal or zero
intervals can trigger them. Without provider logs, conversion of these sequences into
another unit would be speculation.

## 6. Mapping and identity decisions

**Egemen's section - pending.** Complete the independent text/category/identity and
treatment investigation, add reviewed CSVs, record exact/normalised/fuzzy-proposal
match counts and unmatched values. Add Egemen's genuine findings to the issues register.
Do not insert a fictional identity merge merely to fill a mapping table.

## 7. Counts and validation

**Egemen's section - pending final integration and validate.py.** Cagatay's reproducible
measurement-stage evidence lives in [m3_measurement_safety.json](evidence/m3_measurement_safety.json),
[first clean run](evidence/m3_measurements_run1.txt) and
[second clean run](evidence/m3_measurements_run2.txt). It covers all M2 hashes,
raw/key preservation, idempotence, rollback, and threshold restoration, but is not a
replacement for the required validate.py checks or deliberately failing each STOP.
Final category counts, WARN classifications and final pipeline outputs must be added here.

## 8. What we can't say

**Egemen's section - pending.** Incorporate the measurement limitations above and your
own category/identity findings. No confirmed sensor diagnosis, missingness mechanism,
automatic entity merge, no-treatment interpretation, or causal temperature/lice
relationship has been established by Cagatay's measurement work.
