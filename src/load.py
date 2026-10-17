"""Load the landed raw files (data/raw/) into the SQLite database.

Reads local files only and never calls the API. Properties:
  idempotent     running it again changes nothing (guarded upserts, latest retrieval wins)
  atomic         one transaction: if anything fails, nothing from this run is written
  parameterised  every value reaches SQL through a placeholder
Only what loading requires is transformed (types, timestamps, keys). Cleaning is M3.
"""
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime

from db import DB_PATH, ROOT, connect, init_schema, table_counts

RAW_DIR = ROOT / "data" / "raw"
LOCALITY_FILE = re.compile(r"^localities_(?P<stamp>\d{8}T\d{6}Z)\.json$")
SERIES_FILE = re.compile(r"^(?P<loc>\d+)_(?P<year>\d{4})_(?P<stamp>\d{8}T\d{6}Z)\.json$")
SERIES_FOLDERS = ("lice", "temperature", "treatments")
CATEGORIES = (
    ("medicinal", "medicinalTreatments"),
    ("non_medicinal", "nonMedicinalTreatments"),
    ("cleaner_fish", "cleanerFishTreatments"),
    ("combination", "combinationTreatments"),
)

# ---- SQL: constants with placeholders only. A row is only replaced by a newer retrieval. ----
UPSERT_MUNICIPALITY = (
    "INSERT INTO municipality (municipality_no, name, retrieved_at) VALUES (?, ?, ?) "
    "ON CONFLICT (municipality_no) DO UPDATE SET name = excluded.name, "
    "retrieved_at = excluded.retrieved_at "
    "WHERE excluded.retrieved_at > municipality.retrieved_at"
)
UPSERT_LOCALITY = (
    "INSERT INTO locality (locality_no, name, municipality_key, registry_version, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT (locality_no) DO UPDATE SET name = excluded.name, "
    "municipality_key = excluded.municipality_key, registry_version = excluded.registry_version, "
    "retrieved_at = excluded.retrieved_at "
    "WHERE excluded.retrieved_at > locality.retrieved_at"
)
UPSERT_LICE = (
    "INSERT INTO lice_weekly (locality_key, year, week, avg_adult_female_lice, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT (locality_key, year, week) DO UPDATE SET "
    "avg_adult_female_lice = excluded.avg_adult_female_lice, retrieved_at = excluded.retrieved_at "
    "WHERE excluded.retrieved_at > lice_weekly.retrieved_at"
)
UPSERT_TEMPERATURE = (
    "INSERT INTO sea_temperature_weekly "
    "(locality_key, year, week, sea_temperature, has_reported, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (locality_key, year, week) DO UPDATE SET "
    "sea_temperature = excluded.sea_temperature, has_reported = excluded.has_reported, "
    "retrieved_at = excluded.retrieved_at "
    "WHERE excluded.retrieved_at > sea_temperature_weekly.retrieved_at"
)
SELECT_TREATMENT_STAMP = (
    "SELECT retrieved_at FROM treatment_weekly WHERE locality_key = ? AND year = ? AND week = ?"
)
UPSERT_TREATMENT = (
    "INSERT INTO treatment_weekly (locality_key, year, week, mechanical_removal, "
    "mechanical_removal_entire_locality, record_version, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (locality_key, year, week) DO UPDATE SET "
    "mechanical_removal = excluded.mechanical_removal, "
    "mechanical_removal_entire_locality = excluded.mechanical_removal_entire_locality, "
    "record_version = excluded.record_version, retrieved_at = excluded.retrieved_at "
    "WHERE excluded.retrieved_at > treatment_weekly.retrieved_at"
)
DELETE_EVENTS = (
    "DELETE FROM treatment_event WHERE locality_key = ? AND year = ? AND week = ?"
)
UPSERT_EVENT = (
    "INSERT INTO treatment_event (locality_key, year, week, category, event_seq, "
    "source_event_id, treatment_type, substance_name, substance_id, number_of_cages, "
    "entire_locality, done_before_lice_count, lice_report_id, details_json, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (locality_key, year, week, category, event_seq) DO UPDATE SET "
    "source_event_id = excluded.source_event_id, treatment_type = excluded.treatment_type, "
    "substance_name = excluded.substance_name, substance_id = excluded.substance_id, "
    "number_of_cages = excluded.number_of_cages, entire_locality = excluded.entire_locality, "
    "done_before_lice_count = excluded.done_before_lice_count, "
    "lice_report_id = excluded.lice_report_id, details_json = excluded.details_json, "
    "retrieved_at = excluded.retrieved_at"
)
INSERT_QUARANTINE = (
    "INSERT INTO quarantine (source_kind, source_file, reason, raw_payload, retrieved_at) "
    "VALUES (?, ?, ?, ?, ?) ON CONFLICT (source_file, reason, raw_payload) DO NOTHING"
)
SELECT_LOCALITY_NOS = "SELECT locality_no FROM locality"
SELECT_LOCALITY_KEYS = "SELECT locality_no, locality_key FROM locality"
SELECT_MUNICIPALITY_KEYS = "SELECT municipality_no, municipality_key FROM municipality"
FK_CHECK = "PRAGMA foreign_key_check"


