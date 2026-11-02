"""M3 measurement decisions. Rationale and sensitivity: cleaning_report.md section 5."""
TEMP_MIN_C = -5.0  # Broad seawater screening bound, below NOAA's approximately -2 C minimum.
TEMP_MAX_C = 40.0  # Broad bound above NOAA's approximately 36 C global surface extreme; not a salmon welfare limit.
IQR_MULTIPLIER = 3.0  # Outer fences: flag extremes conservatively, never remove them.
MIN_IQR_OBSERVATIONS = 20  # Require roughly half a reporting year before estimating entity fences.
STUCK_RUN_WEEKS = 6  # Review marker, not a fault diagnosis; exact equality in six consecutive ISO weeks.
TEMP_SPIKE_DELTA_C = 8.0  # Review marker for an isolated rise/fall >=8 C and neighbour agreement <=2 C.
TEMP_SPIKE_NEIGHBOUR_C = 2.0  # Require both neighbouring weeks to be similar; evidence in profile notebook.

# First matching rule wins. Unusual/stuck/spike values remain numerically unchanged.
MEASUREMENT_FLAGS = (
    "invalid_iso_week", "future_placeholder", "future_observation",
    "reporting_conflict", "missing_not_reported", "missing_unknown",
    "invalid_negative", "invalid_range", "suspect_stuck", "suspect_spike",
    "unusual_low", "unusual_high", "ok",
)
