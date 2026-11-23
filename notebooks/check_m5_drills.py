"""Five completed failure drills. Real missed scheduled runs need later evidence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect
from explore import snapshot_all
from load import run_load, UPSERT_LICE
from pipeline_runtime import iso_time, parse_time


def check():
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True,exist_ok=True)
    source = connect(DB_PATH,read_only=True)
    before = snapshot_all(source)
    evidence = {}
    try:
        with tempfile.TemporaryDirectory(dir=base) as folder:
            directory = Path(folder)
            target = directory/'drill.db'
            con = connect(target,create=True)
            source.backup(con)
            con.close()
            raw = directory/'raw'
            shutil.copytree(ROOT/'data/raw',raw)
            log = directory/'runs.db'
            lock = directory/'run.lock'
            common = [sys.executable,'-X','utf8','src/run_pipeline.py','--db',str(target),
                      '--log-db',str(log),'--lock',str(lock),'--raw-dir',str(raw)]
            env = dict(os.environ,PYTHONUTF8='1')

            def invoke(arguments,expected,environment=env):
                completed = subprocess.run(common+arguments,cwd=ROOT,env=environment,capture_output=True,
                                           text=True,encoding='utf-8',timeout=90)
                assert completed.returncode==expected,completed.stdout+completed.stderr
                con = connect(log,read_only=True)
                rows = con.execute('SELECT run_id,step,exit_code,run_kind FROM pipeline_run ORDER BY started_at,rowid').fetchall()
                con.close()
                identifier = rows[-1][0]
                steps = [{'step':r[1],'exit_code':r[2],'kind':r[3]} for r in rows if r[0]==identifier]
                return {'exit_code':completed.returncode,'steps':steps}

            bad = dict(env,BW_CLIENT_ID='invalid:m5-drill',BW_CLIENT_SECRET='invalid-m5-drill')
            evidence['credential_failure'] = invoke([],1,bad)
            assert len(evidence['credential_failure']['steps'])==1
            evidence['load_failure'] = invoke(['--skip-ingest','--drill-fail-step','load'],1)
            assert len(evidence['load_failure']['steps'])==1
            con = connect(target,read_only=True)
            assert snapshot_all(con)==before
            con.close()
            # Use the fixed raw snapshot for later idempotent loads, then measure
            # a clean failure against that committed source layer.
            baseline = invoke(['--skip-ingest'],0)
            con = connect(target,read_only=True)
            loaded = snapshot_all(con)
            con.close()
            evidence['clean_failure'] = invoke(['--skip-ingest','--drill-fail-step','clean','--drill-after','22000'],1)
            assert len(evidence['clean_failure']['steps'])==2
            con = connect(target,read_only=True)
            assert snapshot_all(con)==loaded
            con.close()
            evidence['timeout'] = invoke(['--skip-ingest','--drill-hang-step','load','--timeout','.3'],124)
            first = subprocess.Popen(common+['--skip-ingest','--drill-hang-step','load','--timeout','3'],
                                     cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                end = time.monotonic()+5
                while not lock.exists() and time.monotonic()<end:
                    time.sleep(.02)
                assert lock.exists()
                completed = subprocess.run(common+['--skip-ingest'],cwd=ROOT,env=env,
                                           capture_output=True,text=True,encoding='utf-8',timeout=10)
                assert completed.returncode==75
                assert first.wait(timeout=10)==124
            finally:
                if first.poll() is None:
                    first.kill()
                    first.wait()
            evidence['concurrent_run'] = {'second_exit_code':75,'no_second_step_ran':True,'first_exit_code':124}
            con = connect(target)
            row = con.execute('SELECT locality_key,year,week,retrieved_at FROM lice_weekly LIMIT 1').fetchone()
            corrected = iso_time(parse_time(row[3])+timedelta(seconds=1))
            with con:
                con.execute(UPSERT_LICE,(*row[:3],.123456,corrected))
            con.close()
            run_load(target,raw_dir=raw,quiet=True)
            con = connect(target,read_only=True)
            assert con.execute('SELECT avg_adult_female_lice,retrieved_at FROM lice_weekly WHERE locality_key=? AND year=? AND week=?',row[:3]).fetchone()==(.123456,corrected)
            con.close()
            evidence['old_file_reloaded'] = {'newer_value_preserved':True}
            evidence['real_missed_runs'] = {'status':'not_yet_performed','fixture_gap_test_is_not_live_evidence':True}
        assert snapshot_all(source)==before
        evidence['production_database_unchanged'] = True
    finally:
        source.close()
    (ROOT/'docs/evidence/m5_failure_drills.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':
    check()
