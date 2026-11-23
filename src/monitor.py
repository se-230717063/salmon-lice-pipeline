"""Independent read-only checks. An ALARM exits 1, even if the pipeline never ran."""
import argparse
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from db import DB_PATH, ROOT, connect
from pipeline_runtime import iso_time, parse_time, run_clock, wall_time
from run_pipeline import LOG_PATH, STEPS

LOCAL_ZONE = timezone(timedelta(hours=3))  # Turkey UTC+3 throughout the project period.
SCHEDULE_TIMES = ((15,15),(20,15))  # Actual Windows triggers; unequal 5h/19h gaps.
SCHEDULE_START = '2026-11-23T12:15:00Z'  # Installed first 15:15 local trigger, not inferred history.
MAX_SUCCESS_HOURS = 26  # Longest planned gap 19h plus 7h for startup/network trouble.
GAP_GRACE_MINUTES = 30  # Delayed starts beyond this remain visible as missed slots.
GAP_LOOKBACK_DAYS = 7  # Includes the required experiment; old gaps age out, never erased.
COMPLETENESS_WEEKS = 4  # Latest four due weekly status periods, not future placeholders.
MAX_VALUE_AGE_DAYS = 21  # Weekly period start + publication allowance + one reporting week.

COMPLETENESS_SQL = """WITH
periods AS (SELECT json_extract(value,'$[0]') AS year,json_extract(value,'$[1]') AS week FROM json_each(:periods)),
cohort AS (SELECT value AS locality_no FROM json_each(:cohort))
SELECT c.locality_no,p.year,p.week,t.has_reported,t.locality_key,
       tc.sea_temperature,lc.avg_adult_female_lice
FROM cohort c CROSS JOIN periods p
LEFT JOIN locality l ON l.locality_no=c.locality_no
LEFT JOIN sea_temperature_weekly t ON t.locality_key=l.locality_key AND t.year=p.year AND t.week=p.week
LEFT JOIN sea_temperature_weekly_clean tc ON tc.locality_key=t.locality_key AND tc.year=p.year AND tc.week=p.week
LEFT JOIN lice_weekly_clean lc ON lc.locality_key=l.locality_key AND lc.year=p.year AND lc.week=p.week
ORDER BY c.locality_no,p.year,p.week"""
FRESHNESS_SQL = """SELECT l.locality_no,t.year,t.week,t.sea_temperature,c.avg_adult_female_lice
FROM locality l JOIN sea_temperature_weekly_clean t USING(locality_key)
LEFT JOIN lice_weekly_clean c ON c.locality_key=t.locality_key AND c.year=t.year AND c.week=t.week
WHERE l.locality_no IN (SELECT value FROM json_each(?))"""


def item(name, passed, detail):
    return {'check':name,'status':'PASS' if passed else 'ALARM','detail':detail}


def due_periods(clock):
    day = clock.date()
    lag = 14 if day.weekday()<2 else 7  # Reports for last week due following Tuesday.
    monday = day-timedelta(days=day.weekday()+lag)
    return [(monday-timedelta(weeks=i)).isocalendar()[:2] for i in reversed(range(COMPLETENESS_WEEKS))]


def expected_slots(clock):
    first = parse_time(SCHEDULE_START)
    local = clock.astimezone(LOCAL_ZONE)
    start = max(first.astimezone(LOCAL_ZONE).date(),local.date()-timedelta(days=GAP_LOOKBACK_DAYS))
    result = []
    while start<=local.date():
        for hour,minute in SCHEDULE_TIMES:
            slot = datetime.combine(start,time(hour,minute),LOCAL_ZONE).astimezone(timezone.utc)
            if slot>=first and slot+timedelta(minutes=GAP_GRACE_MINUTES)<=clock:
                result.append(slot)
        start += timedelta(days=1)
    return result


