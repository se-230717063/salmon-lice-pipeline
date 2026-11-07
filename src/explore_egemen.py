"""Read-only M4 time, association and clustered-comparison helpers. No model fitting."""
from collections import defaultdict
from datetime import date
import json

import numpy as np
from scipy import stats

from db import ROOT
from explore import bindings, query, coverage


def fixed_query(con,name,arguments):
    allowed={'m4_egemen_time.sql','m4_egemen_pairs.sql'}
    if name not in allowed:
        raise ValueError('Unregistered Egemen SQL file')
    cursor=con.execute((ROOT/'sql/queries'/name).read_text(encoding='utf-8'),arguments)
    columns=[item[0] for item in cursor.description]
    return [dict(zip(columns,row)) for row in cursor]


def paired_reports(con,params,*,layer='clean',strict=False):
    arguments=bindings(params)
    arguments.update(layer=layer,
        lice_flags_json=json.dumps(params.strict_lice_flags if strict else params.primary_lice_flags),
        temperature_flags_json=json.dumps(params.strict_temperature_flags if strict else params.primary_temperature_flags))
    return fixed_query(con,'m4_egemen_pairs.sql',arguments)


def time_tables(con,params,threshold):
    rows=fixed_query(con,'m4_egemen_time.sql',bindings(params,threshold=threshold))
    lookup={(r['year'],r['week']):r for r in rows}
    weekly=[]
    blocks=defaultdict(lambda:{'n':0,'reaching_threshold':0,'expected':0})
    for year in range(params.start_year,params.end_year+1):
        for week in range(1,date(year,12,28).isocalendar().week+1):
            row=lookup.get((year,week),{'year':year,'week':week,'n':0,'reaching_threshold':0})
            value=row['reaching_threshold']/row['n'] if row['n'] else None
            weekly.append(dict(row,share=value,shown=row['n']>=params.min_time_farms))
            block=min(3,(week-1)//params.time_block_weeks)+1
            aggregate=blocks[(year,block)]
            aggregate['n']+=row['n']
            aggregate['reaching_threshold']+=row['reaching_threshold']
            aggregate['expected']+=len(params.cohort)
    coarse=[]
    for (year,block),row in sorted(blocks.items()):
        coarse.append(dict(row,year=year,block=block,share=row['reaching_threshold']/row['n'] if row['n'] else None,
                           shown=row['n']/row['expected']>=params.min_block_coverage))
    return weekly,coarse


def correlation(rows,label):
    x=np.asarray([r['temperature'] for r in rows],dtype=float)
    y=np.asarray([r['lice'] for r in rows],dtype=float)
    if len(x)<3 or np.ptp(x)==0 or np.ptp(y)==0:
        return {'label':label,'n':len(x),'pearson':None,'spearman':None}
    return {'label':label,'n':len(x),'pearson':float(stats.pearsonr(x,y).statistic),
            'spearman':float(stats.spearmanr(x,y).statistic)}


def within_group(rows,keys):
    groups=defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    residuals=[]
    for members in groups.values():
        if len(members)<2:
            continue
        mx=np.mean([r['temperature'] for r in members]); my=np.mean([r['lice'] for r in members])
        residuals.extend(dict(r,temperature=float(r['temperature']-mx),lice=float(r['lice']-my)) for r in members)
    return residuals
