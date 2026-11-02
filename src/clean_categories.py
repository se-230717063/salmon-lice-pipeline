"""M3 entity/treatment cleaning inside the caller's transaction. No import side effects."""
from collections import Counter
import csv
from datetime import date
import unicodedata

MAPPING_SPECS = (
    ('municipality_name_mapping', ('municipality_no','raw_name','clean_name','decided_by','decided_at','note'), 'DELETE FROM municipality_name_mapping', 'INSERT INTO municipality_name_mapping VALUES (?, ?, ?, ?, ?, ?)'),
    ('locality_name_mapping', ('locality_no','raw_name','clean_name','decided_by','decided_at','note'), 'DELETE FROM locality_name_mapping', 'INSERT INTO locality_name_mapping VALUES (?, ?, ?, ?, ?, ?)'),
    ('treatment_value_mapping', ('field','raw_value','clean_value','decided_by','decided_at','note'), 'DELETE FROM treatment_value_mapping', 'INSERT INTO treatment_value_mapping VALUES (?, ?, ?, ?, ?, ?)'),
    ('locality_identity_mapping', ('source_locality_no','canonical_locality_no','decided_by','decided_at','note'), 'DELETE FROM locality_identity_mapping', 'INSERT INTO locality_identity_mapping VALUES (?, ?, ?, ?, ?)'),
)
INSERT_MUNICIPALITY = 'INSERT INTO municipality_clean VALUES (?, ?, ?, ?, ?, ?)'
INSERT_LOCALITY = 'INSERT INTO locality_clean VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
INSERT_WEEKLY = 'INSERT INTO treatment_weekly_clean VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
INSERT_EVENT = 'INSERT INTO treatment_event_clean VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'


def read_mappings(directory):
    mappings = {}
    for name, columns, _, _ in MAPPING_SPECS:
        path = directory / (name + '.csv')
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != columns:
                raise ValueError('Unexpected CSV header: ' + name)
            rows = []
            for row in reader:
                if None in row or any(row.get(column) is None or not row[column].strip() for column in columns):
                    raise ValueError('Incomplete mapping row: ' + name)
                date.fromisoformat(row['decided_at'])
                rows.append(row)
        mappings[name] = rows
    if mappings['locality_identity_mapping']:
        # Fail safely instead of producing per-locality statistics before identity resolution.
        raise ValueError('Identity mappings require a resolved measurement grouping implementation first')
    return mappings


