"""Read-only M3 text, treatment and identity investigation from M2 tables."""
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
from statistics import median
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from db import DB_PATH, connect, snapshot


def normal_key(value):
    # Comparison/proposal key only. Never writes a canonical name or merges IDs.
    normalized = unicodedata.normalize('NFC', value).translate(str.maketrans({'İ':'i','ı':'i'}))
    return ' '.join(normalized.split()).casefold()


def profile_categories(db_path=DB_PATH):
    con = connect(db_path, read_only=True)
    try:
        before = snapshot(con)
        text = {}
        for label, sql in {
            'municipality.name': 'SELECT name, COUNT(*) FROM municipality GROUP BY name ORDER BY name',
            'locality.name': 'SELECT name, COUNT(*) FROM locality GROUP BY name ORDER BY name',
            'locality.registry_version': 'SELECT registry_version, COUNT(*) FROM locality GROUP BY registry_version ORDER BY registry_version',
            'treatment_event.category': 'SELECT category, COUNT(*) FROM treatment_event GROUP BY category ORDER BY category',
            'treatment_event.treatment_type': 'SELECT treatment_type, COUNT(*) FROM treatment_event GROUP BY treatment_type ORDER BY treatment_type',
            'treatment_event.substance_name': 'SELECT substance_name, COUNT(*) FROM treatment_event GROUP BY substance_name ORDER BY substance_name',
            'treatment_event.substance_id': 'SELECT substance_id, COUNT(*) FROM treatment_event GROUP BY substance_id ORDER BY substance_id',
        }.items():
            values = con.execute(sql).fetchall()
            grouped = defaultdict(list)
            changed = []
            for value, count in values:
                if value is not None:
                    grouped[normal_key(value)].append(value)
                    if value != unicodedata.normalize('NFC', value) or value != ' '.join(value.split()):
                        changed.append([repr(value), count])
            text[label] = {'repr_inventory': [[repr(v), n] for v, n in values],
                           'normalization_changes': changed,
                           'normalization_collisions': [v for v in grouped.values() if len(v)>1]}
        duplicates = con.execute('SELECT name, COUNT(*) FROM locality GROUP BY name HAVING COUNT(*)>1 ORDER BY name').fetchall()
        locality_names = con.execute('SELECT locality_no, name, municipality_key FROM locality ORDER BY locality_no').fetchall()
        identity_candidates = []
        grouped = defaultdict(list)
        for number, name, municipality in locality_names:
            if name:
                grouped[(normal_key(name), municipality)].append(number)
        for (name, municipality), numbers in grouped.items():
            if len(numbers)>1:
                identity_candidates.append({'name_key': name, 'municipality_key': municipality, 'locality_nos': numbers})
        treatment = con.execute('SELECT locality_key, year, week, category, treatment_type, substance_name, substance_id, number_of_cages, entire_locality, done_before_lice_count, details_json FROM treatment_event ORDER BY locality_key, year, week, category, event_seq').fetchall()
        per_category = {}
        for category in sorted({r[3] for r in treatment}):
            rows = [r for r in treatment if r[3]==category]
            cages = [r[7] for r in rows if r[7] is not None]
            per_category[category] = {'rows':len(rows), 'null_type':sum(r[4] is None for r in rows),
                'null_substance':sum(r[5] is None for r in rows), 'null_cages':sum(r[7] is None for r in rows),
                'cages_min_median_max': [min(cages),median(cages),max(cages)] if cages else None,
                'negative_cages':sum(v<0 for v in cages),
                'entire_locality':dict(Counter(repr(r[8]) for r in rows)),
                'done_before_lice_count':dict(Counter(repr(r[9]) for r in rows))}
        code_names = defaultdict(set)
        for row in treatment:
            if row[6] is not None:
                code_names[row[6]].add(row[5])
        per_locality = {}
        for key in sorted({r[0] for r in treatment}):
            rows = [r for r in treatment if r[0]==key]
            cages = [r[7] for r in rows if r[7] is not None]
            number = con.execute('SELECT locality_no FROM locality WHERE locality_key=?',(key,)).fetchone()[0]
            per_locality[number] = {'events':len(rows),'missing_cages':sum(r[7] is None for r in rows),
                'cages_min_median_max':[min(cages),median(cages),max(cages)] if cages else None,
                'first_week':min((r[1],r[2]) for r in rows),'last_week':max((r[1],r[2]) for r in rows)}
        result = {'text':text, 'duplicate_exact_name_groups':len(duplicates),
                  'duplicate_exact_name_examples':duplicates[:15],
                  'same_normalized_name_and_municipality_candidates':identity_candidates,
                  'treatment_by_category':per_category,
                  'treatment_by_locality':per_locality,
                  'substance_code_names':{k:sorted(v) for k,v in sorted(code_names.items())},
                  'weekly_flags':con.execute('SELECT mechanical_removal, mechanical_removal_entire_locality, COUNT(*) FROM treatment_weekly GROUP BY 1,2').fetchall(),
                  'treatment_periods':con.execute('SELECT l.locality_no, MIN(t.year*100+t.week), MAX(t.year*100+t.week), COUNT(*) FROM treatment_weekly t JOIN locality l USING(locality_key) GROUP BY l.locality_no ORDER BY l.locality_no').fetchall(),
                  'combination_nested_sizes':[{'locality_key':r[0],'year':r[1],'week':r[2],
                      'medicinal':len(json.loads(r[10]).get('medicinalTreatments') or []),
                      'non_medicinal':len(json.loads(r[10]).get('nonMedicinalTreatments') or [])}
                      for r in treatment if r[3]=='combination'],
                  'm2_unchanged':snapshot(con)==before}
        return result
    finally:
        con.close()


if __name__=='__main__':
    print(json.dumps(profile_categories(),ensure_ascii=False,indent=2))
