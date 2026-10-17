"""Shared database helpers. Every script gets its connection from connect()."""
import hashlib
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "salmon_lice.db"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"
MIN_SQLITE = (3, 37, 0)  # STRICT tables need SQLite 3.37+

# Fixed SQL text per table: no string building anywhere, so no value can ever reach SQL by formatting.
COUNT_SQL = {
    "municipality": "SELECT COUNT(*) FROM municipality",
    "locality": "SELECT COUNT(*) FROM locality",
    "lice_weekly": "SELECT COUNT(*) FROM lice_weekly",
    "sea_temperature_weekly": "SELECT COUNT(*) FROM sea_temperature_weekly",
    "treatment_weekly": "SELECT COUNT(*) FROM treatment_weekly",
    "treatment_event": "SELECT COUNT(*) FROM treatment_event",
    "quarantine": "SELECT COUNT(*) FROM quarantine",
}
SNAPSHOT_SQL = {
    "municipality": "SELECT * FROM municipality ORDER BY municipality_key",
    "locality": "SELECT * FROM locality ORDER BY locality_key",
    "lice_weekly": "SELECT * FROM lice_weekly ORDER BY locality_key, year, week",
    "sea_temperature_weekly": "SELECT * FROM sea_temperature_weekly ORDER BY locality_key, year, week",
    "treatment_weekly": "SELECT * FROM treatment_weekly ORDER BY locality_key, year, week",
    "treatment_event": "SELECT * FROM treatment_event ORDER BY locality_key, year, week, category, event_seq",
    "quarantine": "SELECT * FROM quarantine ORDER BY quarantine_id",
}


def connect(db_path=DB_PATH):
    """Open the database and turn on foreign-key enforcement immediately."""
    if sqlite3.sqlite_version_info < MIN_SQLITE:
        raise RuntimeError(f"SQLite {sqlite3.sqlite_version} is too old; STRICT needs 3.37+")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_schema(con):
    """Create all tables. Safe to run more than once (CREATE TABLE IF NOT EXISTS)."""
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def table_counts(con):
    return {table: con.execute(sql).fetchone()[0] for table, sql in COUNT_SQL.items()}


def snapshot(con):
    """{table: (row count, hash of every row)}: used to prove that two loads give identical state."""
    result = {}
    for table, sql in SNAPSHOT_SQL.items():
        digest, count = hashlib.sha256(), 0
        for row in con.execute(sql):
            digest.update(repr(row).encode("utf-8"))
            count += 1
        result[table] = (count, digest.hexdigest())
    return result