def build_categories(con, mappings_dir, *, tick=lambda: None):
    mappings = read_mappings(mappings_dir)
    for name, columns, delete, insert in MAPPING_SPECS:
        con.execute(delete)
        for row in mappings[name]:
            values = tuple(int(row[column]) if column in ('locality_no','source_locality_no','canonical_locality_no') else row[column] for column in columns)
            con.execute(insert, values)
            tick()
    names = {
        'municipality': {(row['municipality_no'],row['raw_name']):row['clean_name'] for row in mappings['municipality_name_mapping']},
        'locality': {(int(row['locality_no']),row['raw_name']):row['clean_name'] for row in mappings['locality_name_mapping']},
    }
    vocabulary = {(row['field'],row['raw_value']):row['clean_value'] for row in mappings['treatment_value_mapping']}
    used = {'municipality_name_mapping':set(), 'locality_name_mapping':set(), 'treatment_value_mapping':set(), 'locality_identity_mapping':set()}
    flags, counts = {}, {}

    def name_value(kind, number, raw):
        if raw is None:
            return None, 'missing_unknown'
        key = (number, raw)
        if key in names[kind]:
            used[kind + '_name_mapping'].add(key)
            value = names[kind][key]
            return value, 'mapped' if value != raw else 'ok'
        comparison = ' '.join(unicodedata.normalize('NFC', raw).split())
        return raw, 'unmatched' if comparison != raw else 'ok'

    def text_value(field, raw, structural=False):
        if raw is None:
            return None, 'not_applicable' if structural else 'missing_unknown'
        key = (field, raw)
        if key in vocabulary:
            used['treatment_value_mapping'].add(key)
            value = vocabulary[key]
            return value, 'mapped' if value != raw else 'ok'
        if field == 'substance_id' and raw == '0':
            return raw, 'ambiguous_code'
        return raw, 'ok'

    for sql in ('DELETE FROM treatment_event_clean', 'DELETE FROM treatment_weekly_clean', 'DELETE FROM locality_clean', 'DELETE FROM municipality_clean'):
        con.execute(sql)
    municipality_flags = Counter()
    for key, number, raw, stamp in con.execute('SELECT municipality_key, municipality_no, name, retrieved_at FROM municipality ORDER BY municipality_key').fetchall():
        value, flag = name_value('municipality', number, raw)
        con.execute(INSERT_MUNICIPALITY, (key,number,raw,value,flag,stamp))
        municipality_flags[flag] += 1
        tick()
    flags['municipality_clean.name'] = dict(municipality_flags)
    counts['municipality_clean'] = sum(municipality_flags.values())
    locality_flags, registry_flags = Counter(), Counter()
    for key, number, raw, municipality, version, stamp in con.execute('SELECT locality_key, locality_no, name, municipality_key, registry_version, retrieved_at FROM locality ORDER BY locality_key').fetchall():
        value, flag = name_value('locality', number, raw)
        version_flag = 'missing_unknown' if version is None else 'ok'
        con.execute(INSERT_LOCALITY, (key,number,municipality,raw,value,flag,version,version,version_flag,stamp))
        locality_flags[flag] += 1
        registry_flags[version_flag] += 1
        tick()
    flags['locality_clean.name'], flags['locality_clean.registry_version'] = dict(locality_flags), dict(registry_flags)
    counts['locality_clean'] = sum(locality_flags.values())
    weekly_flags = [Counter(), Counter()]
    for key, year, week, removal, entire, version, stamp in con.execute('SELECT * FROM treatment_weekly ORDER BY locality_key, year, week').fetchall():
        removal_flag = 'missing_unknown' if removal is None else 'ok'
        entire_flag = 'missing_unknown' if entire is None else 'ok'
        cleaned_entire = entire
        if entire == 1 and removal == 0:
            cleaned_entire, entire_flag = None, 'conflict'
        con.execute(INSERT_WEEKLY, (key,year,week,removal,removal,removal_flag,entire,cleaned_entire,entire_flag,version,stamp))
        weekly_flags[0][removal_flag] += 1
        weekly_flags[1][entire_flag] += 1
        tick()
    flags['treatment_weekly_clean.mechanical_removal'] = dict(weekly_flags[0])
    flags['treatment_weekly_clean.mechanical_removal_entire_locality'] = dict(weekly_flags[1])
    counts['treatment_weekly_clean'] = sum(weekly_flags[0].values())
    event_flags = {field:Counter() for field in ('category','treatment_type','substance_name','substance_id','number_of_cages')}
    for row in con.execute('SELECT * FROM treatment_event ORDER BY locality_key, year, week, category, event_seq').fetchall():
        key, year, week, category, seq, external_id, treatment_type, substance_name, substance_id, cages, entire, before_lice, report_id, details, stamp = row
        category_value, category_flag = text_value('category',category)
        type_value, type_flag = text_value('treatment_type',treatment_type,category=='combination')
        substance_value, substance_flag = text_value('substance_name',substance_name,category!='medicinal')
        id_value, id_flag = text_value('substance_id',substance_id,category!='medicinal')
        clean_cages = cages
        cages_flag = ('not_applicable' if category=='combination' else 'missing_unknown') if cages is None else 'ok'
        if cages is not None and cages < 0:
            clean_cages, cages_flag = None, 'invalid_negative'
        con.execute(INSERT_EVENT, (key,year,week,category,seq,category,category_value,category_flag,external_id,
            treatment_type,type_value,type_flag,substance_name,substance_value,substance_flag,
            substance_id,id_value,id_flag,cages,clean_cages,cages_flag,entire,before_lice,report_id,details,stamp))
        for field, flag in zip(event_flags, (category_flag,type_flag,substance_flag,id_flag,cages_flag)):
            event_flags[field][flag] += 1
        tick()
    for field, counter in event_flags.items():
        flags['treatment_event_clean.'+field] = dict(counter)
    counts['treatment_event_clean'] = sum(event_flags['category'].values())
    unmatched = []
    for kind in ('municipality','locality'):
        for key in names[kind]:
            if key not in used[kind+'_name_mapping']:
                unmatched.append({'mapping':kind+'_name_mapping','key':key})
    for key in vocabulary:
        if key not in used['treatment_value_mapping']:
            unmatched.append({'mapping':'treatment_value_mapping','key':key})
    return {'mapping_rows_loaded':{name:len(rows) for name,rows in mappings.items()},
            'mapping_entries_matched':{name:len(keys) for name,keys in used.items()},
            'unmatched_mapping_entries':unmatched, 'table_rows':counts, 'flag_counts':flags}
