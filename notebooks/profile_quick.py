"""Read-only M3 profile. Run from any working directory; no third-party packages."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from db import DB_PATH, snapshot

MEASUREMENTS = {
    "lice_weekly": "SELECT locality_key, year, week, avg_adult_female_lice, retrieved_at FROM lice_weekly ORDER BY locality_key, year, week",
    "sea_temperature_weekly": "SELECT locality_key, year, week, sea_temperature, retrieved_at, has_reported FROM sea_temperature_weekly ORDER BY locality_key, year, week",
}


def quantile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def profile(db_path=DB_PATH):
    con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        result = {"m2_snapshot": snapshot(con), "foreign_key_violations": con.execute("PRAGMA foreign_key_check").fetchall()}
        names = dict(con.execute("SELECT locality_key, locality_no FROM locality"))
        cohort = [int(v) for v in (ROOT / "config/cohort.txt").read_text().split()]
        result["cohort_size"] = len(cohort)
        result["measurements"] = {}
        for table, sql in MEASUREMENTS.items():
            rows = con.execute(sql).fetchall()
            grouped = defaultdict(list)
            for row in rows:
                grouped[row[0]].append(row)
            entities, invalid_examples, future_examples = [], [], []
            for key, records in sorted(grouped.items()):
                values = [r[3] for r in records if r[3] is not None]
                observed_dates, future = [], 0
                invalid_iso = 0
                runs, current, longest = [], [], 0
                jumps = []
                for row in records:
                    try:
                        day = date.fromisocalendar(row[1], row[2], 1)
                    except ValueError:
                        invalid_iso += 1
                        continue
                    retrieved = datetime.fromisoformat(row[4].replace("Z", "+00:00")).date()
                    if day > retrieved:
                        future += 1
                        if len(future_examples) < 5:
                            future_examples.append([names[key], row[1], row[2], row[3], row[4]])
                    else:
                        observed_dates.append((day, row[3]))
                    if current and day - current[-1][0] == timedelta(days=7) and row[3] is not None and row[3] == current[-1][1]:
                        current.append((day, row[3]))
                    else:
                        if len(current) >= 6:
                            runs.append([str(current[0][0]), str(current[-1][0]), current[0][1], len(current)])
                        current = [(day, row[3])] if row[3] is not None else []
                    longest = max(longest, len(current))
                if len(current) >= 6:
                    runs.append([str(current[0][0]), str(current[-1][0]), current[0][1], len(current)])
                for previous, following in zip(observed_dates, observed_dates[1:]):
                    if following[0] - previous[0] == timedelta(days=7) and previous[1] is not None and following[1] is not None:
                        jumps.append([abs(following[1] - previous[1]), str(following[0]), previous[1], following[1]])
                expected = (max(d for d, _ in observed_dates) - min(d for d, _ in observed_dates)).days // 7 + 1 if observed_dates else 0
                historical_nulls = sum(v is None for _, v in observed_dates)
                entities.append({"locality_no": names[key], "rows": len(records), "nulls": len(records)-len(values),
                    "min": min(values) if values else None, "median": median(values) if values else None,
                    "max": max(values) if values else None, "q1": quantile(values, .25), "q3": quantile(values, .75),
                    "most_common": Counter(values).most_common(5), "first": str(min(d for d, _ in observed_dates)) if observed_dates else None,
                    "last": str(max(d for d, _ in observed_dates)) if observed_dates else None,
                    "absent_weeks_between_first_last": expected-len(observed_dates), "historical_nulls": historical_nulls,
                    "historical_null_share": historical_nulls / len(observed_dates) if observed_dates else None,
                    "future_rows": future, "invalid_iso_weeks": invalid_iso, "longest_exact_run": longest,
                    "runs_at_least_6": runs, "largest_adjacent_jumps": sorted(jumps, reverse=True)[:5]})
                for row in records:
                    if row[3] is not None and (row[3] < 0 if table == "lice_weekly" else not -5 <= row[3] <= 40):
                        invalid_examples.append([names[key], row[1], row[2], row[3]])
            per_year = []
            for year in sorted({r[1] for r in rows}):
                selected = [r for r in rows if r[1] == year]
                per_year.append({"year": year, "rows": len(selected), "nulls": sum(r[3] is None for r in selected)})
            result["measurements"][table] = {"rows": len(rows), "entities": len(grouped), "nulls": sum(r[3] is None for r in rows),
                "screening_invalid_examples": invalid_examples, "future_examples": future_examples,
                "per_year": per_year, "per_entity": entities}
        result["temperature_reporting_states"] = con.execute("SELECT has_reported, sea_temperature IS NULL, COUNT(*) FROM sea_temperature_weekly GROUP BY has_reported, sea_temperature IS NULL").fetchall()
        # These inventories are evidence for Egemen, not mapping or identity decisions.
        result["category_inventory_for_egemen"] = {}
        for label, sql in {
            "treatment_category": "SELECT category, COUNT(*) FROM treatment_event GROUP BY category",
            "treatment_type": "SELECT treatment_type, COUNT(*) FROM treatment_event GROUP BY treatment_type",
            "substance_name": "SELECT substance_name, COUNT(*) FROM treatment_event GROUP BY substance_name",
            "substance_id": "SELECT substance_id, COUNT(*) FROM treatment_event GROUP BY substance_id",
            "municipality_5054": "SELECT name, COUNT(*) FROM municipality WHERE municipality_no = '5054' GROUP BY name",
        }.items():
            result["category_inventory_for_egemen"][label] = [[repr(value), count] for value, count in con.execute(sql)]
        result["text_inventory_for_egemen"] = {
            label: [repr(row[0]) for row in con.execute(sql)]
            for label, sql in {
                "municipality_names": "SELECT DISTINCT name FROM municipality ORDER BY name",
                "locality_names": "SELECT DISTINCT name FROM locality ORDER BY name",
                "registry_versions": "SELECT DISTINCT registry_version FROM locality ORDER BY registry_version",
            }.items()
        }
        result["treatment_coverage_for_egemen"] = con.execute("SELECT l.locality_no, COUNT(t.week), MIN(t.year), MAX(t.year) FROM locality l LEFT JOIN treatment_weekly t ON l.locality_key=t.locality_key WHERE l.locality_no IN (SELECT locality_no FROM locality WHERE locality_key IN (SELECT locality_key FROM lice_weekly)) GROUP BY l.locality_no ORDER BY l.locality_no").fetchall()
        result["snapshot_unchanged"] = result["m2_snapshot"] == snapshot(con)
        return result
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    print(json.dumps(profile(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
