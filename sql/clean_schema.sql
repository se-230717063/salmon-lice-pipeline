-- M3. M2 schema.sql and all M2 rows remain untouched.
-- All six cleaned tables preserve their own source grain and primary key.
-- Category tables are the contract for Egemen's build_categories extension;
-- they remain empty until that stage is implemented. This is NOT a final M3 build.

CREATE TABLE IF NOT EXISTS lice_weekly_clean (
    locality_key INTEGER NOT NULL REFERENCES locality(locality_key),
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    avg_adult_female_lice_raw REAL,
    avg_adult_female_lice REAL,
    avg_adult_female_lice_flag TEXT NOT NULL CHECK (avg_adult_female_lice_flag IN (
        'invalid_iso_week', 'future_placeholder', 'future_observation', 'reporting_conflict',
        'missing_not_reported', 'missing_unknown', 'invalid_negative', 'invalid_range',
        'suspect_stuck', 'suspect_spike', 'unusual_low', 'unusual_high', 'ok')),
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week),
    FOREIGN KEY (locality_key, year, week) REFERENCES lice_weekly(locality_key, year, week)
) STRICT;

-- Mapping contracts: Egemen supplies reviewed CSV rows, never Python dictionaries.
-- Natural source identifiers in CSVs remain stable across database rebuilds.
CREATE TABLE IF NOT EXISTS municipality_name_mapping (
    municipality_no TEXT NOT NULL REFERENCES municipality(municipality_no),
    raw_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (municipality_no, raw_name)
) STRICT;

CREATE TABLE IF NOT EXISTS locality_name_mapping (
    locality_no INTEGER NOT NULL REFERENCES locality(locality_no),
    raw_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (locality_no, raw_name)
) STRICT;

-- Global vocabulary decisions do not refer to a single locality, so no entity FK applies.
CREATE TABLE IF NOT EXISTS treatment_value_mapping (
    field TEXT NOT NULL CHECK (field IN ('category', 'treatment_type', 'substance_name', 'substance_id')),
    raw_value TEXT NOT NULL,
    clean_value TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (field, raw_value)
) STRICT;

-- Populate only if identity evidence exists; no merges have been assumed in this stage.
CREATE TABLE IF NOT EXISTS locality_identity_mapping (
    source_locality_no INTEGER PRIMARY KEY REFERENCES locality(locality_no),
    canonical_locality_no INTEGER NOT NULL REFERENCES locality(locality_no),
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    note TEXT NOT NULL,
    CHECK (source_locality_no != canonical_locality_no)
) STRICT;

CREATE TABLE IF NOT EXISTS sea_temperature_weekly_clean (
    locality_key INTEGER NOT NULL REFERENCES locality(locality_key),
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    sea_temperature_raw REAL,
    sea_temperature REAL,
    sea_temperature_flag TEXT NOT NULL CHECK (sea_temperature_flag IN (
        'invalid_iso_week', 'future_placeholder', 'future_observation', 'reporting_conflict',
        'missing_not_reported', 'missing_unknown', 'invalid_negative', 'invalid_range',
        'suspect_stuck', 'suspect_spike', 'unusual_low', 'unusual_high', 'ok')),
    has_reported INTEGER NOT NULL CHECK (has_reported IN (0, 1)),
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week),
    FOREIGN KEY (locality_key, year, week) REFERENCES sea_temperature_weekly(locality_key, year, week)
) STRICT;

CREATE TABLE IF NOT EXISTS municipality_clean (
    municipality_key INTEGER PRIMARY KEY REFERENCES municipality(municipality_key),
    municipality_no TEXT NOT NULL UNIQUE,
    name_raw TEXT,
    name TEXT,
    name_flag TEXT NOT NULL CHECK (name_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    retrieved_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS locality_clean (
    locality_key INTEGER PRIMARY KEY REFERENCES locality(locality_key),
    locality_no INTEGER NOT NULL UNIQUE,
    municipality_key INTEGER REFERENCES municipality(municipality_key),
    name_raw TEXT,
    name TEXT,
    name_flag TEXT NOT NULL CHECK (name_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    registry_version_raw TEXT,
    registry_version TEXT,
    registry_version_flag TEXT NOT NULL CHECK (registry_version_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    retrieved_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS treatment_weekly_clean (
    locality_key INTEGER NOT NULL REFERENCES locality(locality_key),
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    mechanical_removal_raw INTEGER,
    mechanical_removal INTEGER CHECK (mechanical_removal IN (0, 1)),
    mechanical_removal_flag TEXT NOT NULL CHECK (mechanical_removal_flag IN ('ok', 'missing_unknown', 'invalid', 'conflict')),
    mechanical_removal_entire_locality_raw INTEGER,
    mechanical_removal_entire_locality INTEGER CHECK (mechanical_removal_entire_locality IN (0, 1)),
    mechanical_removal_entire_locality_flag TEXT NOT NULL CHECK (mechanical_removal_entire_locality_flag IN ('ok', 'missing_unknown', 'invalid', 'conflict')),
    record_version INTEGER,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week),
    FOREIGN KEY (locality_key, year, week) REFERENCES treatment_weekly(locality_key, year, week)
) STRICT;

CREATE TABLE IF NOT EXISTS treatment_event_clean (
    locality_key INTEGER NOT NULL REFERENCES locality(locality_key),
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('medicinal', 'non_medicinal', 'cleaner_fish', 'combination')),
    event_seq INTEGER NOT NULL,
    category_raw TEXT NOT NULL,
    category_clean TEXT,
    category_flag TEXT NOT NULL CHECK (category_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    source_event_id INTEGER,
    treatment_type_raw TEXT,
    treatment_type TEXT,
    treatment_type_flag TEXT NOT NULL CHECK (treatment_type_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    substance_name_raw TEXT,
    substance_name TEXT,
    substance_name_flag TEXT NOT NULL CHECK (substance_name_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    substance_id_raw TEXT,
    substance_id TEXT,
    substance_id_flag TEXT NOT NULL CHECK (substance_id_flag IN ('ok', 'missing_unknown', 'mapped', 'unmatched')),
    number_of_cages_raw INTEGER,
    number_of_cages INTEGER,
    number_of_cages_flag TEXT NOT NULL CHECK (number_of_cages_flag IN ('ok', 'missing_unknown', 'invalid_negative')),
    entire_locality INTEGER CHECK (entire_locality IN (0, 1)),
    done_before_lice_count INTEGER CHECK (done_before_lice_count IN (0, 1)),
    lice_report_id TEXT,
    details_json TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week, category, event_seq),
    FOREIGN KEY (locality_key, year, week) REFERENCES treatment_weekly(locality_key, year, week),
    FOREIGN KEY (locality_key, year, week, category, event_seq)
        REFERENCES treatment_event(locality_key, year, week, category, event_seq)
) STRICT;
