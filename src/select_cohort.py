"""Preparation step: pick a reproducible cohort of actively reporting localities.

A locality is 'active' if it reported at least MIN_WEEKS lice values in every year of
ACTIVE_YEARS. The cohort is a seeded random sample of the active localities and is
written to config/cohort.txt (committed, so the pipeline is deterministic).
"""
import json
import os
import random
import sys

from dotenv import load_dotenv

from api_client import TokenManager, make_request
from ingest import BASE, ROOT, rows_of, save_raw, utc_stamp

ACTIVE_YEARS = (2025, 2022)
MIN_WEEKS = 26
SEED = 42


def weeks_reported(tokens, loc, year):
    response = make_request(f"{BASE}/locality/{loc}/avgfemalelice/{year}", tokens)
    if response is None or response.status_code != 200:
        return None
    try:
        rows = rows_of(response.json()) or []
    except ValueError:
        return None
    return sum(1 for r in rows if isinstance(r, dict) and r.get("value") is not None)


def main():
    load_dotenv()
    cohort_size = int(os.environ.get("COHORT_SIZE", 40))
    tokens = TokenManager()

    response = make_request(f"{BASE}/localities", tokens)
    if response is None or response.status_code != 200:
        print("ERROR: could not fetch the locality list.")
        sys.exit(1)
    save_raw("localities", f"localities_{utc_stamp()}.json", response.content)
    rows = rows_of(json.loads(response.content)) or []
    all_locs = sorted(str(r["localityNo"]) for r in rows
                      if isinstance(r, dict) and "localityNo" in r)
    print(f"Scanning {len(all_locs)} localities (about 30 minutes)...")

    active, unknown = [], 0
    for i, loc in enumerate(all_locs, 1):
        ok = True
        for year in ACTIVE_YEARS:
            weeks = weeks_reported(tokens, loc, year)
            if weeks is None:
                unknown += 1
                ok = False
                break
            if weeks < MIN_WEEKS:
                ok = False
                break
        if ok:
            active.append(loc)
        if i % 100 == 0:
            print(f"  {i}/{len(all_locs)} scanned, {len(active)} active so far", flush=True)

    chosen = sorted(random.Random(SEED).sample(active, min(cohort_size, len(active))))
    config_dir = ROOT / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "cohort.txt").write_text("\n".join(chosen) + "\n", encoding="utf-8")
    print(f"Total: {len(all_locs)} | active (>= {MIN_WEEKS} weeks in {ACTIVE_YEARS}): "
          f"{len(active)} | unknown (request failed): {unknown} | selected: {len(chosen)}")


if __name__ == "__main__":
    main()