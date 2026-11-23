"""Test committed code in a fresh local Git clone with a frozen copy of landed raw."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import connect
from explore import snapshot_all
from pipeline_evidence import fingerprint
from pipeline_runtime import iso_time, run_clock


def check():
    if (ROOT/'data/pipeline.lock').exists():
        raise RuntimeError('Wait for the active pipeline before freezing raw data for a fresh clone')
    clock = iso_time(run_clock())
    source_fingerprint = fingerprint()
    raw_fingerprint = fingerprint(raw=True)
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ,PYTHONUTF8='1')
    with tempfile.TemporaryDirectory(dir=base) as folder:
        checkout = Path(folder)/'checkout'
        subprocess.run(['git','clone','--quiet','--local','--no-hardlinks',str(ROOT),str(checkout)],
                       check=True,capture_output=True,timeout=60)
        if fingerprint(checkout)!=source_fingerprint:
            raise RuntimeError('Commit all source changes before verifying a fresh clone')
        shutil.copytree(ROOT/'data/raw',checkout/'data/raw',dirs_exist_ok=True)
        if fingerprint(checkout,raw=True)!=raw_fingerprint:
            raise RuntimeError('Raw changed during snapshot; retry after the scheduled run')
        commands = [
            [sys.executable,'-X','utf8','src/run_pipeline.py','--skip-ingest','--run-time',clock],
            [sys.executable,'-X','utf8','notebooks/build_m4.py'],
            [sys.executable,'-X','utf8','-m','nbconvert','--to','notebook','--execute','--inplace',
             'notebooks/m4_eda.ipynb','--ExecutePreprocessor.timeout=180']]
        completed = subprocess.run(commands[0],cwd=checkout,env=env,capture_output=True,
                                   text=True,encoding='utf-8',timeout=180)
        assert completed.returncode==0,completed.stdout+completed.stderr
        con = connect(checkout/'data/salmon_lice.db',read_only=True)
        before = snapshot_all(con)
        con.close()
        for command in commands[1:]:
            completed = subprocess.run(command,cwd=checkout,env=env,capture_output=True,
                                       text=True,encoding='utf-8',timeout=300)
            assert completed.returncode==0,completed.stdout+completed.stderr
        con = connect(checkout/'data/salmon_lice.db',read_only=True)
        assert snapshot_all(con)==before
        con.close()
        if fingerprint(raw=True)!=raw_fingerprint:
            raise RuntimeError('Live raw changed during clone check; retry against one stable snapshot')
        result = {'tested_commit':commit,'run_time':clock,'fresh_git_clone':True,
                  'offline_runner_exit_code':0,'m4_notebook_exit_code':0,'m4_all_17_tables_unchanged':True,
                  'source_fingerprint':source_fingerprint,'raw_fingerprint':raw_fingerprint,
                  'figure_count':len(list((checkout/'figures').glob('*.png')))}
    (ROOT/'docs/evidence/m5_fresh_clone.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    check()
