"""Deliberately fail every M3 STOP on temporary copies; also fail late in categories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from clean import CLEAN_SNAPSHOT_SQL, SimulatedCleanFailure, run_clean
from db import DB_PATH, connect, snapshot
from validate import validate


def state(con):
    return {'m2':snapshot(con), 'clean_and_mappings':{name:con.execute(sql).fetchall() for name,sql in CLEAN_SNAPSHOT_SQL.items()}}


def checks(db_path=DB_PATH):
    source = connect(db_path,read_only=True)
    baseline = state(source)
    evidence = []
    parent = ROOT/'tmp/m3'
    parent.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            for identifier, sql, parameters in (
                ('row_counts','DELETE FROM lice_weekly_clean WHERE (locality_key,year,week)=(SELECT locality_key,year,week FROM lice_weekly_clean LIMIT 1)',()),
                ('raw_preservation',"UPDATE locality_clean SET name_raw=? WHERE locality_key=(SELECT MIN(locality_key) FROM locality_clean)",('deliberately changed raw name',)),
                ('impossible_values','UPDATE sea_temperature_weekly_clean SET sea_temperature=? WHERE (locality_key,year,week)=(SELECT locality_key,year,week FROM sea_temperature_weekly_clean WHERE sea_temperature IS NOT NULL LIMIT 1)',(1000.,)),
                ('foreign_keys','INSERT INTO lice_weekly VALUES (?, ?, ?, ?, ?)',(999999999,2024,1,.1,'2026-10-10T00:00:00Z')),
                ('strict_schema','CREATE TABLE deliberately_non_strict (value TEXT)',()),
            ):
                target = Path(directory)/(identifier+'.db')
                con = connect(target)
                source.backup(con)
                con.execute('PRAGMA foreign_keys=OFF')
                with con:
                    con.execute(sql,parameters)
                con.close()
                completed = subprocess.run([sys.executable,'-X','utf8',str(ROOT/'src/validate.py'),'--db',str(target)],capture_output=True,text=True,encoding='utf-8',cwd=ROOT)
                target_line = next((line for line in completed.stdout.splitlines() if line.startswith('STOP '+identifier+' ')),None)
                if completed.returncode!=1 or target_line is None:
                    raise RuntimeError('STOP injection failed: '+identifier+'\n'+completed.stdout+completed.stderr)
                evidence.append({'check':identifier,'result':'PASS','exit_code':completed.returncode,'observed':target_line})
            missing = subprocess.run([sys.executable,'-X','utf8',str(ROOT/'src/validate.py'),'--db',str(Path(directory)/'does_not_exist.db')],capture_output=True,text=True,encoding='utf-8',cwd=ROOT)
            if missing.returncode!=1 or not missing.stdout.startswith('STOP database_read '):
                raise RuntimeError('Missing database did not stop validation')
            evidence.append({'check':'database_read','result':'PASS','exit_code':missing.returncode,'observed':missing.stdout.strip()})

            target = Path(directory)/'late_category_failure.db'
            con = connect(target)
            source.backup(con)
            con.close()
            try:
                run_clean(target,fail_after_rows=22000,quiet=True)
            except SimulatedCleanFailure:
                pass
            else:
                raise RuntimeError('Late category failure injection did not fire')
            con = connect(target,read_only=True)
            unchanged = state(con)==baseline
            con.close()
            if not unchanged:
                raise RuntimeError('Late category failure changed prior state')
            evidence.append({'check':'late_category_atomicity','result':'PASS','detail':'Failure after 22000 writes preserves all six clean tables, four mappings and seven M2 tables'})
        if state(source)!=baseline:
            raise RuntimeError('Original database changed during validation tests')
        evidence.append({'check':'original_untouched','result':'PASS'})
        return evidence
    finally:
        source.close()


if __name__=='__main__':
    print(json.dumps(checks(),ensure_ascii=False,indent=2))
