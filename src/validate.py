"""Read-only M3 expectations. STOP exits 1; WARN is visible but does not stop the build."""
import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
import math
from pathlib import Path
import sqlite3

import clean_config
from db import DB_PATH, ROOT, connect

# Review threshold, not a deletion rule: tolerate occasional gaps, warn when >1/3
# of expected elapsed weeks have no usable temperature. See cleaning_report section 7.
MAX_MISSING_SHARE = 0.35
FRESHNESS_LAG_WEEKS = 1  # Current ISO week is incomplete at retrieval; expect the previous week.

# Every paired query has identical source grain/order. No identifier interpolation.
RAW_PAIRS = {
    'municipality_clean': ('SELECT municipality_key, municipality_no, name, retrieved_at FROM municipality ORDER BY municipality_key', 'SELECT municipality_key, municipality_no, name_raw, retrieved_at FROM municipality_clean ORDER BY municipality_key'),
    'locality_clean': ('SELECT locality_key, locality_no, name, municipality_key, registry_version, retrieved_at FROM locality ORDER BY locality_key', 'SELECT locality_key, locality_no, name_raw, municipality_key, registry_version_raw, retrieved_at FROM locality_clean ORDER BY locality_key'),
    'lice_weekly_clean': ('SELECT locality_key, year, week, avg_adult_female_lice, retrieved_at FROM lice_weekly ORDER BY locality_key, year, week', 'SELECT locality_key, year, week, avg_adult_female_lice_raw, retrieved_at FROM lice_weekly_clean ORDER BY locality_key, year, week'),
    'sea_temperature_weekly_clean': ('SELECT locality_key, year, week, sea_temperature, has_reported, retrieved_at FROM sea_temperature_weekly ORDER BY locality_key, year, week', 'SELECT locality_key, year, week, sea_temperature_raw, has_reported, retrieved_at FROM sea_temperature_weekly_clean ORDER BY locality_key, year, week'),
    'treatment_weekly_clean': ('SELECT * FROM treatment_weekly ORDER BY locality_key, year, week', 'SELECT locality_key, year, week, mechanical_removal_raw, mechanical_removal_entire_locality_raw, record_version, retrieved_at FROM treatment_weekly_clean ORDER BY locality_key, year, week'),
    'treatment_event_clean': ('SELECT * FROM treatment_event ORDER BY locality_key, year, week, category, event_seq', 'SELECT locality_key, year, week, category, event_seq, source_event_id, treatment_type_raw, substance_name_raw, substance_id_raw, number_of_cages_raw, entire_locality, done_before_lice_count, lice_report_id, details_json, retrieved_at FROM treatment_event_clean ORDER BY locality_key, year, week, category, event_seq'),
}