def check_runs(log_path, clock):
    try:
        con = connect(log_path,read_only=True)
        try:
            rows = con.execute("SELECT run_id,run_time,step,exit_code FROM pipeline_run WHERE run_kind='scheduled' ORDER BY run_time,started_at").fetchall()
        finally:
            con.close()
        runs = defaultdict(list)
        future = []
        for identifier,stamp,step,code in rows:
            moment = parse_time(stamp)
            if moment>clock:
                future.append(identifier)
            else:
                runs[identifier].append((moment,step,code))
        successes = [group[0][0] for group in runs.values() if len(group)==len(STEPS) and
                     {r[1] for r in group}==set(STEPS) and all(r[2]==0 for r in group)]
        last = max(successes) if successes else None
        latest = max(runs.values(),key=lambda group:group[0][0]) if runs else []
        recent_failure = any(row[2]!=0 for row in latest)
        okay = last is not None and clock-last<=timedelta(hours=MAX_SUCCESS_HOURS) and not recent_failure and not future
        first_check = item('last_success',okay,{'latest_complete_scheduled':iso_time(last) if last else None,
                  'max_age_hours':MAX_SUCCESS_HOURS,'latest_attempt_has_failure':recent_failure,'future_clock_run_ids':future})
        starts = [group[0][0] for group in runs.values()]
        missing = [iso_time(slot) for slot in expected_slots(clock) if not any(
                   slot<=start<=slot+timedelta(minutes=GAP_GRACE_MINUTES) for start in starts)]
        return [first_check,item('gaps',not missing and not future,
                 {'missing_scheduled_slots':missing,'grace_minutes':GAP_GRACE_MINUTES,'lookback_days':GAP_LOOKBACK_DAYS})]
    except (OSError,ValueError,sqlite3.Error) as exc:
        return [item(name,False,{'error':str(exc)}) for name in ('last_success','gaps')]


def check_data(db_path, clock):
    cohort = [int(value) for value in (ROOT/'config/cohort.txt').read_text().split()]
    try:
        con = connect(db_path,read_only=True)
        try:
            con.execute('BEGIN')  # One consistent view for the two read-only data checks.
            periods = due_periods(clock)
            rows = con.execute(COMPLETENESS_SQL,{'periods':json.dumps(periods),'cohort':json.dumps(cohort)}).fetchall()
            missing = []
            nonreports = 0
            for number,year,week,reported,key,temperature,lice in rows:
                if key is None or (reported==1 and (temperature is None or lice is None)):
                    missing.append([number,year,week,'missing_status' if key is None else 'reported_measurement_missing'])
                elif reported==0:
                    nonreports += 1
            completeness = item('completeness',not missing,{'expected_status_cells':len(cohort)*len(periods),
                 'periods':periods,'missing_count':len(missing),'missing_examples':missing[:12],
                 'explicit_nonreports':nonreports,'rule':'40 weekly statuses; measurements required when source has_reported=1; nonreport is never zero'})
            latest = {number:{'temperature':None,'lice':None} for number in cohort}
            for number,year,week,temperature,lice in con.execute(FRESHNESS_SQL,(json.dumps(cohort),)):
                day = date.fromisocalendar(year,week,1)
                if day>clock.date():
                    continue
                for name,value in (('temperature',temperature),('lice',lice)):
                    if value is not None and (latest[number][name] is None or day>latest[number][name]):
                        latest[number][name] = day
            stale = {str(number):{name:day.isoformat() if day else None for name,day in values.items()
                      if day is None or (clock.date()-day).days>MAX_VALUE_AGE_DAYS}
                     for number,values in latest.items()}
            stale = {number:values for number,values in stale.items() if values}
            freshness = item('freshness',not stale,{'now':iso_time(clock),'max_age_days':MAX_VALUE_AGE_DAYS,
                  'stale_entities':stale,'note':'Missing stock status prevents asserting inactivity; stale measurements remain visible'})
            return [completeness,freshness]
        finally:
            con.close()
    except (OSError,ValueError,sqlite3.Error) as exc:
        return [item(name,False,{'error':str(exc)}) for name in ('completeness','freshness')]


def monitor(db_path=DB_PATH, log_path=LOG_PATH, *, now=None):
    clock = now or run_clock()
    return check_runs(log_path,clock)+check_data(db_path,clock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--now')
    parser.add_argument('--db',type=Path,default=DB_PATH)
    parser.add_argument('--log-db',type=Path,default=LOG_PATH)
    args = parser.parse_args()
    clock = run_clock(args.now)
    checks = monitor(args.db,args.log_db,now=clock)
    lines = [row['status']+' '+row['check']+' '+json.dumps(row['detail'],ensure_ascii=False) for row in checks]
    print('\n'.join(lines))
    folder = ROOT/'logs'
    folder.mkdir(exist_ok=True)
    with (folder/'monitor.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps({'now':iso_time(clock),'logged_at':wall_time(),
                                'source_db':str(args.db.resolve()),'source_log_db':str(args.log_db.resolve()),'checks':checks})+'\n')
    raise SystemExit(1 if any(row['status']=='ALARM' for row in checks) else 0)


if __name__=='__main__':
    main()
