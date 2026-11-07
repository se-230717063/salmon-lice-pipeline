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


def regime(row,params):
    value=row['temperature']
    if params.cold_range_c[0]<=value<params.cold_range_c[1]:
        return 'cold'
    if params.warm_range_c[0]<=value<params.warm_range_c[1]:
        return 'warm'
    return None


def pooled_difference(rows,params,threshold):
    output={}
    for label in ('cold','warm'):
        values=[r['lice'] for r in rows if regime(r,params)==label]
        output['n_'+label]=len(values)
        output['share_'+label]=float(np.mean(np.asarray(values)>=threshold)) if values else None
    output['difference']=output['share_warm']-output['share_cold'] if output['n_cold'] and output['n_warm'] else None
    return output


def clustered_comparison(con,params,threshold,*,strict=False):
    rows=paired_reports(con,params,strict=strict)
    flags=params.strict_lice_flags if strict else params.primary_lice_flags
    eligible={(r['locality_no'],r['year']) for r in coverage(con,params,flags=flags,threshold=threshold)
              if r['eligible'] and r['year']<=params.end_year}
    base=[r for r in rows if (r['locality_no'],r['year']) in eligible and regime(r,params)]
    groups=defaultdict(list)
    for row in base:
        groups[(row['locality_no'],row['year'])].append(row)
    paired_years=[]
    for (number,year),members in sorted(groups.items()):
        estimate=pooled_difference(members,params,threshold)
        if min(estimate['n_cold'],estimate['n_warm'])>=params.min_regime_weeks:
            paired_years.append(dict(estimate,locality_no=number,year=year))
    by_farm=defaultdict(list)
    for estimate in paired_years:
        by_farm[estimate['locality_no']].append(estimate['difference'])
    farm_differences=[{'locality_no':number,'paired_years':len(values),'difference':float(np.mean(values))}
                      for number,values in sorted(by_farm.items())]
    differences=np.asarray([r['difference'] for r in farm_differences])
    mean=float(np.mean(differences)) if len(differences) else None
    interval=None
    if len(differences)>=2:
        rng=np.random.default_rng(params.seed)
        draws=rng.choice(differences,size=(params.bootstrap_replicates,len(differences)),replace=True).mean(axis=1)
        interval=[float(v) for v in np.quantile(draws,[.025,.975])]
    matched_keys={(r['locality_no'],r['year']) for r in paired_years}
    matched=[r for r in base if (r['locality_no'],r['year']) in matched_keys]
    by_year=[]; by_block=[]
    for year in range(params.start_year,params.end_year+1):
        by_year.append(dict(pooled_difference([r for r in matched if r['year']==year],params,threshold),year=year))
    for block in range(1,5):
        by_block.append(dict(pooled_difference([r for r in matched if min(3,(r['week']-1)//params.time_block_weeks)+1==block],params,threshold),block=block))
    week_groups=defaultdict(list); season_groups=defaultdict(list)
    for row in matched:
        week_groups[(row['year'],row['week'])].append(row)
        season_groups[(row['locality_no'],row['year'],min(3,(row['week']-1)//params.time_block_weeks)+1)].append(row)
    common_weeks=[]
    for (year,week),members in sorted(week_groups.items()):
        estimate=pooled_difference(members,params,threshold)
        if min(estimate['n_cold'],estimate['n_warm'])>=params.min_overlap_farms:
            common_weeks.append(dict(estimate,year=year,week=week))
    within_season=[]
    for (number,year,block),members in sorted(season_groups.items()):
        estimate=pooled_difference(members,params,threshold)
        if min(estimate['n_cold'],estimate['n_warm'])>=params.min_stratum_regime_weeks:
            within_season.append(dict(estimate,locality_no=number,year=year,block=block))
    return {'threshold':threshold,'filter':'strict' if strict else 'primary','qualified_farm_years':len(eligible),
        'paired_farm_years':len(paired_years),'farms':len(farm_differences),'difference':mean,'interval95':interval,
        'bootstrap_replicates':params.bootstrap_replicates,'bootstrap_unit':'farm; retain all its paired years; equal farm weight',
        'farm_years':paired_years,'farm_differences':farm_differences,
        'unmatched_pooled':pooled_difference(base,params,threshold),'matched_pooled':pooled_difference(matched,params,threshold),
        'by_year':by_year,'by_block':by_block,'same_year_week':common_weeks,'within_farm_year_block':within_season,
        'same_year_week_mean':float(np.mean([r['difference'] for r in common_weeks])) if common_weeks else None,
        'within_farm_year_block_mean':float(np.mean([r['difference'] for r in within_season])) if within_season else None}