class SimulatedFailure(RuntimeError):
    """Raised on purpose by checks.py to prove that a failed load leaves nothing behind."""


# ---------------------------------------------------------------- helpers
def iso_stamp(stamp):
    """20261010T180954Z -> 2026-10-10T18:09:54Z (ISO 8601 UTC)."""
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")


def rows_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "localities", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return None


def read_json(path):
    try:
        return json.loads(path.read_bytes()), None
    except (OSError, ValueError) as exc:  # ValueError covers bad JSON and bad UTF-8
        return None, type(exc).__name__


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def valid_week(value):
    return is_int(value) and 1 <= value <= 53


def clean_real(value, label, cleaned):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    cleaned[label] += 1
    return None


def clean_int(value, label, cleaned):
    if value is None:
        return None
    if is_int(value):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    cleaned[label] += 1
    return None


def clean_flag(value, label, cleaned):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    cleaned[label] += 1
    return None


def clean_text(value, label, cleaned):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    cleaned[label] += 1
    return None


def add_quarantine(quarantine, kind, file_name, reason, payload, stamp):
    quarantine.append(
        (kind, file_name, reason, json.dumps(payload, sort_keys=True, ensure_ascii=False), stamp)
    )


# ---------------------------------------------------------------- 1. read raw files
def collect(raw_dir):
    """Read every raw file. Per natural key keep the row from the most recently retrieved file."""
    best = {"localities": {}, "lice": {}, "temperature": {}, "treatments": {}}
    seen, stats, stamps, quarantine = Counter(), Counter(), [], []

    def keep(kind, key, candidate, row):
        seen[kind] += 1
        current = best[kind].get(key)
        if current is None or candidate > current[0]:  # (retrieved_at, file name)
            best[kind][key] = (candidate, row)

    def open_file(path, kind, stamp):
        payload, error = read_json(path)
        if error:
            stats["files skipped (unreadable)"] += 1
            add_quarantine(quarantine, kind, path.name, f"unreadable file: {error}",
                           {"file": path.name}, stamp)
            return None
        rows = rows_of(payload)
        if rows is None:
            stats["files skipped (unexpected shape)"] += 1
            add_quarantine(quarantine, kind, path.name, "unexpected payload shape",
                           {"file": path.name}, stamp)
            return None
        stats["files read"] += 1
        stamps.append(stamp)
        return rows

    for path in sorted((raw_dir / "localities").glob("*.json")):
        match = LOCALITY_FILE.match(path.name)
        if not match:
            stats["files skipped (unrecognised name)"] += 1
            continue
        stamp = iso_stamp(match["stamp"])
        rows = open_file(path, "localities", stamp)
        for row in rows or []:
            number = row.get("localityNo") if isinstance(row, dict) else None
            if not is_int(number):
                add_quarantine(quarantine, "localities", path.name,
                               "missing or invalid localityNo", row, stamp)
                continue
            keep("localities", number, (stamp, path.name), row)

    for folder in SERIES_FOLDERS:
        for path in sorted((raw_dir / folder).glob("*.json")):
            match = SERIES_FILE.match(path.name)
            if not match or not 2000 <= int(match["year"]) <= 2100:
                stats["files skipped (unrecognised name)"] += 1
                continue
            stamp = iso_stamp(match["stamp"])
            number, year = int(match["loc"]), int(match["year"])
            rows = open_file(path, folder, stamp)
            for row in rows or []:
                week = row.get("week") if isinstance(row, dict) else None
                if not valid_week(week):
                    add_quarantine(quarantine, folder, path.name,
                                   "missing or invalid week", row, stamp)
                    continue
                keep(folder, (number, year, week), (stamp, path.name), row)

    return best, quarantine, stats, seen, stamps


