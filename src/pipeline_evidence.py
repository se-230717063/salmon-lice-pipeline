"""Deterministic source/raw fingerprints and real scheduled-run summaries."""
from datetime import timedelta, timezone
import hashlib
from itertools import groupby
import json

from db import ROOT, connect
from pipeline_runtime import parse_time
from run_pipeline import STEPS


def fingerprint(root=ROOT, *, raw=False):
    root = root.resolve()
    if raw:
        paths = sorted((root/'data/raw').glob('*/*.json'))
    else:
        paths = sorted([*(root/'src').glob('*.py'),*(root/'notebooks').glob('*.py'),
                        *(root/'sql').rglob('*.sql'),*(root/'data/mappings').glob('*.csv'),
                        root/'config/cohort.txt',root/'requirements.txt'])
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(b'\0')
        content = path.read_bytes()
        if not raw:
            # Git core.autocrlf may change checkout line endings without changing code.
            content = content.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
        digest.update(hashlib.sha256(content).digest())
    return {'sha256':digest.hexdigest(),'files':len(paths)}


def run_summary(log_path):
    con = connect(log_path,read_only=True)
    try:
        rows = con.execute('SELECT run_id,run_time,run_kind,step,exit_code,detail FROM pipeline_run ORDER BY run_id,started_at').fetchall()
    finally:
        con.close()
    runs = []
    for identifier,group in groupby(rows,key=lambda row:row[0]):
        group = list(group)
        full = (len(group)==len(STEPS) and {r[3] for r in group}==set(STEPS) and all(r[4]==0 for r in group))
        runs.append({'run_id':identifier,'run_time':group[0][1],'kind':group[0][2],
                     'fully_successful_live':full,'failed_steps':[r[3] for r in group if r[4]!=0]})
    scheduled = sorted(row['run_time'] for row in runs if row['kind']=='scheduled' and row['fully_successful_live'])
    days = sorted({parse_time(stamp).astimezone(timezone(timedelta(hours=3))).date() for stamp in scheduled})
    longest = current = 0
    previous = None
    for day in days:
        current = current+1 if previous is not None and day-previous==timedelta(days=1) else 1
        longest = max(longest,current)
        previous = day
    return {'runs':runs,'scheduled_successes':len(scheduled),'scheduled_local_dates':[day.isoformat() for day in days],
            'longest_consecutive_local_days':longest,'first_scheduled_success':scheduled[0] if scheduled else None,
            'last_scheduled_success':scheduled[-1] if scheduled else None}
