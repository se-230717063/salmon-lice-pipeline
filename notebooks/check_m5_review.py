"""Regression cases discovered during Cagatay's M5 review; disposable data only."""
import json
import csv
from pathlib import Path
import sys
import tempfile
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import connect, snapshot
from load import run_load
from load import SimulatedFailure
from clean import run_clean
from validate import validate, typical_added_rows, freshness_groups
from pipeline_runtime import run_clock
from run_pipeline import CREATE_LOG, INSERT_LOG


def check():
    base = ROOT/'tmp/m5'
    base.mkdir(parents=True,exist_ok=True)
    result = {}
    with tempfile.TemporaryDirectory(dir=base) as folder:
        directory = Path(folder)
        raw = directory/'raw'
        for kind in ('localities','lice','temperature','treatments'):
            (raw/kind).mkdir(parents=True)
        cohort = [int(n) for n in (ROOT/'config/cohort.txt').read_text().split()]
        stamp = '20261123T120000Z'
        mapped = {int(row['locality_no']) for row in csv.DictReader((ROOT/'data/mappings/locality_name_mapping.csv').open(encoding='utf-8'))}
        registry = [{'localityNo':n,'name':'Test','municipalityNo':'5054','municipality':'Indre Fosen'} for n in sorted(set(cohort)|mapped)]
        (raw/'localities'/('localities_'+stamp+'.json')).write_text(json.dumps(registry))
        for n in cohort:
            treatments = [{'week':47,'mechanicalRemoval':True,'mechanicalRemovalEntireLocality':False,
                           'version':1,'nonMedicinalTreatments':[{'type':'Test','numberOfCages':1},{'type':'Test','numberOfCages':2}]}] if n==cohort[0] else []
            for kind,rows in (
                ('lice',[{'week':47,'value':.1}]),
                ('temperature',[{'week':47,'seaTemperature':8,'hasReported':True}]),
                ('treatments',treatments)):
                (raw/kind/(str(n)+'_2026_'+stamp+'.json')).write_text(json.dumps(rows))
        target = directory/'fixture.db'
        run_load(target,raw_dir=raw,quiet=True)
        clock = run_clock('2026-11-23T12:00Z')
        run_clean(target,quiet=True,run_time=clock)
        checks = {r['id']:r for r in validate(target,run_time=clock,volume=0)}
        assert checks['freshness']['level']=='PASS'
        assert checks['lice_freshness']['level']=='PASS'
        assert checks['volume']['level']=='INFO'
        assert '(2026, 46)' in checks['weekly_coverage']['detail']
        result['zero_weekly_growth_info_while_both_feeds_fresh'] = True
        result['monday_coverage_respects_following_tuesday_deadline'] = True
        future_checks = {r['id']:r for r in validate(target,run_time=run_clock('2026-12-28T12:00Z'))}
        assert future_checks['freshness']['level']=='WARN' and future_checks['lice_freshness']['level']=='WARN'
        result['both_feed_freshness_uses_run_clock'] = True
        backdated = {r['id']:r for r in validate(target,run_time=run_clock('2026-11-01T12:00Z'))}
        assert backdated['impossible_values']['level']=='STOP'
        result['future_values_relative_to_run_clock_stop'] = True
        con = connect(target,read_only=True)
        before = snapshot(con)
        con.close()
        empty = directory/'empty'
        empty.mkdir()
        try:
            run_load(target,raw_dir=empty,quiet=True)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing raw sources accepted')
        con = connect(target,read_only=True)
        assert snapshot(con)==before
        con.close()
        result['missing_sources_fail_without_changing_existing_db'] = True
        log = directory/'log.db'
        con = connect(log,create=True)
        with con:
            con.execute(CREATE_LOG)
            for identifier,before_count,after_count in [('earlier',10,20),('bootstrap',0,100000),('current',10,100010)]:
                detail = json.dumps({'load':{'before':{'lice_weekly':before_count},'after':{'lice_weekly':after_count}}})
                con.execute(INSERT_LOG,(identifier,'2026-11-23T11:00:00Z','src/load.py',
                    '2026-11-23T11:00:00Z','2026-11-23T11:01:00Z',0,'scheduled',detail))
        con.close()
        assert typical_added_rows(log,'current',clock)==10
        result['volume_baseline_excludes_current_and_bootstrap'] = True
        checks = {r['id']:r for r in validate(target,run_time=clock,volume=100,typical_volume=10)}
        assert checks['volume']['level']=='WARN'
        result['tenfold_volume_warns'] = True
        declared_clock = run_clock('2026-11-23T12:00Z')
        old = declared_clock.date()-timedelta(days=40)
        groups = freshness_groups({1:old,2:declared_clock.date()},[1,2],{1:(0,'2026-11-23T12:00:00Z')},declared_clock)
        assert groups==([1],[1],[],False)
        groups = freshness_groups({1:old},[1],{1:(0,'2026-11-23T12:00:00Z')},declared_clock)
        assert groups[-1] is True
        groups = freshness_groups({1:old,2:declared_clock.date()},[1,2],{1:(0,'2026-11-01T12:00:00Z')},declared_clock)
        assert groups[2]==[1]
        result['explicit_nonreport_info_does_not_hide_whole_feed_or_old_status'] = True
        con = connect(target,read_only=True)
        original_raw = snapshot(con)
        original_clean_events = con.execute('SELECT * FROM treatment_event_clean').fetchall()
        con.close()
        correction = [{'week':47,'mechanicalRemoval':True,'mechanicalRemovalEntireLocality':False,
                       'version':2,'nonMedicinalTreatments':[{'type':'Test','numberOfCages':3}]}]
        (raw/'treatments'/(str(cohort[0])+'_2026_20261123T120100Z.json')).write_text(json.dumps(correction))
        try:
            run_load(target,raw_dir=raw,quiet=True,fail_after_rows=len(registry)+1+2*len(cohort)+1)
        except SimulatedFailure:
            pass
        else:
            raise AssertionError('Late source event failure did not fire')
        con = connect(target,read_only=True)
        assert snapshot(con)==original_raw
        assert con.execute('SELECT * FROM treatment_event_clean').fetchall()==original_clean_events
        con.close()
        result['failed_treatment_revision_restores_source_and_clean_events'] = True
        run_load(target,raw_dir=raw,quiet=True)
        run_clean(target,quiet=True,run_time=clock)
        con = connect(target,read_only=True)
        assert con.execute('SELECT COUNT(*) FROM treatment_event').fetchone()[0]==1
        assert con.execute('SELECT COUNT(*) FROM treatment_event_clean').fetchone()[0]==1
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        con.close()
        result['revised_treatment_list_removes_obsolete_keys_without_fk_failure'] = True
    (ROOT/'docs/evidence/m5_review_checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    check()
