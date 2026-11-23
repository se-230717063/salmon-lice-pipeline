"""Separate archive age from observed revision evidence; never infer publication delay."""
from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from load import SERIES_FILE, iso_stamp, rows_of


def profile():
    groups = defaultdict(list)
    summary = {}
    for folder in ('lice','temperature','treatments'):
        ages = []
        stamps = set()
        empty = 0
        for path in sorted((ROOT/'data/raw'/folder).glob('*.json')):
            match = SERIES_FILE.match(path.name)
            if not match:
                continue
            stamp = iso_stamp(match['stamp'])
            rows = rows_of(json.loads(path.read_bytes()))
            empty += not rows
            stamps.add(stamp)
            for row in rows:
                try:
                    day = date.fromisocalendar(int(match['year']),row['week'],1)
                except ValueError:
                    continue
                # Future placeholders are not publication delays.
                age = (datetime.fromisoformat(stamp.replace('Z','+00:00')).date()-day).days
                if age>=0:
                    ages.append(age)
                groups[(folder,match['loc'],match['year'],row['week'])].append((stamp,row))
        revisions = 0
        repeated = 0
        for key,versions in groups.items():
            if key[0]!=folder:
                continue
            versions.sort(key=lambda item:item[0])
            repeated += len(versions)>1
            revisions += any(a[1]!=b[1] for a,b in zip(versions,versions[1:]))
        summary[folder] = {'retrievals':len(stamps),'first_retrieval':min(stamps),'last_retrieval':max(stamps),
            'max_archive_age_days':max(ages),'min_archive_age_days':min(ages),
            'keys_with_repeated_observations':repeated,'keys_with_observed_revision':revisions,'empty_annual_arrays':empty}
    result = {'interpretation':'Archive ages are not publication delays. No certified maximum publication/revision lag is inferred.',
              'strategy':'Re-fetch all annual slices from 2022 every run; overlap is the entire supported project history.',
              'sources':summary}
    target = ROOT/'docs/evidence/m5_delay_profile.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    profile()
