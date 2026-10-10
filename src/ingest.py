"""M1 ingestion: land raw BarentsWatch Fish Health responses, untouched, in data/raw/."""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from api_client import STATUS_COUNTS, TokenManager, make_request

BASE = "https://www.barentswatch.no/bwapi/v1/geodata/fishhealth"
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
COHORT_FILE = ROOT / "config" / "cohort.txt"
ENDPOINTS = {
    "lice": "avgfemalelice",
    "temperature": "seatemperature",
    "treatments": "liceTreatments",
}


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rows_of(payload):
    """Return the list of rows in a response payload, or None if the shape is unexpected."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "localities", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return None


def classify(content):
    """Inspect a COPY of the response: 'ok', 'empty' or 'unexpected'. Raw bytes stay untouched."""
    try:
        rows = rows_of(json.loads(content))
    except ValueError:
        return "unexpected"
    if rows is None:
        return "unexpected"
    return "empty" if len(rows) == 0 else "ok"


def save_raw(folder, name, content):
    """Write bytes exactly as received. 'xb' refuses to overwrite an existing file."""
    path = RAW_DIR / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as fh:
        fh.write(content)
    return path


def fetch_and_store(tokens, stat, folder, url, stem):
    stat["requests"] += 1
    response = make_request(url, tokens)
    if response is None:
        stat["failed"] += 1
        return
    if response.status_code != 200:
        stat["http_error"] += 1
        print(f"WARNING: HTTP {response.status_code} for {url}; nothing saved.")
        return
    kind = classify(response.content)
    try:
        save_raw(folder, f"{stem}_{utc_stamp()}.json", response.content)
    except FileExistsError:
        stat["skipped_exists"] += 1
        return
    stat["saved"] += 1
    if kind != "ok":
        stat[kind] += 1


def print_summary(stats):
    print("\n=== RUN SUMMARY ===")
    print(f"{'source':<13}{'requests':>9}{'saved':>7}{'empty':>7}"
          f"{'unexpected':>11}{'http_err':>9}{'failed':>8}")
    healthy = True
    for name, s in stats.items():
        print(f"{name:<13}{s['requests']:>9}{s['saved']:>7}{s['empty']:>7}"
              f"{s['unexpected']:>11}{s['http_error']:>9}{s['failed']:>8}")
        if s["failed"] or s["unexpected"] or s["http_error"]:
            healthy = False
    print("HTTP status counts:", dict(STATUS_COUNTS))
    print("RESULT:", "healthy" if healthy else "PROBLEMS FOUND - check warnings above")
    return healthy


def main():
    load_dotenv()
    start_year = int(os.environ.get("START_YEAR", 2022))
    end_year = int(os.environ.get("END_YEAR", datetime.now(timezone.utc).year))

    if not COHORT_FILE.exists():
        print(f"ERROR: {COHORT_FILE} not found. Run: python src/select_cohort.py")
        sys.exit(1)
    cohort = [ln.strip() for ln in COHORT_FILE.read_text(encoding="utf-8").splitlines()
              if ln.strip()]
    print(f"Ingestion starting: {len(cohort)} localities, years {start_year}-{end_year}")

    tokens = TokenManager()
    stats = {name: Counter() for name in ("localities", *ENDPOINTS)}

    fetch_and_store(tokens, stats["localities"], "localities",
                    f"{BASE}/localities", "localities")

    for i, loc in enumerate(cohort, 1):
        for year in range(start_year, end_year + 1):
            for folder, endpoint in ENDPOINTS.items():
                fetch_and_store(tokens, stats[folder], folder,
                                f"{BASE}/locality/{loc}/{endpoint}/{year}",
                                f"{loc}_{year}")
        if i % 10 == 0:
            print(f"  {i}/{len(cohort)} localities done", flush=True)

    sys.exit(0 if print_summary(stats) else 1)


if __name__ == "__main__":
    main()