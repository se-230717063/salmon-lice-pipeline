"""M3 orchestrator: atomic measurement, category and mapping rebuild.

Reads only M2 tables. Rebuilds clean tables in one explicit transaction, including
transactional DDL. No executescript(): sqlite3 would commit before that call.
"""
import argparse
import importlib
from pathlib import Path
import sqlite3

from db import DB_PATH, ROOT, connect, snapshot
from clean_measurements import clean_rows

SCHEMA = ROOT / "sql/clean_schema.sql"
SELECT_LICE = "SELECT locality_key, year, week, avg_adult_female_lice, retrieved_at FROM lice_weekly ORDER BY locality_key, year, week"
SELECT_TEMP = "SELECT locality_key, year, week, sea_temperature, retrieved_at, has_reported FROM sea_temperature_weekly ORDER BY locality_key, year, week"
INSERT_LICE = "INSERT INTO lice_weekly_clean (locality_key, year, week, avg_adult_female_lice_raw, avg_adult_female_lice, avg_adult_female_lice_flag, retrieved_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
INSERT_TEMP = "INSERT INTO sea_temperature_weekly_clean (locality_key, year, week, sea_temperature_raw, sea_temperature, sea_temperature_flag, has_reported, retrieved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
CLEAN_SNAPSHOT_SQL = {
    "lice_weekly_clean": "SELECT * FROM lice_weekly_clean ORDER BY locality_key, year, week",
    "sea_temperature_weekly_clean": "SELECT * FROM sea_temperature_weekly_clean ORDER BY locality_key, year, week",
    "municipality_clean": "SELECT * FROM municipality_clean ORDER BY municipality_key",
    "locality_clean": "SELECT * FROM locality_clean ORDER BY locality_key",
    "treatment_weekly_clean": "SELECT * FROM treatment_weekly_clean ORDER BY locality_key, year, week",
    "treatment_event_clean": "SELECT * FROM treatment_event_clean ORDER BY locality_key, year, week, category, event_seq",
    "municipality_name_mapping": "SELECT * FROM municipality_name_mapping ORDER BY municipality_no, raw_name",
    "locality_name_mapping": "SELECT * FROM locality_name_mapping ORDER BY locality_no, raw_name",
    "treatment_value_mapping": "SELECT * FROM treatment_value_mapping ORDER BY field, raw_value",
    "locality_identity_mapping": "SELECT * FROM locality_identity_mapping ORDER BY source_locality_no",
}


class SimulatedCleanFailure(RuntimeError):
    """Intentional failure used only by safety proofs on disposable copies."""


def schema_statements():
    pending = ""
    for line in SCHEMA.read_text(encoding="utf-8").splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ""
    if pending.strip() and any(line.strip() and not line.lstrip().startswith("--") for line in pending.splitlines()):
        raise ValueError("Incomplete clean schema SQL")


def category_builder():
    try:
        module = importlib.import_module("clean_categories")
    except ModuleNotFoundError as exc:
        if exc.name != "clean_categories":
            raise
        return None
    return module.build_categories


def run_clean(db_path=DB_PATH, *, fail_after_rows=None, quiet=False, require_categories=False):
    if not Path(db_path).is_file():
        raise FileNotFoundError("M2 database not found; run python src/load.py first")
    builder = category_builder()
    if builder is None:
        raise RuntimeError("Category stage missing: Egemen must implement clean_categories.build_categories")
    con = connect(db_path)
    count = 0

    def tick():
        nonlocal count
        count += 1
        if fail_after_rows is not None and count >= fail_after_rows:
            raise SimulatedCleanFailure("Intentional failure during cleaned-layer writes")
    try:
        # Read and write under one transaction for a consistent M2 snapshot.
        con.execute("BEGIN IMMEDIATE")
        with con:
            before = snapshot(con)
            lice, lice_flags = clean_rows(con.execute(SELECT_LICE).fetchall(), "lice")
            temperature, temp_flags = clean_rows(con.execute(SELECT_TEMP).fetchall(), "temperature")
            # Transactional migration of the clean-only event flag vocabulary.
            # Source treatment_event is never dropped or modified.
            con.execute("DROP TABLE IF EXISTS treatment_event_clean")
            for statement in schema_statements():
                con.execute(statement)
            con.execute("DELETE FROM lice_weekly_clean")
            con.execute("DELETE FROM sea_temperature_weekly_clean")
            for sql, rows in ((INSERT_LICE, lice), (INSERT_TEMP, temperature)):
                for row in rows:
                    con.execute(sql, row)
                    tick()
            categories = builder(con, ROOT / "data/mappings", tick=tick)
            if snapshot(con) != before:
                raise RuntimeError("M2 contents changed; rolling back the entire clean build")
            if con.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Foreign key violation; rolling back the entire clean build")
        result = {"measurements": {
            "lice_weekly_clean": {"rows": len(lice), "flags": lice_flags},
            "sea_temperature_weekly_clean": {"rows": len(temperature), "flags": temp_flags}},
            "m2_unchanged": True, "categories": categories,
            "category_stage": "complete" if builder else "pending"}
        if not quiet:
            for table, info in result["measurements"].items():
                print(f"{table}: {info['rows']} rows (same as M2)")
                for flag, number in info["flags"].items():
                    print(f"  {flag}: {number}")
            print("M2 contents: UNCHANGED; foreign_key_check: OK")
            print("categories:", categories if builder else "PENDING - clean_categories.py not implemented")
            print("STATUS:", "BUILD COMPLETE - run validate.py" if builder else "MEASUREMENTS COMPLETE; M3 INCOMPLETE (category stage and validation pending)")
        return result
    except Exception:
        if not quiet:
            print("STATUS: FAILED - cleaned-layer transaction rolled back")
        raise
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--require-categories", action="store_true", help="Final integration guard; fails until Egemen's module exists")
    args = parser.parse_args()
    try:
        run_clean(args.db, require_categories=args.require_categories)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
