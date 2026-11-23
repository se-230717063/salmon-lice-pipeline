"""Acceptance checks using real child processes and disposable databases only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['PYTHONUTF8'] = '1'
sys.path.insert(0, str(ROOT/'src'))
from db import connect
from run_pipeline import run_step


def check():
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(dir=base) as folder:
        directory = Path(folder)
        failure = directory/'fail.py'
        later = directory/'later.py'
        sleeper = directory/'sleep.py'
        failure.write_text('raise SystemExit(23)\n', encoding='utf-8')
        later.write_text('raise RuntimeError("must never run")\n', encoding='utf-8')
        sleeper.write_text('import time\ntime.sleep(30)\n', encoding='utf-8')
        log = directory/'runs.db'
        lock = directory/'run.lock'
        common = ['--run-time','2026-11-23T12:00Z','--db',str(directory/'data.db'),
                  '--log-db',str(log),'--lock',str(lock)]

        def invoke(steps, extra=()):
            code = ('import sys; sys.path.insert(0,"src"); import run_pipeline as r; '
                    'r.STEPS='+repr(tuple(str(s) for s in steps))+'; r.main()')
            return [sys.executable,'-c',code,*common,*extra]

        failed = subprocess.run(invoke((failure,later)), cwd=ROOT, capture_output=True, text=True)
        assert failed.returncode == 23, failed.stdout+failed.stderr
        con = connect(log, read_only=True)
        rows = con.execute('SELECT step,exit_code,run_kind,run_time FROM pipeline_run').fetchall()
        con.close()
        assert len(rows)==1 and rows[0][1:]==(23,'manual','2026-11-23T12:00:00Z'), rows
        assert not lock.exists()
        results['failure_code_and_no_later_step'] = True
        timed = subprocess.run(invoke((sleeper,later),('--timeout','0.2')),cwd=ROOT,
                               capture_output=True,text=True)
        assert timed.returncode==124, timed.stdout+timed.stderr
        results['timeout_124_logged'] = True
        first = subprocess.Popen(invoke((sleeper,),('--timeout','2')),cwd=ROOT,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+5
            while not lock.exists() and time.monotonic()<deadline:
                time.sleep(.02)
            assert lock.exists(), 'First runner did not acquire lock'
            second = subprocess.run(invoke((failure,)),cwd=ROOT,capture_output=True,text=True)
            assert second.returncode==75, second.stdout+second.stderr
            assert first.wait(timeout=6)==124
        finally:
            if first.poll() is None:
                first.kill()
                first.wait()
        con = connect(log,read_only=True)
        rows = con.execute('SELECT exit_code FROM pipeline_run ORDER BY started_at').fetchall()
        schema = con.execute('PRAGMA table_info(pipeline_run)').fetchall()
        strict = con.execute("SELECT strict FROM pragma_table_list WHERE name='pipeline_run'").fetchone()[0]
        con.close()
        assert len(rows)==3 and sorted(r[0] for r in rows)==[23,124,124], rows
        assert strict==1
        assert {'run_id','run_time','step','started_at','finished_at','exit_code','run_kind','detail'} <= {r[1] for r in schema}
        assert not lock.exists()
        results['concurrent_75_no_step_logged'] = True
        results['strict_required_log_columns'] = True
        try:
            connect(directory/'wrong.db')
        except Exception:
            assert not (directory/'wrong.db').exists()
        else:
            raise AssertionError('Wrong database path silently created')
        results['wrong_db_path_rejected'] = True
    print(json.dumps(results, indent=2))
    target = ROOT/'docs/evidence/m5_runner_checks.json'
    target.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    check()
