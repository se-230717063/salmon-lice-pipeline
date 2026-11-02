"""Pure measurement rules; no database writes, API access, imputation or identity merging."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import math

import clean_config as config


def quantile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def initial_rule(row, kind):
    """row = (locality_key, year, week, raw_value, retrieved_at[, has_reported])."""
    _, year, week, raw, retrieved_at, *extra = row
    try:
        day = date.fromisocalendar(year, week, 1)
    except ValueError:
        return None, "invalid_iso_week", None
    retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00")).date()
    if day > retrieved:
        flag = "future_placeholder" if kind == "temperature" and raw is None and extra[0] == 0 else "future_observation"
        return None, flag, day
    if kind == "temperature":
        reported = extra[0]
        if (reported == 0 and raw is not None) or (reported == 1 and raw is None):
            return None, "reporting_conflict", day
        if reported == 0:
            return None, "missing_not_reported", day
    if raw is None:
        return None, "missing_unknown", day
    if not math.isfinite(raw):
        return None, "invalid_range", day
    if kind == "lice" and raw < 0:
        return None, "invalid_negative", day
    if kind == "temperature" and not config.TEMP_MIN_C <= raw <= config.TEMP_MAX_C:
        return None, "invalid_range", day
    return raw, "ok", day


def clean_rows(rows, kind):
    """Return inserts in input order, plus mutually exclusive flag counts.

    Statistics use valid observations within each existing M2 locality identity.
    Egemen must revisit grouping if his investigation establishes an identity split.
    """
    prepared = []
    grouped = defaultdict(list)
    for row in rows:
        value, flag, day = initial_rule(row, kind)
        item = {"row": row, "value": value, "flag": flag, "day": day}
        prepared.append(item)
        grouped[row[0]].append(item)
    for items in grouped.values():
        eligible = [item["value"] for item in items if item["flag"] == "ok"]
        fences = None
        if len(eligible) >= config.MIN_IQR_OBSERVATIONS:
            q1, q3 = quantile(eligible, .25), quantile(eligible, .75)
            if q3 > q1:  # Degenerate IQR is reported, not turned into a zero-width filter.
                width = config.IQR_MULTIPLIER * (q3 - q1)
                fences = (q1 - width, q3 + width)
        if kind == "temperature":
            run = []

            def flag_run():
                if len(run) >= config.STUCK_RUN_WEEKS:
                    for member in run:
                        member["flag"] = "suspect_stuck"

            for item in items:
                if item["flag"] != "ok":
                    flag_run()
                    run = []
                elif run and item["day"] - run[-1]["day"] == timedelta(days=7) and item["value"] == run[-1]["value"]:
                    run.append(item)
                else:
                    flag_run()
                    run = [item]
            flag_run()
            for previous, current, following in zip(items, items[1:], items[2:]):
                if current["flag"] != "ok" or previous["value"] is None or following["value"] is None:
                    continue
                if current["day"] - previous["day"] != timedelta(days=7) or following["day"] - current["day"] != timedelta(days=7):
                    continue
                a, b, c = previous["value"], current["value"], following["value"]
                if abs(a-c) <= config.TEMP_SPIKE_NEIGHBOUR_C and min(abs(b-a), abs(b-c)) >= config.TEMP_SPIKE_DELTA_C and (b-a)*(b-c) > 0:
                    current["flag"] = "suspect_spike"
        if fences:
            for item in items:
                if item["flag"] == "ok":
                    if item["value"] < fences[0]:
                        item["flag"] = "unusual_low"
                    elif item["value"] > fences[1]:
                        item["flag"] = "unusual_high"
    output, counts = [], Counter()
    for item in prepared:
        key, year, week, raw, stamp, *extra = item["row"]
        values = (key, year, week, raw, item["value"], item["flag"])
        if kind == "temperature":
            values += (extra[0],)
        output.append(values + (stamp,))
        counts[item["flag"]] += 1
    return output, dict(sorted(counts.items()))