def validate(db_path=DB_PATH):
    results = []

    def record(identifier, severity, passed, detail):
        results.append({'id':identifier,'level':'PASS' if passed else severity,'detail':detail})

    con = connect(db_path, read_only=True)
    try:
        pairs = {}
        try:
            pairs = {name:(con.execute(raw).fetchall(),con.execute(clean).fetchall()) for name,(raw,clean) in RAW_PAIRS.items()}
        except sqlite3.OperationalError as exc:
            record('row_counts','STOP',False,'Missing or incompatible clean schema: '+str(exc))
            return results
        unequal = {name:(len(raw),len(clean)) for name,(raw,clean) in pairs.items() if len(raw)!=len(clean)}
        record('row_counts','STOP',not unequal,str(unequal) if unequal else 'All six cleaned tables equal their source row counts')
        changed = [name for name,(raw,clean) in pairs.items() if raw!=clean]
        record('raw_preservation','STOP',not changed,'Changed keys/raw/provenance: '+str(changed))
        invalid = {
            'negative_lice':con.execute('SELECT COUNT(*) FROM lice_weekly_clean WHERE avg_adult_female_lice < ?', (0,)).fetchone()[0],
            'temperature_range':con.execute('SELECT COUNT(*) FROM sea_temperature_weekly_clean WHERE sea_temperature < ? OR sea_temperature > ?', (clean_config.TEMP_MIN_C,clean_config.TEMP_MAX_C)).fetchone()[0],
            'negative_cages':con.execute('SELECT COUNT(*) FROM treatment_event_clean WHERE number_of_cages < ?', (0,)).fetchone()[0],
            'invalid_flag_with_value':con.execute("SELECT COUNT(*) FROM sea_temperature_weekly_clean WHERE sea_temperature_flag IN ('invalid_iso_week','future_placeholder','future_observation','reporting_conflict','missing_not_reported','missing_unknown','invalid_range') AND sea_temperature IS NOT NULL").fetchone()[0],
            'lice_invalid_flag_with_value':con.execute("SELECT COUNT(*) FROM lice_weekly_clean WHERE avg_adult_female_lice_flag IN ('invalid_iso_week','future_observation','missing_unknown','invalid_negative','invalid_range') AND avg_adult_female_lice IS NOT NULL").fetchone()[0],
        }
        invalid['calendar_or_future_values'] = 0
        for sql in ('SELECT year, week, avg_adult_female_lice, retrieved_at FROM lice_weekly_clean', 'SELECT year, week, sea_temperature, retrieved_at FROM sea_temperature_weekly_clean'):
            for year,week,value,stamp in con.execute(sql):
                if value is None:
                    continue
                try:
                    valid = math.isfinite(value) and date.fromisocalendar(year,week,1) <= datetime.fromisoformat(stamp.replace('Z','+00:00')).date()
                except ValueError:
                    valid = False
                invalid['calendar_or_future_values'] += not valid
        record('impossible_values','STOP',not any(invalid.values()),str(invalid))
        foreign = con.execute('PRAGMA foreign_key_check').fetchall()
        record('foreign_keys','STOP',not foreign,str(foreign) if foreign else 'No M2/M3 foreign-key violations')
        non_strict = [row[1] for row in con.execute('PRAGMA table_list') if row[1] not in ('sqlite_schema','sqlite_temp_schema') and row[2]=='table' and row[-1]!=1]
        record('strict_schema','STOP',not non_strict,'Non-STRICT tables: '+str(non_strict))

        cohort = {int(v) for v in (ROOT/'config/cohort.txt').read_text().split()}
        temperature = con.execute('SELECT l.locality_no, t.year, t.week, t.sea_temperature, t.retrieved_at, t.sea_temperature_flag FROM sea_temperature_weekly_clean t JOIN locality l USING(locality_key)').fetchall()
        shares = defaultdict(lambda:[0,0])
        latest = max(datetime.fromisoformat(row[4].replace('Z','+00:00')).date() for row in temperature)
        expected = (latest-timedelta(weeks=FRESHNESS_LAG_WEEKS)).isocalendar()[:2]
        current = set()
        for number,year,week,value,stamp,flag in temperature:
            if number not in cohort:
                continue
            try:
                elapsed = date.fromisocalendar(year,week,1) <= datetime.fromisoformat(stamp.replace('Z','+00:00')).date()
            except ValueError:
                elapsed = False
            if elapsed:
                shares[number][1] += 1
                shares[number][0] += value is None
            if (year,week)==expected and value is not None:
                current.add(number)
        high_missing = {number:round(shares[number][0]/shares[number][1],4) if shares[number][1] else 1.0 for number in sorted(cohort)
                        if not shares[number][1] or shares[number][0]/shares[number][1] > MAX_MISSING_SHARE}
        record('missing_share','WARN',not high_missing,'Elapsed temperature NULL share > '+str(MAX_MISSING_SHARE)+': '+str(high_missing))
        absent = sorted(cohort-current)
        record('freshness','WARN',not absent,'Expected '+str(expected)+' at retrieval '+str(latest)+'; usable '+str(len(current))+'/40; missing '+str(absent))
        sequences = con.execute("SELECT sea_temperature_flag,COUNT(*) FROM sea_temperature_weekly_clean WHERE sea_temperature_flag IN ('suspect_stuck','suspect_spike') GROUP BY sea_temperature_flag").fetchall()
        record('sequence_review','WARN',not sequences,'Retained suspect measurements: '+str(sequences))
        ambiguous = con.execute("SELECT COUNT(*) FROM treatment_event_clean WHERE substance_id_flag='ambiguous_code'").fetchone()[0]
        record('ambiguous_substance_code','WARN',ambiguous==0,str(ambiguous)+' medicinal events have non-identifying substance code 0; names preserved')
        unknown_cages = con.execute("SELECT COUNT(*) FROM treatment_event_clean WHERE number_of_cages_flag='missing_unknown'").fetchone()[0]
        record('unknown_cages','WARN',unknown_cages==0,str(unknown_cages)+' non-wrapper interventions have unknown cage counts')
        unused = con.execute('SELECT m.locality_no,m.raw_name FROM locality_name_mapping m LEFT JOIN locality l ON l.locality_no=m.locality_no AND l.name=m.raw_name WHERE l.locality_no IS NULL').fetchall()
        unused += con.execute('SELECT m.municipality_no,m.raw_name FROM municipality_name_mapping m LEFT JOIN municipality r ON r.municipality_no=m.municipality_no AND r.name=m.raw_name WHERE r.municipality_no IS NULL').fetchall()
        unused += con.execute("SELECT m.field,m.raw_value FROM treatment_value_mapping m WHERE NOT EXISTS (SELECT 1 FROM treatment_event t WHERE (m.field='category' AND t.category=m.raw_value) OR (m.field='treatment_type' AND t.treatment_type=m.raw_value) OR (m.field='substance_name' AND t.substance_name=m.raw_value) OR (m.field='substance_id' AND t.substance_id=m.raw_value))").fetchall()
        record('mapping_matches','WARN',not unused,'Unused mapping entries: '+str(unused))
        return results
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=DB_PATH)
    args = parser.parse_args()
    try:
        results = validate(args.db)
    except (OSError,sqlite3.Error,ValueError) as exc:
        print('STOP database_read '+str(exc))
        raise SystemExit(1)
    for result in results:
        print(result['level']+' '+result['id']+' '+result['detail'])
    raise SystemExit(1 if any(r['level']=='STOP' for r in results) else 0)


if __name__=='__main__':
    main()
