"""Export real manual pipeline evidence; never relabel it as scheduled evidence."""
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect, table_counts
from run_pipeline import LOG_PATH, STEPS
from pipeline_runtime import parse_time
from validate import validate


def summarize():
    con = connect(LOG_PATH,read_only=True)
    try:
        records = con.execute('SELECT run_id,run_time,step,started_at,finished_at,exit_code,run_kind,detail FROM pipeline_run ORDER BY run_time,started_at').fetchall()
    finally:
        con.close()
    runs = defaultdict(list)
    for row in records:
        runs[row[0]].append(row)
    complete = [rows for rows in runs.values() if rows[0][6]=='manual' and
                {r[2] for r in rows}==set(STEPS) and all(r[5]==0 for r in rows)]
    if not complete:
        raise RuntimeError('No real completed manual live pipeline run to export')
    rows = complete[-1]
    steps = [{'step':r[2],'started_at':r[3],'finished_at':r[4],'exit_code':r[5],
              'seconds':(parse_time(r[4])-parse_time(r[3])).total_seconds()} for r in rows]
    con = connect(DB_PATH,read_only=True)
    try:
        counts = table_counts(con)
    finally:
        con.close()
    payload = {'run_id':rows[0][0],'run_time':rows[0][1],'run_kind':'manual',
               'counts_as_scheduled_evidence':False,'steps':steps,
               'total_seconds':(parse_time(rows[-1][4])-parse_time(rows[0][3])).total_seconds(),
               'source_table_counts':counts,
               'scheduled_runs_so_far':len({r[0] for r in records if r[6]=='scheduled'}),
               'post_review_validation':validate(DB_PATH,run_time=parse_time(rows[0][1]))}
    (ROOT/'docs/evidence/m5_live_review.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k not in ('post_review_validation',)},indent=2))
    print('Current WARNs:',[r['id'] for r in payload['post_review_validation'] if r['level']=='WARN'])


if __name__=='__main__':
    summarize()
