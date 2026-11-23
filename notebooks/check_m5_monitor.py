"""Prove all four independent monitor alarms on clearly labelled disposable data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect
from clean import run_clean, CLEAN_SNAPSHOT_SQL
from db import snapshot
from load import UPSERT_LICE
from monitor import monitor
from pipeline_runtime import run_clock
from run_pipeline import CREATE_LOG, INSERT_LOG, STEPS


def state(con):
    return [snapshot(con),{name:con.execute(sql).fetchall() for name,sql in CLEAN_SNAPSHOT_SQL.items()}]


def check():
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True,exist_ok=True)
    source = connect(DB_PATH,read_only=True)
    original = state(source)
    evidence = {'fixture_only':True}
    try:
        with tempfile.TemporaryDirectory(dir=base) as folder:
            directory = Path(folder)
            target = directory/'fixture.db'
            con = connect(target,create=True)
            source.backup(con)
            cohort = [int(v) for v in (ROOT/'config/cohort.txt').read_text().split()]
            with con:
                for number in cohort:
                    key = con.execute('SELECT locality_key FROM locality WHERE locality_no=?',(number,)).fetchone()[0]
                    for week in (43,44,45,46):
                        con.execute(UPSERT_LICE,(key,2026,week,.1,'2026-11-23T12:50:00Z'))
                        con.execute('UPDATE sea_temperature_weekly SET sea_temperature=?,has_reported=?,retrieved_at=? WHERE locality_key=? AND year=? AND week=?',
                                    (10.,1,'2026-11-23T12:50:00Z',key,2026,week))
            con.close()
            run_clean(target,quiet=True,run_time=run_clock('2026-11-23T12:50Z'))
            log = directory/'runs.db'
            con = connect(log,create=True)
            with con:
                con.execute(CREATE_LOG)
                for step in STEPS:
                    con.execute(INSERT_LOG,('fixture','2026-11-23T12:15:00Z',step,
                        '2026-11-23T12:15:00Z','2026-11-23T12:16:00Z',0,'scheduled','{}'))
            con.close()
            clock = run_clock('2026-11-23T12:50Z')
            rows = monitor(target,log,now=clock)
            assert all(row['status']=='PASS' for row in rows),rows
            con = connect(target,read_only=True)
            before = state(con)
            con.close()
            monitor(target,log,now=clock)
            con = connect(target,read_only=True)
            assert state(con)==before
            con.close()
            evidence['baseline_all_four_pass_and_db_unchanged'] = True
            con = connect(log)
            with con:
                con.execute('UPDATE pipeline_run SET exit_code=? WHERE step=?',(23,'src/validate.py'))
            con.close()
            rows = {r['check']:r for r in monitor(target,log,now=clock)}
            assert rows['last_success']['status']=='ALARM'
            evidence['last_success_alarm'] = rows['last_success']
            con = connect(log)
            with con:
                con.execute('UPDATE pipeline_run SET exit_code=?',(0,))
            con.close()
            rows = {r['check']:r for r in monitor(target,log,now=run_clock('2026-11-24T12:50Z'))}
            assert rows['gaps']['status']=='ALARM'
            assert len(rows['gaps']['detail']['missing_scheduled_slots'])==2
            evidence['gaps_alarm_two_slots'] = rows['gaps']
            con = connect(target)
            with con:
                con.execute('DELETE FROM sea_temperature_weekly_clean WHERE locality_key=? AND year=? AND week=?',(key,2026,43))
            con.close()
            rows = {r['check']:r for r in monitor(target,log,now=clock)}
            assert rows['completeness']['status']=='ALARM'
            evidence['completeness_alarm'] = rows['completeness']
            rows = {r['check']:r for r in monitor(target,log,now=run_clock('2026-12-28T12:50Z'))}
            assert rows['freshness']['status']=='ALARM'
            evidence['freshness_alarm'] = {'status':'ALARM','stale_entities':len(rows['freshness']['detail']['stale_entities'])}
            completed = subprocess.run([sys.executable,'-X','utf8','src/monitor.py','--db',str(target),
                        '--log-db',str(log),'--now','2026-11-23T12:50Z'],cwd=ROOT,
                        capture_output=True,text=True,encoding='utf-8',timeout=30)
            assert completed.returncode==1 and len(completed.stdout.splitlines())==4
            evidence['alarm_cli_exit_1_four_lines'] = True
        assert state(source)==original
        evidence['production_database_unchanged'] = True
    finally:
        source.close()
    (ROOT/'docs/evidence/m5_monitor_checks.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':
    check()
