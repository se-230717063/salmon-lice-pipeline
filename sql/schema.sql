-- Schema for the salmon lice database. Safe to run repeatedly.
-- Surrogate keys (INTEGER PRIMARY KEY) for entities; the source id is kept as NOT NULL UNIQUE.
-- Timestamps: TEXT, ISO 8601 UTC (2026-10-10T18:09:54Z).

CREATE TABLE IF NOT EXISTS municipality (
    municipality_key INTEGER PRIMARY KEY,
    municipality_no  TEXT NOT NULL UNIQUE,
    name             TEXT,
    retrieved_at     TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS locality (
    locality_key     INTEGER PRIMARY KEY,
    locality_no      INTEGER NOT NULL UNIQUE,
    name             TEXT,
    municipality_key INTEGER REFERENCES municipality (municipality_key),
    registry_version TEXT,
    retrieved_at     TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS lice_weekly (
    locality_key          INTEGER NOT NULL REFERENCES locality (locality_key),
    year                  INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    week                  INTEGER NOT NULL CHECK (week BETWEEN 1 AND 53),
    avg_adult_female_lice REAL,
    retrieved_at          TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week)
) STRICT;

CREATE TABLE IF NOT EXISTS sea_temperature_weekly (
    locality_key    INTEGER NOT NULL REFERENCES locality (locality_key),
    year            INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    week            INTEGER NOT NULL CHECK (week BETWEEN 1 AND 53),
    sea_temperature REAL,
    has_reported    INTEGER NOT NULL CHECK (has_reported IN (0, 1)),
    retrieved_at    TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week)
) STRICT;

CREATE TABLE IF NOT EXISTS treatment_weekly (
    locality_key                       INTEGER NOT NULL REFERENCES locality (locality_key),
    year                               INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    week                               INTEGER NOT NULL CHECK (week BETWEEN 1 AND 53),
    mechanical_removal                 INTEGER CHECK (mechanical_removal IN (0, 1)),
    mechanical_removal_entire_locality INTEGER CHECK (mechanical_removal_entire_locality IN (0, 1)),
    record_version                     INTEGER,
    retrieved_at                       TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week)
) STRICT;

-- One row per item of the nested treatment lists. Medicinal items have no id in the source,
-- so an event is identified by its list position (event_seq) within (week, category).
-- details_json keeps the complete original item, including nested lists.
CREATE TABLE IF NOT EXISTS treatment_event (
    locality_key           INTEGER NOT NULL,
    year                   INTEGER NOT NULL,
    week                   INTEGER NOT NULL,
    category               TEXT NOT NULL CHECK (category IN
                           ('medicinal', 'non_medicinal', 'cleaner_fish', 'combination')),
    event_seq              INTEGER NOT NULL CHECK (event_seq >= 1),
    source_event_id        INTEGER,
    treatment_type         TEXT,
    substance_name         TEXT,
    substance_id           TEXT,
    number_of_cages        INTEGER,
    entire_locality        INTEGER CHECK (entire_locality IN (0, 1)),
    done_before_lice_count INTEGER CHECK (done_before_lice_count IN (0, 1)),
    lice_report_id         TEXT,
    details_json           TEXT NOT NULL,
    retrieved_at           TEXT NOT NULL,
    PRIMARY KEY (locality_key, year, week, category, event_seq),
    FOREIGN KEY (locality_key, year, week)
        REFERENCES treatment_weekly (locality_key, year, week)
) STRICT;

-- Records that cannot be loaded (unknown locality, wrong shape, unreadable file).
-- The UNIQUE constraint makes re-running a load add nothing new.
CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_id INTEGER PRIMARY KEY,
    source_kind   TEXT NOT NULL,
    source_file   TEXT NOT NULL,
    reason        TEXT NOT NULL,
    raw_payload   TEXT NOT NULL,
    retrieved_at  TEXT NOT NULL,
    UNIQUE (source_file, reason, raw_payload)
) STRICT;