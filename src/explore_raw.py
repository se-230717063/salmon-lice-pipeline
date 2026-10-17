"""Explore landed raw files to test key assumptions (M2 section 2.2). Read-only."""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

RAW = Path("data/raw")
PAT = re.compile(r"^(?P<loc>\d+)_(?P<year>\d{4})_(?P<stamp>\d{8}T\d{6}Z)\.json$")


def rows_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "localities", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return None


def load(path):
    return json.loads(path.read_bytes())


for kind in ("lice", "temperature", "treatments"):
    files = sorted((RAW / kind).glob("*.json"))
    by_key = defaultdict(list)           # (loc, year) -> [(stamp, path)]
    for p in files:
        m = PAT.match(p.name)
        if m:
            by_key[(m["loc"], m["year"])].append((m["stamp"], p))
        else:
            print(f"[{kind}] unexpected file name: {p.name}")
    refetched = sum(1 for v in by_key.values() if len(v) > 1)
    print(f"\n=== {kind}: {len(files)} files, {len(by_key)} distinct (locality, year), "
          f"{refetched} fetched more than once ===")

    dup_weeks = nulls = non_numeric = 0
    week_min, week_max = 99, 0
    shapes, key_sets, item_keys = Counter(), Counter(), defaultdict(Counter)
    unreported_temps = Counter()
    ids_seen = defaultdict(set)
    ids_dup = 0
    for (loc, year), versions in by_key.items():
        stamp, path = max(versions)       # latest retrieval only
        payload = load(path)
        shapes[type(payload).__name__] += 1
        rows = rows_of(payload)
        if rows is None:
            print(f"  unexpected payload shape in {path.name}")
            continue
        weeks = Counter(r.get("week") for r in rows if isinstance(r, dict))
        dup_weeks += sum(1 for c in weeks.values() if c > 1)
        for r in rows:
            if not isinstance(r, dict):
                continue
            w = r.get("week")
            if isinstance(w, int):
                week_min, week_max = min(week_min, w), max(week_max, w)
            key_sets[tuple(sorted(r.keys()))] += 1
            if kind == "lice":
                v = r.get("value")
                if v is None:
                    nulls += 1
                elif not isinstance(v, (int, float)):
                    non_numeric += 1
            if kind == "temperature":
                if r.get("hasReported") is False:
                    unreported_temps[repr(r.get("seaTemperature"))] += 1
            if kind == "treatments":
                for cat in ("medicinalTreatments", "nonMedicinalTreatments",
                            "cleanerFishTreatments", "combinationTreatments"):
                    for item in r.get(cat) or []:
                        if isinstance(item, dict):
                            item_keys[cat][tuple(sorted(item.keys()))] += 1
                            if "id" in item:
                                k = (loc, year, w, cat, item["id"])
                                ids_dup += k in ids_seen[cat]
                                ids_seen[cat].add(k)
    print(f"  payload shapes: {dict(shapes)}")
    print(f"  weeks range: {week_min}..{week_max}; duplicate weeks within a file: {dup_weeks}")
    print(f"  row field sets: {dict(key_sets)}")
    if kind == "lice":
        print(f"  null values: {nulls}; non-numeric values: {non_numeric}")
    if kind == "temperature":
        print(f"  seaTemperature where hasReported is false: {dict(unreported_temps)}")
    if kind == "treatments":
        for cat, c in item_keys.items():
            print(f"  {cat} item field sets: {dict(c)}")
        print(f"  duplicate item ids per (locality, year, week, category): {ids_dup}")

# localities: does every cohort locality exist, and do names change between files?
loc_files = sorted((RAW / "localities").glob("*.json"))
names = defaultdict(set)
for p in loc_files:
    for r in rows_of(load(p)) or []:
        if isinstance(r, dict) and "localityNo" in r:
            names[r["localityNo"]].add((r.get("name"), r.get("municipalityNo")))
print(f"\n=== localities: {len(loc_files)} files, {len(names)} distinct localityNo ===")
changed = {k: v for k, v in names.items() if len(v) > 1}
print(f"  localities whose name/municipality differs between files: {len(changed)}")
cohort = Path("config/cohort.txt")
if cohort.exists():
    missing = [c for c in cohort.read_text().split() if int(c) not in names]
    print(f"  cohort localities missing from the locality list (orphans): {len(missing)}")