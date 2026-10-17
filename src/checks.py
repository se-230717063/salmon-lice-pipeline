"""Integrity and constraint checks against a temporary copy of the database.

M2 Section 4: Prove It, Don't Claim It.
Runs against a temporary copy of the database (never the real one).
Reports PASS or FAIL for all six required properties:
  1. Duplicate natural key: Inserting an entity with an existing source ID is rejected.
  2. Orphan event: Inserting an event referencing a non-existent entity is rejected.
  3. NULL key: Inserting an event with a NULL in its key is rejected.
  4. Wrong type: Inserting text into a numeric column is rejected (STRICT mode).
  5. Idempotence: Loading twice gives identical row counts in every table.
  6. Atomicity: A load that fails partway leaves every table's row count unchanged.
"""
import pathlib
import shutil
import sqlite3
import sys
import tempfile

from db import DB_PATH, connect, init_schema, snapshot, table_counts
from load import SimulatedFailure, run_load

INSERT_LOCALITY = (
    "INSERT INTO locality (locality_no, name, municipality_key, registry_version, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?)"
)
INSERT_LICE = (
    "INSERT INTO lice_weekly (locality_key, year, week, avg_adult_female_lice, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?)"
)


def get_table_counts(con):
    # Uses fixed SQL statements from db.COUNT_SQL (zero string formatting in SQL).
    return table_counts(con)


def check_duplicate_natural_key(con):
    """Inserting an entity with an existing source ID is rejected."""
    existing_no = con.execute("SELECT locality_no FROM locality LIMIT 1").fetchone()[0]
    try:
        con.execute(
            INSERT_LOCALITY,
            (existing_no, "Duplicate Test", None, None, "2026-10-17T12:00:00Z"),
        )
        return False, "Duplicate natural key was accepted without error"
    except sqlite3.IntegrityError:
        return True, "PASS"


def check_orphan_event(con):
    """Inserting an event that references a non-existent entity is rejected."""
    # Find a non-existent locality_key
    max_key = con.execute("SELECT COALESCE(MAX(locality_key), 0) + 9999 FROM locality").fetchone()[0]
    try:
        con.execute(
            INSERT_LICE,
            (max_key, 2024, 1, 0.15, "2026-10-17T12:00:00Z"),
        )
        return False, "Orphan event was accepted without error"
    except sqlite3.IntegrityError:
        return True, "PASS"


def check_null_key(con):
    """Inserting an event with a NULL in its key is rejected."""
    try:
        con.execute(
            INSERT_LICE,
            (None, 2024, 1, 0.15, "2026-10-17T12:00:00Z"),
        )
        return False, "Event with NULL key was accepted without error"
    except sqlite3.IntegrityError:
        return True, "PASS"


def check_wrong_type(con):
    """Inserting text into a numeric column is rejected (STRICT enforcement)."""
    valid_key = con.execute("SELECT locality_key FROM locality LIMIT 1").fetchone()[0]
    try:
        # avg_adult_female_lice is REAL in a STRICT table; text cannot be stored
        con.execute(
            INSERT_LICE,
            (valid_key, 2024, 99, "not-a-number", "2026-10-17T12:00:00Z"),
        )
        return False, "Text in REAL column was accepted without error"
    except (sqlite3.IntegrityError, sqlite3.OperationalError):
        return True, "PASS"


def check_idempotence(db_path):
    """Loading twice gives identical row counts and row contents in every table."""
    con = connect(db_path)
    before_snap = snapshot(con)
    con.close()

    # Second load
    run_load(db_path=db_path, quiet=True)

    con = connect(db_path)
    after_snap = snapshot(con)
    con.close()

    if before_snap == after_snap:
        return True, "PASS"
    return False, f"FAIL: state changed after re-load"


def check_atomicity(tmp_dir):
    """A load that fails partway leaves every table's row count unchanged."""
    target = pathlib.Path(tmp_dir) / "atomicity.db"
    con = connect(target)
    init_schema(con)
    before = get_table_counts(con)
    con.close()

    failed = False
    try:
        run_load(db_path=target, fail_after_rows=1000, quiet=True)
    except SimulatedFailure:
        failed = True
    except Exception as exc:
        return False, f"Unexpected exception: {exc}"

    if not failed:
        return False, "Loader did not raise SimulatedFailure"

    con = connect(target)
    after = get_table_counts(con)
    con.close()
    return (True, "PASS") if before == after else (False, f"FAIL: row counts changed ({before} -> {after})")


def run_all_checks():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run python src/load.py first.")
        sys.exit(1)

    print(f"Running integrity checks against a temporary copy of {DB_PATH.name}...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_db = pathlib.Path(tmp_dir) / "check_copy.db"
        shutil.copyfile(DB_PATH, tmp_db)

        con = connect(tmp_db)

        results = []
        # Constraint checks on open connection
        for name, fn in [
            ("Duplicate natural key", lambda: check_duplicate_natural_key(con)),
            ("Orphan event", lambda: check_orphan_event(con)),
            ("NULL key", lambda: check_null_key(con)),
            ("Wrong type", lambda: check_wrong_type(con)),
        ]:
            ok, msg = fn()
            results.append((name, ok, msg))

        con.close()

        # Idempotence check (runs loader on copy)
        ok, msg = check_idempotence(tmp_db)
        results.append(("Idempotence", ok, msg))

        # Atomicity check (runs loader with simulated failure on fresh empty db)
        ok, msg = check_atomicity(tmp_dir)
        results.append(("Atomicity", ok, msg))

    print("\n=== INTEGRITY CHECKS SUMMARY ===")
    all_passed = True
    for name, ok, msg in results:
        status = "PASS" if ok else f"FAIL ({msg})"
        if not ok:
            all_passed = False
        print(f"{name:<25}: {status}")

    print("================================")
    print("ALL CHECKS PASSED!" if all_passed else "SOME CHECKS FAILED.")
    return all_passed


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
