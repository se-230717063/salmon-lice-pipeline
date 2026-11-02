"""Reproducible safety evidence for Cagatay's measurement stage, on disposable DBs.

Not a replacement for Egemen's required validate.py or its STOP injection tests.
Run: python notebooks/check_m3_safety.py
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import clean_config
import db
from clean import CLEAN_SNAPSHOT_SQL, SimulatedCleanFailure, run_clean
from clean_measurements import clean_rows
from db import DB_PATH, connect, snapshot
from load import run_load


def clean_snapshot(con):
    return {table: hashlib.sha256(repr(con.execute(sql).fetchall()).encode("utf-8")).hexdigest()
            for table, sql in CLEAN_SNAPSHOT_SQL.items()}


def verify(condition, name, results):
    if not condition:
        raise RuntimeError("FAIL: " + name)
    results.append({"check": name, "result": "PASS"})


def run_checks():
    results = []
    parent = ROOT / "tmp/m3"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as directory:
        rebuilt = Path(directory) / "rebuilt.db"
        run_load(db_path=rebuilt, quiet=True)
        con = connect(rebuilt)
        baseline = snapshot(con)
        con.close()
        original_path = db.DB_PATH
        try:
            db.DB_PATH = rebuilt
            namespace = {"__name__": "__main__"}
            notebook = json.loads((ROOT / "notebooks/m3_profile.ipynb").read_text(encoding="utf-8"))
            with contextlib.redirect_stdout(io.StringIO()):
                for cell in notebook["cells"]:
                    if cell["cell_type"] == "code":
                        exec(compile("".join(cell["source"]), "m3_profile_fresh_build", "exec"), namespace)
            verify(True, "notebook executes top-to-bottom on fresh M2 without clean tables", results)
        finally:
            db.DB_PATH = original_path
        source = connect(DB_PATH)
        verify(snapshot(source) == baseline, "fresh M2 rebuild matches existing M2 contents", results)
        source.close()

        # Failure on first build must also roll back CREATE TABLE statements.
        try:
            run_clean(rebuilt, fail_after_rows=1000, quiet=True)
        except SimulatedCleanFailure:
            pass
        else:
            raise RuntimeError("Failure injection did not fire")
        con = connect(rebuilt)
        verify(snapshot(con) == baseline, "first-build failure preserves all M2 hashes", results)
        verify(not con.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_clean'").fetchall(),
               "first-build failure rolls back clean schema as well as rows", results)
        con.close()

        first = run_clean(rebuilt, quiet=True)
        con = connect(rebuilt)
        before = clean_snapshot(con)
        baseline_contents = {name: con.execute(sql).fetchall() for name, sql in CLEAN_SNAPSHOT_SQL.items()}
        verify(snapshot(con) == baseline, "successful clean preserves all seven M2 hashes", results)
        for name, raw_sql, cleaned_sql in (
            ("lice", "SELECT locality_key, year, week, avg_adult_female_lice FROM lice_weekly ORDER BY locality_key, year, week", "SELECT locality_key, year, week, avg_adult_female_lice_raw FROM lice_weekly_clean ORDER BY locality_key, year, week"),
            ("temperature", "SELECT locality_key, year, week, sea_temperature FROM sea_temperature_weekly ORDER BY locality_key, year, week", "SELECT locality_key, year, week, sea_temperature_raw FROM sea_temperature_weekly_clean ORDER BY locality_key, year, week"),
        ):
            verify(con.execute(raw_sql).fetchall() == con.execute(cleaned_sql).fetchall(),
                   name + " preserves every key, row and raw value", results)
        verify(con.execute("PRAGMA foreign_key_check").fetchall() == [], "all declared foreign keys resolve", results)
        verify(all(row[-1] == 1 for row in con.execute("PRAGMA table_list") if row[1] not in ("sqlite_schema", "sqlite_temp_schema")),
               "all M2 and M3 tables are STRICT", results)
        verify(con.execute("SELECT COUNT(*) FROM sea_temperature_weekly_clean WHERE sea_temperature < ? OR sea_temperature > ?", (clean_config.TEMP_MIN_C, clean_config.TEMP_MAX_C)).fetchone()[0] == 0,
               "no screened impossible temperature survives", results)
        verify(con.execute("SELECT COUNT(*) FROM lice_weekly_clean WHERE avg_adult_female_lice < ?", (0,)).fetchone()[0] == 0,
               "no negative cleaned lice count survives", results)
        verify(con.execute("SELECT COUNT(*) FROM sea_temperature_weekly_clean WHERE sea_temperature_flag IN ('unusual_high', 'unusual_low', 'suspect_stuck', 'suspect_spike') AND sea_temperature IS NOT sea_temperature_raw").fetchone()[0] == 0,
               "unusual and sequentially suspect measurements are retained unchanged", results)
        con.close()
        run_clean(rebuilt, quiet=True)
        con = connect(rebuilt)
        verify(clean_snapshot(con) == before, "second build has identical measurement contents", results)
        con.close()
        try:
            run_clean(rebuilt, fail_after_rows=1000, quiet=True)
        except SimulatedCleanFailure:
            pass
        else:
            raise RuntimeError("Failure injection did not fire")
        con = connect(rebuilt)
        verify(clean_snapshot(con) == before and snapshot(con) == baseline,
               "failed rebuild preserves previous cleaned contents and M2", results)
        con.close()
        original = clean_config.IQR_MULTIPLIER
        try:
            clean_config.IQR_MULTIPLIER = 4.0
            run_clean(rebuilt, quiet=True)
            con = connect(rebuilt)
            verify(clean_snapshot(con) != before, "changing IQR multiplier changes flag output", results)
            altered = {name: con.execute(sql).fetchall() for name, sql in CLEAN_SNAPSHOT_SQL.items()}
            differences_are_only_iqr_flags = True
            for name in CLEAN_SNAPSHOT_SQL:
                for old, new in zip(baseline_contents[name], altered[name]):
                    if old != new:
                        differences_are_only_iqr_flags &= old[:5] == new[:5] and old[6:] == new[6:] and {old[5], new[5]} <= {"ok", "unusual_low", "unusual_high"}
            verify(differences_are_only_iqr_flags, "IQR sensitivity changes only IQR flags, not measurements or other flags", results)
            con.close()
        finally:
            clean_config.IQR_MULTIPLIER = original
        run_clean(rebuilt, quiet=True)
        con = connect(rebuilt)
        verify(clean_snapshot(con) == before, "restoring IQR multiplier restores exact contents", results)
        con.close()

        stamp = "2026-10-10T00:00:00Z"
        synthetic = [(1, 2025, 53, 10.0, stamp, 1), (1, 2026, 42, None, stamp, 0),
                     (1, 2026, 43, 10.0, stamp, 1), (1, 2026, 1, 10.0, stamp, 0),
                     (1, 2026, 2, None, stamp, 1)]
        rows, _ = clean_rows(synthetic, "temperature")
        verify([r[5] for r in rows] == ["invalid_iso_week", "future_placeholder", "future_observation", "reporting_conflict", "reporting_conflict"],
               "calendar, future and contradictory-field branches reject suspect values", results)
        # Repetition across a missing week must not become a consecutive six-week run.
        rows, _ = clean_rows([(1, 2026, w, 10., stamp, 1) for w in (1, 2, 3, 5, 6, 7)], "temperature")
        verify(all(r[5] == "ok" for r in rows), "missing week breaks exact-value runs", results)
        rows, _ = clean_rows([(1, 2026, w, 0., stamp) for w in range(1, 8)], "lice")
        verify(all(r[4] == 0. and r[5] == "ok" for r in rows), "repeated zero lice counts are not labelled sensor faults", results)
        return {"scope": "Cagatay measurement stage only; category stage and validate.py pending",
                "checks": results, "m2_hashes": baseline, "measurement_hashes": before, "clean_result": first}


if __name__ == "__main__":
    print(json.dumps(run_checks(), ensure_ascii=False, indent=2))
