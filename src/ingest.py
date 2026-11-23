"""Bounded, single-thread annual snapshots; missed runs cannot skip historical weeks."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

from dotenv import load_dotenv
from api_client import STATUS_COUNTS, TokenManager, make_request
from db import ROOT
from pipeline_runtime import iso_time, run_clock, parse_time

BASE = 'https://www.barentswatch.no/bwapi/v1/geodata/fishhealth'
RAW_DIR = ROOT/'data/raw'
COHORT_FILE = ROOT/'config/cohort.txt'
ENDPOINTS = {'lice':'avgfemalelice','temperature':'seatemperature','treatments':'liceTreatments'}
FIRST_YEAR = 2022
MAX_REQUESTS = 721  # Current five annual slices=601 calls; permits one new year, then fails loudly.
REQUEST_PAUSE_S = .1  # One sequential request stream; 429 Retry-After is also respected.


def rows_of(payload):
    if isinstance(payload,list):
        return payload
    if isinstance(payload,dict):
        for key in ('data','localities','items'):
            if isinstance(payload.get(key),list):
                return payload[key]
    return None


def save_raw(folder, name, content):
    path = RAW_DIR/folder/name
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=content:
            raise ValueError('Same retrieval clock has different response bytes: '+str(path))
        return False
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.part')
    try:
        with temporary.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic publish without overwrite. Interrupted writes never become .json.
        os.link(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def fetch_and_store(tokens, stats, folder, url, stem, stamp):
    stats['requests'] += 1
    response = make_request(url,tokens)
    if response is None or response.status_code!=200:
        raise RuntimeError('Retrieval failed: '+url)
    try:
        rows = rows_of(response.json())
    except ValueError as exc:
        raise ValueError('Non-JSON source response: '+url) from exc
    if rows is None or any(not isinstance(row,dict) for row in rows):
        raise ValueError('Unexpected source shape: '+url)
    if not rows and folder in ('localities','temperature'):
        raise ValueError('Unexpected empty required source: '+url)
    if folder!='localities' and any(type(row.get('week')) is not int or not 1<=row['week']<=53 for row in rows):
        raise ValueError('Missing or invalid source week: '+url)
    if folder=='localities' and any(type(row.get('localityNo')) is not int for row in rows):
        raise ValueError('Missing locality identity: '+url)
    stats['saved'] += save_raw(folder,stem+'_'+stamp+'.json',response.content)
    stats['rows'] += len(rows)
    stats['empty'] += not rows
    return len(rows)


def ingest(clock, *, state_path, no_dotenv=False):
    if not no_dotenv:
        load_dotenv(ROOT/'.env')
    cohort = [int(value) for value in COHORT_FILE.read_text().split()]
    if not cohort or len(cohort)!=len(set(cohort)):
        raise ValueError('Cohort must be nonempty and unique')
    request_count = 1+len(cohort)*len(ENDPOINTS)*(clock.year-FIRST_YEAR+1)
    if clock.year<FIRST_YEAR or request_count>MAX_REQUESTS:
        raise ValueError('Catch-up exceeds configured history/request budget; no partial fetch permitted')
    previous = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
    if previous and parse_time(previous['last_success'])>clock:
        raise ValueError('Ingest clock precedes last success; use --skip-ingest for historical rebuilds')
    print('Snapshot replay: all source years',FIRST_YEAR,'to',clock.year,
          '; requests',request_count,'; last success',previous['last_success'] if previous else 'none',flush=True)
    tokens = TokenManager()
    tokens.get()  # Fail authentication before creating any raw snapshot.
    stamp = clock.strftime('%Y%m%dT%H%M%SZ')
    stats = {kind:Counter() for kind in ('localities',*ENDPOINTS)}
    fetch_and_store(tokens,stats['localities'],'localities',BASE+'/localities','localities',stamp)
    totals = Counter()
    for index,number in enumerate(cohort,1):
        for year in range(FIRST_YEAR,clock.year+1):
            for folder,endpoint in ENDPOINTS.items():
                time.sleep(REQUEST_PAUSE_S)
                url = f'{BASE}/locality/{number}/{endpoint}/{year}'
                totals[folder] += fetch_and_store(tokens,stats[folder],folder,url,f'{number}_{year}',stamp)
        print('Retrieved',index,'/',len(cohort),'farms',flush=True)
    if any(totals[folder]==0 for folder in ('lice','temperature')):
        raise ValueError('Whole measurement feed empty; last success not advanced')
    # Empty individual lice/treatment years occur in landed data. They are explicit
    # valid annual arrays, not proof of missing HTTP responses or zero lice counts.
    state = {'last_success':iso_time(clock),'first_year':FIRST_YEAR,'last_year':clock.year,
             'mode':'full_annual_replay','requests':request_count,
             'cohort_sha256':hashlib.sha256(COHORT_FILE.read_bytes()).hexdigest(),
             'sources':{kind:dict(value) for kind,value in stats.items()}}
    state_path.parent.mkdir(parents=True,exist_ok=True)
    pending = state_path.with_suffix('.tmp')
    pending.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    pending.replace(state_path)  # Advance only after all requests succeeded.
    print('HTTP status counts:',dict(STATUS_COUNTS))
    print('INGEST_SUMMARY',json.dumps(state),flush=True)
    return state


def main():
    global RAW_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-time')
    parser.add_argument('--raw-dir',type=Path,default=RAW_DIR)
    parser.add_argument('--state',type=Path)
    parser.add_argument('--no-dotenv',action='store_true',help='Credential drill: use environment only')
    args = parser.parse_args()
    RAW_DIR = args.raw_dir
    state_path = args.state or RAW_DIR.parent/'ingest_state.json'
    try:
        ingest(run_clock(args.run_time),state_path=state_path,no_dotenv=args.no_dotenv)
    except (OSError,ValueError,RuntimeError) as exc:
        print('ERROR:',str(exc))
        raise SystemExit(1)


if __name__=='__main__':
    main()
