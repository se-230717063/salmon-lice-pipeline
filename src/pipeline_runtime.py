"""UTC clock shared by processes; wall time is for logging and the default clock."""
from datetime import datetime, timezone


def wall_time():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Clock must include a timezone, e.g. 2026-11-23T12:00Z")
    return parsed.astimezone(timezone.utc)


def run_clock(value=None):
    return parse_time(value if value is not None else wall_time())


def iso_time(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
