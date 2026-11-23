"""Capture actual experiment states; refuses to invent recovery before it happens."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect, table_counts
from load import collect, clean_real
from monitor import monitor
from pipeline_runtime import iso_time, run_clock, parse_time
from run_pipeline import LOG_PATH, STEPS

OUTPUT = ROOT/'output/m5_experiment'
EXPECTED_MISSES = ['2026-11-24T17:15:00Z','2026-11-25T12:15:00Z']


def capture(phase,clock):
    if (ROOT/'data/pipeline.lock').exists():
        raise RuntimeError('Pipeline still running; wait before capturing a stable state')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    con = connect(DB_PATH,read_only=True)
    try:
        counts = table_counts(con)
        target = con.execute('SELECT COUNT(*),SUM(has_reported) FROM sea_temperature_weekly WHERE year=? AND week=?',(2026,47)).fetchone()
        lice = con.execute('SELECT COUNT(*) FROM lice_weekly WHERE year=? AND week=?',(2026,47)).fetchone()[0]
        payload = {'phase':phase,'captured_at':iso_time(clock),'target_period':[2026,47],
                   'target_status_rows':target[0],'target_reported_temperature_rows':target[1],
                   'target_lice_rows':lice,'counts':counts,'monitor':monitor(now=clock),
                   'raw_json_files':len(list((ROOT/'data/raw').glob('*/*.json')))}
        if phase=='after':
            before = json.loads((OUTPUT/'before.json').read_text(encoding='utf-8'))
            log = connect(LOG_PATH,read_only=True)
            try:
                rows = log.execute("SELECT run_id,run_time,step,exit_code,detail FROM pipeline_run WHERE run_kind='scheduled' AND run_time>? ORDER BY run_time,started_at",(before['captured_at'],)).fetchall()
            finally:
                log.close()
            runs = defaultdict(list)
            for row in rows:
                runs[row[0]].append(row)
            complete = [group for group in runs.values() if len(group)==4 and
                        {r[2] for r in group}==set(STEPS) and all(r[3]==0 for r in group)]
            if not complete:
                raise RuntimeError('No fully successful scheduled recovery run after experiment began')
            recovered = complete[-1]
            gaps = next(row for row in payload['monitor'] if row['check']=='gaps')
            if not set(EXPECTED_MISSES)<=set(gaps['detail'].get('missing_scheduled_slots',[])):
                raise RuntimeError('Expected two real missed slots have not been demonstrated')
            # Verify every latest landed measurement key/value/version against M2,
            # rather than claiming that a successful HTTP status proves completeness.
            best,_,_,_,_ = collect(ROOT/'data/raw')
            matches = {}
            for kind,sql,field in (
                ('lice','SELECT l.locality_no,t.year,t.week,t.avg_adult_female_lice,t.retrieved_at FROM lice_weekly t JOIN locality l USING(locality_key)','value'),
                ('temperature','SELECT l.locality_no,t.year,t.week,t.sea_temperature,t.retrieved_at FROM sea_temperature_weekly t JOIN locality l USING(locality_key)','seaTemperature')):
                actual = {(n,y,w):(value,stamp) for n,y,w,value,stamp in con.execute(sql)}
                mismatch = []
                for key,((stamp,_),row) in best[kind].items():
                    expected = (clean_real(row.get(field),kind,Counter()),stamp)
                    if actual.get(key)!=expected:
                        mismatch.append(key)
                if mismatch:
                    raise RuntimeError('Recovery raw/DB mismatch in '+kind+': '+str(mismatch[:5]))
                matches[kind] = {'verified_latest_raw_keys':len(best[kind]),'mismatches':0}
            ingest_row = next(row for row in recovered if row[2]=='src/ingest.py')
            path = (ROOT/json.loads(ingest_row[4])['output']).resolve()
            if not path.is_relative_to((ROOT/'logs').resolve()):
                raise ValueError('Unexpected ingestion log path')
            line = next(line for line in path.read_text(encoding='utf-8').splitlines() if line.startswith('INGEST_SUMMARY '))
            acquisition = json.loads(line.split(' ',1)[1])
            payload.update({'status':'real_missed_run_recovery_verified','before_captured_at':before['captured_at'],
                'expected_missed_slots':EXPECTED_MISSES,'recovery_run_id':recovered[0][0],
                'recovery_run_time':recovered[0][1],'acquisition':acquisition,'raw_to_db':matches,
                'target_lice_row_change':lice-before['target_lice_rows'],
                'note':'A zero row delta is reported honestly if the weekly source did not change during the gap.'})
    finally:
        con.close()
    (OUTPUT/(phase+'.json')).write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    if phase=='after':
        (ROOT/'docs/evidence/m5_missed_run_recovery.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('Captured',phase,'at',iso_time(clock))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('before','after'))
    args = parser.parse_args()
    capture(args.phase,run_clock())
