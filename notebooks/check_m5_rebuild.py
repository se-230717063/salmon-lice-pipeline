"""Real offline runner rebuild twice, guarded old-file replay and M4 execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'notebooks'))
from db import DB_PATH, connect
from explore import snapshot_all
from load import run_load, UPSERT_LICE
from build_m4 import build
from pipeline_runtime import iso_time, parse_time


def check():
    source = connect(DB_PATH,read_only=True)
    original = snapshot_all(source)
    source.close()
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as folder:
        directory = Path(folder)
        target = directory/'fresh.db'
        command = [sys.executable,'-X','utf8','src/run_pipeline.py','--skip-ingest',
                   '--run-time','2026-11-23T12:00Z','--db',str(target),
                   '--log-db',str(directory/'runs.db'),'--lock',str(directory/'run.lock')]
        times = []
        hashes = []
        env = dict(os.environ,PYTHONUTF8='1')
        for _ in range(2):
            start = time.perf_counter()
            completed = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,
                                       encoding='utf-8',env=env,timeout=180)
            assert completed.returncode==0,completed.stdout+completed.stderr
            times.append(time.perf_counter()-start)
            con = connect(target,read_only=True)
            hashes.append(snapshot_all(con))
            con.close()
        assert hashes[0]==hashes[1]
        # Execute the M4 source notebook without overwriting its historical outputs.
        notebook = directory/'m4_fresh.ipynb'
        build(notebook)
        env.update(M4_DB_PATH=str(target),M4_FIGURE_DIR=str(directory/'figures'),
                   M4_EVIDENCE_DIR=str(directory/'evidence'))
        completed = subprocess.run([sys.executable,'-X','utf8','-m','nbconvert','--to','notebook',
                    '--execute','--inplace',str(notebook),'--ExecutePreprocessor.timeout=180'],
                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',env=env,timeout=300)
        assert completed.returncode==0,completed.stdout+completed.stderr
        con = connect(target)
        assert snapshot_all(con)==hashes[0], 'M4 changed DB'
        row = con.execute('SELECT locality_key,year,week,avg_adult_female_lice,retrieved_at FROM lice_weekly LIMIT 1').fetchone()
        correction_stamp = iso_time(parse_time(row[4])+timedelta(seconds=1))
        with con:
            con.execute(UPSERT_LICE,(*row[:3],.123456,correction_stamp))
        con.close()
        start = time.perf_counter()
        run_load(target,quiet=True)
        reload_seconds = time.perf_counter()-start
        con = connect(target,read_only=True)
        kept = con.execute('SELECT avg_adult_female_lice,retrieved_at FROM lice_weekly WHERE locality_key=? AND year=? AND week=?',row[:3]).fetchone()
        con.close()
        assert kept==(.123456,correction_stamp), kept
        source = connect(DB_PATH,read_only=True)
        assert snapshot_all(source)==original
        source.close()
        payload = {'offline_runner_exit_code':0,'same_clock_two_builds_identical':True,
                   'all_17_table_hashes':hashes[0],'rebuild_seconds':times,
                   'full_reload_seconds':reload_seconds,'older_raw_cannot_undo_newer_value':True,
                   'm4_fresh_notebook_exit_code':0,'m4_readonly_tables_unchanged':True,
                   'm4_figure_count':len(list((directory/'figures').glob('*.png'))),
                   'production_database_unchanged':True}
        (ROOT/'docs/evidence/m5_rebuild_checks.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in payload.items() if k!='all_17_table_hashes'},indent=2))


if __name__=='__main__':
    check()