# ---------------------------------------------------------------- 2. validate and type
def event_values(category, seq, item, cleaned):
    fields = item if isinstance(item, dict) else {}
    return (
        category,
        seq,
        clean_int(fields.get("id"), "treatment item id not an integer -> NULL", cleaned),
        clean_text(fields.get("type"), "treatment item type wrong type -> NULL", cleaned),
        clean_text(fields.get("name"), "treatment item name wrong type -> NULL", cleaned),
        clean_text(fields.get("substanceId"), "treatment item substanceId wrong type -> NULL", cleaned),
        clean_int(fields.get("numberOfCages"), "treatment item numberOfCages not an integer -> NULL", cleaned),
        clean_flag(fields.get("entireLocality"), "treatment item entireLocality not boolean -> NULL", cleaned),
        clean_flag(fields.get("doneBeforeLiceCount"), "treatment item doneBeforeLiceCount not boolean -> NULL", cleaned),
        clean_text(fields.get("liceReportId"), "treatment item liceReportId wrong type -> NULL", cleaned),
        json.dumps(item, sort_keys=True, ensure_ascii=False),
    )


def prepare(best, known, cleaned, quarantine):
    data = {"municipalities": {}, "localities": [], "lice": [], "temperature": [], "treatments": []}

    for number, ((stamp, _), row) in sorted(best["localities"].items()):
        mun_no = clean_text(row.get("municipalityNo"), "locality.municipalityNo wrong type -> NULL", cleaned)
        mun_name = clean_text(row.get("municipality"), "locality.municipality wrong type -> NULL", cleaned)
        if mun_no is not None:
            current = data["municipalities"].get(mun_no)
            if current is None or stamp > current[1]:
                data["municipalities"][mun_no] = (mun_name, stamp)
        data["localities"].append((
            number,
            clean_text(row.get("name"), "locality.name wrong type -> NULL", cleaned),
            mun_no,
            clean_text(row.get("aquaCultureRegistryVersion"),
                       "locality.aquaCultureRegistryVersion wrong type -> NULL", cleaned),
            stamp,
        ))

    for kind in SERIES_FOLDERS:
        for (number, year, week), ((stamp, file_name), row) in sorted(best[kind].items()):
            if number not in known:
                add_quarantine(quarantine, kind, file_name, f"unknown locality {number}", row, stamp)
                continue
            if kind == "lice":
                value = clean_real(row.get("value"), "lice.value non-numeric -> NULL", cleaned)
                data["lice"].append((number, year, week, value, stamp))
            elif kind == "temperature":
                flag = row.get("hasReported")
                if not isinstance(flag, bool):
                    add_quarantine(quarantine, kind, file_name, "invalid hasReported", row, stamp)
                    continue
                temperature = clean_real(row.get("seaTemperature"),
                                         "temperature.seaTemperature non-numeric -> NULL", cleaned)
                data["temperature"].append((number, year, week, temperature, int(flag), stamp))
            else:
                events, bad_list = [], False
                for category, key in CATEGORIES:
                    items = row.get(key)
                    if items is None:
                        continue
                    if not isinstance(items, list):
                        bad_list = True
                        break
                    for seq, item in enumerate(items, start=1):
                        events.append(event_values(category, seq, item, cleaned))
                if bad_list:
                    add_quarantine(quarantine, kind, file_name,
                                   "treatment list is not a list", row, stamp)
                    continue
                parent = (
                    number, year, week,
                    clean_flag(row.get("mechanicalRemoval"),
                               "treatment.mechanicalRemoval not boolean -> NULL", cleaned),
                    clean_flag(row.get("mechanicalRemovalEntireLocality"),
                               "treatment.mechanicalRemovalEntireLocality not boolean -> NULL", cleaned),
                    clean_int(row.get("version"), "treatment.version not an integer -> NULL", cleaned),
                    stamp,
                )
                data["treatments"].append((parent, events))
    return data


