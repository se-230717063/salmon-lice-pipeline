"""Shared read-only M4 contracts, fixed SQL and reproducible figure helpers."""
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from db import ROOT, DB_PATH, SNAPSHOT_SQL, connect
from clean import CLEAN_SNAPSHOT_SQL


@dataclass(frozen=True)
class Parameters:
    cohort: tuple
    start_year: int = 2022
    end_year: int = 2025  # Complete years for primary summaries; 2026 is coverage-only here.
    thresholds: tuple = (0.2, 0.5)  # Fixed analytical >= thresholds, not assigned legal limits.
    primary_lice_flags: tuple = ('ok', 'unusual_high', 'unusual_low')
    strict_lice_flags: tuple = ('ok',)
    primary_temperature_flags: tuple = ('ok', 'unusual_high', 'unusual_low', 'suspect_stuck', 'suspect_spike')
    strict_temperature_flags: tuple = ('ok',)
    min_coverage: float = 0.75  # Require three quarters of calendar weeks for farm-year comparisons.
    histogram_widths: tuple = (0.05, 0.1, 0.2)  # Natural lice/fish units; middle width used in group panels.
    selected_histogram_width: float = 0.1
    temperature_edges: tuple = (-5., 4., 8., 12., 16., 20., 40.)  # Contract for later E-stage inspection, not a fitted choice.
    seed: int = 42
    bootstrap_replicates: int = 2000  # Reserved for Egemen's stage; no interval computed by Cagatay.
    min_time_farms: int = 20  # Half the cohort for a weekly pooled time point.
    time_block_weeks: int = 13  # Four source-week blocks per complete ISO year.
    min_block_coverage: float = 0.5  # Descriptive block plots require half the calendar opportunities.
    spring_windows: tuple = ((16,21),(21,26))  # Calendar annotations; no farm-specific legal regime assigned.
    relationship_bin_c: float = 2.0
    upper_tail_quantile: float = 0.99  # Influence diagnostic, not data cleaning.
    cold_range_c: tuple = (4.,8.)  # Fixed half-open regimes selected before comparison results.
    warm_range_c: tuple = (12.,16.)
    min_regime_weeks: int = 6  # Require six matched reports in each regime per farm-year.
    min_overlap_farms: int = 3  # Common-week diagnostic requires three farms in each regime.


def default_parameters():
    return Parameters(cohort=tuple(int(v) for v in (ROOT/'config/cohort.txt').read_text().split()))


def connect_ro(path=DB_PATH):
    return connect(path, read_only=True)


def snapshot_all(con):
    queries = {**SNAPSHOT_SQL, **CLEAN_SNAPSHOT_SQL}
    actual = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if actual != set(queries):
        raise RuntimeError('Update the fixed hash manifest for these tables: '+str(sorted(actual.symmetric_difference(queries))))
    result = {}
    for name, sql in queries.items():
        digest, count = hashlib.sha256(), 0
        for row in con.execute(sql):
            digest.update(repr(row).encode('utf-8'))
            count += 1
        result[name] = {'rows':count,'sha256':digest.hexdigest()}
    return result


def query(con, name, parameters):
    allowed = {'m4_cagatay_key_number.sql','m4_cagatay_observations.sql','m4_cagatay_coverage.sql'}
    if name not in allowed:
        raise ValueError('Unregistered SQL file')
    sql = (ROOT/'sql/queries'/name).read_text(encoding='utf-8')
    cursor = con.execute(sql, parameters)
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns,row)) for row in cursor]


def bindings(params, flags=None, threshold=None):
    return {'cohort_json':json.dumps(params.cohort),'start_year':params.start_year,'end_year':params.end_year,
            'flags_json':json.dumps(params.primary_lice_flags if flags is None else flags),
            'threshold':params.thresholds[0] if threshold is None else threshold}


def coverage_end(con):
    stamp = con.execute('SELECT MAX(retrieved_at) FROM lice_weekly').fetchone()[0]
    retrieved = datetime.fromisoformat(stamp.replace('Z','+00:00')).date()
    # Latest complete ISO week, not the week still in progress on retrieval day.
    end = retrieved-timedelta(days=retrieved.weekday()+1)
    return retrieved, end.isocalendar()[:2]


def coverage(con, params, flags=None, threshold=None):
    retrieved, (end_year,end_week) = coverage_end(con)
    arguments = bindings(params,flags,threshold)
    arguments.update(coverage_end_year=end_year,coverage_end_week=end_week)
    grouped = {(r['locality_no'],r['year']):r for r in query(con,'m4_cagatay_coverage.sql',arguments)}
    result = []
    for number in params.cohort:
        for year in range(params.start_year,end_year+1):
            expected = end_week if year==end_year else date(year,12,28).isocalendar().week
            item = grouped.get((number,year),{'n':0,'reaching_threshold':0})
            n = item['n']
            result.append({'locality_no':number,'year':year,'n':n,'expected_weeks':expected,
                'coverage':n/expected,'eligible':n/expected>=params.min_coverage,
                'reaching_threshold':item['reaching_threshold'],
                'share':item['reaching_threshold']/n if n else None})
    return result


def group_summaries(rows, threshold):
    summaries = []
    for number in sorted({r['locality_no'] for r in rows}):
        values = np.asarray([r['value'] for r in rows if r['locality_no']==number])
        summaries.append({'locality_no':number,'n':len(values),'share':float(np.mean(values>=threshold)),
            'median':float(np.median(values)),'p95':float(np.quantile(values,.95)),
            'mean':float(np.mean(values))})
    # Competition ranks preserve ties. ID order is only presentation, not a ranking tie-break.
    for field in ('share','median','p95'):
        for row in summaries:
            row[field+'_rank'] = 1+sum(other[field]>row[field] for other in summaries)
    return sorted(summaries,key=lambda r:(r['share_rank'],r['locality_no']))


class LookLog:
    def __init__(self):
        self.entries = []

    def add(self, identifier, question, choices, owner='Cagatay Oruk'):
        if any(row['id']==identifier for row in self.entries):
            raise ValueError('Duplicate look ID: '+identifier)
        self.entries.append({'id':identifier,'owner':owner,'question':question,'choices':choices})

    def write(self, directory):
        (directory/'m4_look_log.json').write_text(json.dumps(self.entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def table(rows, columns):
    """Stable markdown output, including n and denominators supplied by callers."""
    print('| '+' | '.join(columns)+' |')
    print('| '+' | '.join('---' for _ in columns)+' |')
    for row in rows:
        print('| '+' | '.join(f'{row.get(column):.6g}' if isinstance(row.get(column),float) else str(row.get(column)) for column in columns)+' |')


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                        'axes.spines.right':False,'figure.dpi':110,'savefig.dpi':160})


def save_figure(fig, directory, filename, title, question, caption):
    fig.suptitle(title+'\n'+question,fontsize=13)
    fig.text(.02,.015,caption,fontsize=8,va='bottom',wrap=True)
    fig.tight_layout(rect=(0,.10,1,.96))
    path = directory/filename
    fig.savefig(path,metadata={'Software':'matplotlib'},facecolor='white')
    plt.close(fig)
    print('Figure:',path.name)
    return path


def write_json(directory,name,value):
    (directory/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