# ---------------------------------------------------------------- 3. write (inside one transaction)
def write_all(con, data, quarantine, tick):
    for number, (name, stamp) in sorted(data["municipalities"].items()):
        con.execute(UPSERT_MUNICIPALITY, (number, name, stamp))
        tick()
    municipality_key = dict(con.execute(SELECT_MUNICIPALITY_KEYS).fetchall())

    for number, name, mun_no, registry, stamp in data["localities"]:
        con.execute(UPSERT_LOCALITY, (number, name, municipality_key.get(mun_no), registry, stamp))
        tick()
    locality_key = dict(con.execute(SELECT_LOCALITY_KEYS).fetchall())

    for number, year, week, value, stamp in data["lice"]:
        con.execute(UPSERT_LICE, (locality_key[number], year, week, value, stamp))
        tick()

    for number, year, week, temperature, flag, stamp in data["temperature"]:
        con.execute(UPSERT_TEMPERATURE, (locality_key[number], year, week, temperature, flag, stamp))
        tick()

    for parent, events in data["treatments"]:
        number, year, week, removal, removal_all, version, stamp = parent
        key = locality_key[number]
        existing = con.execute(SELECT_TREATMENT_STAMP, (key, year, week)).fetchone()
        if existing is not None and not stamp > existing[0]:
            continue  # the database already holds this retrieval or a newer one
        con.execute(UPSERT_TREATMENT, (key, year, week, removal, removal_all, version, stamp))
        tick()
        con.execute(DELETE_EVENTS, (key, year, week))  # replace the whole list of this week
        for event in events:
            con.execute(UPSERT_EVENT, (key, year, week) + event + (stamp,))
            tick()

    for record in quarantine:
        con.execute(INSERT_QUARANTINE, record)
        tick()


# ---------------------------------------------------------------- 4. orchestration and summary
def run_load(db_path=DB_PATH, raw_dir=RAW_DIR, fail_after_rows=None, quiet=False):
    con = connect(db_path)
    try:
        init_schema(con)  # before the transaction: executescript would commit an open one
        best, quarantine, stats, seen, stamps = collect(raw_dir)
        before = table_counts(con)
        localities_before = {row[0] for row in con.execute(SELECT_LOCALITY_NOS)}
        known = localities_before | set(best["localities"])
        cleaned = Counter()
        data = prepare(best, known, cleaned, quarantine)

        counter = {"rows": 0}

        def tick():
            counter["rows"] += 1
            if fail_after_rows is not None and counter["rows"] > fail_after_rows:
                raise SimulatedFailure(f"simulated failure after {fail_after_rows} rows")

        with con:  # one transaction: commit on success, roll back on any exception
            write_all(con, data, quarantine, tick)

        after = table_counts(con)
        localities_after = {row[0] for row in con.execute(SELECT_LOCALITY_NOS)}
        violations = con.execute(FK_CHECK).fetchall()
        result = {
            "ok": not violations,
            "files_read": stats["files read"],
            "before": before,
            "after": after,
        }
        if not quiet:
            print_summary(stats, seen, best, stamps, before, after, cleaned,
                          sorted(localities_after - localities_before), violations)
        return result
    except Exception as exc:
        if not quiet:
            print(f"STATUS: FAILED - nothing from this run was written ({type(exc).__name__}: {exc})")
        raise
    finally:
        con.close()


def print_summary(stats, seen, best, stamps, before, after, cleaned, new_localities, violations):
    span = f" ({min(stamps)[:10]} .. {max(stamps)[:10]})" if stamps else ""
    print(f"files read: {stats['files read']} raw files{span}")
    for label, count in sorted(stats.items()):
        if label != "files read":
            print(f"{label}: {count}")
    collapsed = sum(seen.values()) - sum(len(rows) for rows in best.values())
    print(f"duplicate rows collapsed by key (latest retrieval wins): {collapsed}")
    for table, total in after.items():
        print(f"{table}: {total:,} in database (+{total - before[table]:,} this run)")
    print(f"values cleaned: {sum(cleaned.values())}")
    for label, count in sorted(cleaned.items()):
        print(f"  {label}: {count}")
    print(f"new localities this run: {len(new_localities)} {new_localities[:10]}")
    print(f"quarantined: {after['quarantine']:,} records in database "
          f"(+{after['quarantine'] - before['quarantine']:,} this run)")
    print("foreign_key_check:", "OK" if not violations else f"{len(violations)} VIOLATIONS")
    print("STATUS:", "COMPLETE" if not violations else "COMPLETE WITH FOREIGN KEY VIOLATIONS")


def main():
    try:
        result = run_load()
    except Exception:
        sys.exit(1)
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()