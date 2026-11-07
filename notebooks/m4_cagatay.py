# %% [markdown]
# # M4 exploration - Cagatay stage
# Question: how often do reported cohort weeks reach fixed adult-female lice thresholds,
# and how much do the answer and farm rankings depend on coverage, summaries and flags?
# This stage covers M4 sections 2.1-2.4. Egemen's time, relationship and interval analyses
# are pending. Fixed 0.2/0.5 thresholds are analytical, not farm-specific legal limits.
# %%
from pathlib import Path
from dataclasses import asdict
import json
import os
import sys

ROOT = next((p for p in (Path.cwd(),*Path.cwd().parents) if (p/'src/db.py').is_file()),None)
if ROOT is None:
    raise RuntimeError('Start from the repository root or notebooks directory')
sys.path.insert(0,str(ROOT/'src'))
from explore import (Parameters, connect_ro, snapshot_all, query, bindings, coverage,
                     group_summaries, LookLog, table, style, save_figure, write_json)
import numpy as np
import matplotlib.pyplot as plt

# All analysis choices live here. Paths can be overridden for disposable verification.
PARAMS = Parameters(
    cohort=tuple(int(v) for v in (ROOT/'config/cohort.txt').read_text().split()),
    start_year=2022, end_year=2025, thresholds=(0.2,0.5),
    primary_lice_flags=('ok','unusual_high','unusual_low'), strict_lice_flags=('ok',),
    primary_temperature_flags=('ok','unusual_high','unusual_low','suspect_stuck','suspect_spike'),
    strict_temperature_flags=('ok',), min_coverage=0.75,
    histogram_widths=(0.05,0.1,0.2), selected_histogram_width=0.1,
    temperature_edges=(-5.,4.,8.,12.,16.,20.,40.), seed=42, bootstrap_replicates=2000,
)
DB_PATH = Path(os.environ.get('M4_DB_PATH',str(ROOT/'data/salmon_lice.db')))
FIGURE_DIR = Path(os.environ.get('M4_FIGURE_DIR',str(ROOT/'figures')))
EVIDENCE_DIR = Path(os.environ.get('M4_EVIDENCE_DIR',str(ROOT/'docs/evidence')))
FIGURE_DIR.mkdir(parents=True,exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True,exist_ok=True)
np.random.seed(PARAMS.seed)
style()
con = connect_ro(DB_PATH)
before = snapshot_all(con)
look_log = LookLog()
results = {'parameters':asdict(PARAMS),'scope':'Cagatay sections 2.1-2.4; Egemen sections pending'}
flag_caption = ' + '.join(PARAMS.primary_lice_flags)
period_caption = str(PARAMS.start_year)+'-'+str(PARAMS.end_year)
threshold_caption = ' and '.join(str(t) for t in PARAMS.thresholds)
coverage_label = f'{100*PARAMS.min_coverage:g}%'
print(json.dumps(asdict(PARAMS),indent=2))
print('Read-only database; initial table hashes:',len(before))
print('Primary period: complete source years 2022-2025; source year/week assumed ISO.')
print('Main groups: locality and year; temperature bands reserved for Egemen, no inferred county groups.')
print('Available-report summaries have no minimum coverage; comparative farm summaries require >=75% per farm-year.')
# %% [markdown]
# ## 2.1 Raw versus cleaned: the same question and explicit denominators
# What share of reported cohort weeks reaches each fixed analytical threshold?
# Primary filters retain unusual lice values: they can be real infestations.
# Raw-matched-strict uses raw values on the exact keys accepted by the strict clean filter,
# separating a filter/population change from a numeric cleaning change.
# Available reports are the denominator; absent weeks are not zero-valued observations.
# %%
key_results = []
print((ROOT/'sql/queries/m4_cagatay_key_number.sql').read_text(encoding='utf-8'))
for threshold in PARAMS.thresholds:
    for label, layer, flags in (
        ('raw','raw',PARAMS.primary_lice_flags),
        ('clean_primary','clean',PARAMS.primary_lice_flags),
        ('clean_strict','clean',PARAMS.strict_lice_flags),
        ('raw_matched_strict','raw_matched',PARAMS.strict_lice_flags),
    ):
        arguments = dict(bindings(PARAMS,flags,threshold),layer=layer)
        estimate = query(con,'m4_cagatay_key_number.sql',arguments)[0]
        key_results.append(dict(estimate,threshold=threshold,layer=label,
                               flags='none (M2)' if label=='raw' else ','.join(flags)))
        look_log.add('C-KEY-'+str(threshold)+'-'+label,
                     'Share of available reports reaching the analytical threshold',
                     {'layer':label,'threshold':threshold,'flags':list(flags) if label!='raw' else [],
                      'period':[PARAMS.start_year,PARAMS.end_year],'n':estimate['n'],'coverage_rule':'available reports; no minimum'})
table(key_results,['threshold','layer','flags','n','reaching_threshold','share','mean_lice'])
results['key_numbers'] = key_results
# %% [markdown]
# ## 2.2 Which summary answers which question?
# Share >= threshold answers frequency among reports. The median answers the typical reported
# lice burden; p95 answers upper-tail burden. These need not rank farms alike.
# Primary comparative rankings require >=75% calendar reporting coverage in each included farm-year.
# Farm-years failing coverage remain visible in the unrestricted sensitivity table, not deleted from DB.
# %%
primary_rows = query(con,'m4_cagatay_observations.sql',bindings(PARAMS))
rank_results = {}
for threshold in PARAMS.thresholds:
    grid = coverage(con,PARAMS,threshold=threshold)
    eligible_keys = {(r['locality_no'],r['year']) for r in grid if r['eligible'] and r['year']<=PARAMS.end_year}
    qualified_rows = [r for r in primary_rows if (r['locality_no'],r['year']) in eligible_keys]
    qualified = group_summaries(qualified_rows,threshold)
    unrestricted = group_summaries(primary_rows,threshold)
    differences = sum(r['share_rank']!=r['median_rank'] for r in qualified)
    rank_results[str(threshold)] = {'qualified':qualified,'unrestricted':unrestricted,
        'qualified_n':len(qualified_rows),'qualified_farm_years':len(eligible_keys),
        'different_share_median_ranks':differences}
    print('Threshold',threshold,'qualified farm-year coverage >=',PARAMS.min_coverage)
    table(qualified,['locality_no','n','share','median','p95','share_rank','median_rank','p95_rank'])
    print('Available-report sensitivity, no minimum farm-year coverage:')
    table(unrestricted,['locality_no','n','share','median','p95','share_rank','median_rank','p95_rank'])
    print('Different share-versus-median competition ranks:',differences,'of',len(qualified))
    look_log.add('C-RANK-'+str(threshold),'Do frequency, typical burden and upper-tail burden rank farms alike?',
                 {'threshold':threshold,'summaries':['share','median','p95'],'min_farm_year_coverage':PARAMS.min_coverage,
                  'n':len(qualified_rows),'farms':len(qualified),'alternative_no_coverage_n':len(primary_rows),
                  'flag_filter':list(PARAMS.primary_lice_flags)})
results['rankings'] = rank_results
# %% [markdown]
# ## 2.3 Shape: histogram widths and an ECDF answer different questions
# Histograms show local concentration but depend on bin width. ECDFs show all empirical
# cumulative mass without bins. All available, primary-filter reports in 2022-2025 are used;
# no minimum coverage is imposed for these descriptive shapes. Group panels are years,
# while all 40 farm distributions are summarised numerically above.
# %%
values = np.asarray([row['value'] for row in primary_rows])
shape_summary = {'n':len(values),'min':float(values.min()),'median':float(np.median(values)),
                 'mean':float(values.mean()),'p95':float(np.quantile(values,.95)),
                 'max':float(values.max()),'zeros':int(np.sum(values==0))}
results['shape'] = shape_summary
print('Shape:',shape_summary)
fig = plt.figure(figsize=(12,8))
layout = fig.add_gridspec(2,3)
hist_axes = []
common_right = float(np.ceil((values.max()+max(PARAMS.histogram_widths))/max(PARAMS.histogram_widths))*max(PARAMS.histogram_widths))
common_peak = max(int(np.histogram(values,bins=np.arange(0,common_right+width/2,width))[0].max()) for width in PARAMS.histogram_widths)
for index,width in enumerate(PARAMS.histogram_widths):
    ax = fig.add_subplot(layout[0,index],sharey=hist_axes[0] if hist_axes else None)
    hist_axes.append(ax)
    edges = np.arange(0,common_right+width/2,width)
    ax.hist(values,bins=edges,color='#237a97',edgecolor='white',linewidth=.3)
    ax.set(title='Bin width '+str(width)+' lice/fish',xlabel='Adult female lice [lice/fish]',ylabel='Reported weeks [count]')
    ax.set_xlim(0,common_right); ax.set_ylim(0,common_peak*1.08)
    for threshold in PARAMS.thresholds:
        ax.axvline(threshold,color='#9c4524',linestyle='--',linewidth=1)
    look_log.add('C-HIST-'+str(width),'Does histogram bin width change the apparent lice-count shape?',
                 {'width_lice_per_fish':width,'n':len(values),'flag_filter':list(PARAMS.primary_lice_flags),'coverage_rule':'available reports; no minimum'})
ax = fig.add_subplot(layout[1,:])
ordered = np.sort(values)
ax.step(ordered,np.arange(1,len(ordered)+1)/len(ordered),where='post',color='#237a97')
ax.set(xlabel='Adult female lice [lice/fish]',ylabel='Cumulative reported share [0-1]',xlim=(0,common_right),ylim=(0,1))
for threshold in PARAMS.thresholds:
    ax.axvline(threshold,color='#9c4524',linestyle='--',label='Analytical >= '+str(threshold))
ax.legend(loc='lower right')
save_figure(fig,FIGURE_DIR,'m4_cagatay_shape_overall.png',
            'Typical reports lie below the long upper tail',
            'How do bin choices and a bin-free ECDF describe reported lice counts?',
            'n='+str(len(values))+' reports; source year/week '+period_caption+'. Flags: '+flag_caption+'.\n'
            'Available-report denominator; no minimum coverage. Dashed lines: fixed analytical '+threshold_caption+' lice/fish; not legal limits.')
# %% [markdown]
# ### Are the yearly distributions interchangeable?
# Same axes and bin widths across years prevent scale-driven visual differences.
# Histogram bar heights are fractions of that year's n, and every ECDF uses its own n.
# %%
years = list(range(PARAMS.start_year,PARAMS.end_year+1))
fig, axes = plt.subplots(2,len(years),figsize=(14,8),sharex=True,sharey='row',squeeze=False)
width = PARAMS.selected_histogram_width
edges = np.arange(0,common_right+width/2,width)
year_shapes = []
year_peak = 0.
for column,year in enumerate(years):
    yearly = np.asarray([row['value'] for row in primary_rows if row['year']==year])
    if not len(yearly):
        for ax in axes[:,column]:
            ax.text(.5,.5,'No reports',transform=ax.transAxes,ha='center')
        continue
    year_shapes.append({'year':year,'n':len(yearly),'median':float(np.median(yearly)),'p95':float(np.quantile(yearly,.95))})
    year_peak = max(year_peak,float(np.histogram(yearly,bins=edges)[0].max()/len(yearly)))
    axes[0,column].hist(yearly,bins=edges,weights=np.ones(len(yearly))/len(yearly),color='#237a97',edgecolor='white',linewidth=.3)
    axes[0,column].set(title=str(year)+'; n='+str(len(yearly)),ylabel='Reported share/bin [0-1]',ylim=(0,None))
    axes[1,column].step(np.sort(yearly),np.arange(1,len(yearly)+1)/len(yearly),where='post',color='#237a97')
    axes[1,column].set(ylabel='Cumulative share [0-1]',ylim=(0,1))
    for ax in axes[:,column]:
        ax.set_xlabel('Adult female lice [lice/fish]')
        ax.set_xlim(0,common_right)
        for threshold in PARAMS.thresholds:
            ax.axvline(threshold,color='#9c4524',linestyle='--',linewidth=.8)
    look_log.add('C-SHAPE-YEAR-'+str(year),'How does the annual lice-count distribution differ?',
                 {'year':year,'n':len(yearly),'histogram_width':width,'flag_filter':list(PARAMS.primary_lice_flags),'coverage_rule':'available reports; no minimum'})
table(year_shapes,['year','n','median','p95'])
for ax in axes[0,:]:
    ax.set_ylim(0,year_peak*1.08)
results['year_shapes'] = year_shapes
save_figure(fig,FIGURE_DIR,'m4_cagatay_shape_years.png',
            'Yearly distributions retain low typical counts and an upper tail',
            'Do common-bin histograms and ECDFs tell the same story in each year?',
            'n by year is printed in each panel; source year/week '+period_caption+'. Flags: '+flag_caption+'.\n'
            'Available reports; no minimum coverage. Shared scales; width='+str(width)+' lice/fish; dashed analytical thresholds '+threshold_caption+'.')
# %% [markdown]
# ## 2.4 Coverage, denominator and flag sensitivity
# How many calendar reporting opportunities contribute to each farm-year estimate?
# Calendar opportunities are not evidence that fish were present or reporting was required.
# 2026 coverage ends at the last completed week at retrieval and is not pooled with full years.
# At least 75% coverage supports the comparative ranking; lower-coverage data remain visible.
# %%
coverage_grid = coverage(con,PARAMS)
table(coverage_grid,['locality_no','year','n','expected_weeks','coverage','eligible'])
year_coverage = []
for year in sorted({row['year'] for row in coverage_grid}):
    rows = [r for r in coverage_grid if r['year']==year]
    year_coverage.append({'year':year,'n':sum(r['n'] for r in rows),'calendar_opportunities':sum(r['expected_weeks'] for r in rows),
                          'qualified_farm_years':sum(r['eligible'] for r in rows),'farms':len(rows)})
table(year_coverage,['year','n','calendar_opportunities','qualified_farm_years','farms'])
sensitivity = []
for threshold in PARAMS.thresholds:
    grid = coverage(con,PARAMS,threshold=threshold)
    for label,selected in (
        ('available_reports',[r for r in grid if r['year']<=PARAMS.end_year]),
        (f'coverage_at_least_{100*PARAMS.min_coverage:g}pct',[r for r in grid if r['year']<=PARAMS.end_year and r['eligible']]),
    ):
        n = sum(r['n'] for r in selected)
        exceedances = sum(r['reaching_threshold'] for r in selected)
        sensitivity.append({'threshold':threshold,'rule':label,'farm_years':len(selected),'n':n,
                            'reaching_threshold':exceedances,'share':exceedances/n if n else None})
    look_log.add('C-COVERAGE-'+str(threshold),'Does the minimum farm-year reporting rule change the pooled share?',
                 {'threshold':threshold,'rules':['available_reports','>='+coverage_label+' calendar weeks'],'flag_filter':list(PARAMS.primary_lice_flags)})
table(sensitivity,['threshold','rule','farm_years','n','reaching_threshold','share'])
results['coverage'] = {'grid':coverage_grid,'per_year':year_coverage,'sensitivity':sensitivity}
coverage_years = sorted({row['year'] for row in coverage_grid})
matrix = np.asarray([[next(r['coverage'] for r in coverage_grid if r['locality_no']==number and r['year']==year)
                      for year in coverage_years] for number in PARAMS.cohort])
fig, ax = plt.subplots(figsize=(10,15))
image = ax.imshow(matrix,aspect='auto',cmap='Blues',vmin=0,vmax=1)
ax.set_xticks(range(len(coverage_years)),[str(y) for y in coverage_years])
ax.set_yticks(range(len(PARAMS.cohort)),[str(n) for n in PARAMS.cohort])
ax.set(xlabel='Source ISO year [2026: last completed week only]',ylabel='Locality [source ID]')
for i,number in enumerate(PARAMS.cohort):
    for j,year in enumerate(coverage_years):
        row = next(r for r in coverage_grid if r['locality_no']==number and r['year']==year)
        ax.text(j,i,str(row['n'])+'/'+str(row['expected_weeks']),ha='center',va='center',fontsize=7,
                color='white' if row['coverage']>.65 else '#102c39')
colorbar = fig.colorbar(image,ax=ax,label='Calendar reporting coverage [fraction]')
colorbar.ax.axhline(PARAMS.min_coverage,color='#9c4524',linewidth=2)
complete_grid = [r for r in coverage_grid if r['year']<=PARAMS.end_year]
qualified_count = sum(r['eligible'] for r in complete_grid)
save_figure(fig,FIGURE_DIR,'m4_cagatay_coverage.png',
            str(qualified_count)+' of '+str(len(complete_grid))+' complete farm-years meet the '+coverage_label+' rule',
            'Which locality/year summaries have sufficient calendar reporting coverage?',
            'Each cell shows n/expected calendar weeks; total n='+str(sum(r['n'] for r in coverage_grid))+'. Flags: '+flag_caption+'.\n'
            'Source ISO weeks; 2026 ends at week '+str(coverage_grid[-1]['expected_weeks'])+'. Calendar opportunities do not imply active production.\n'
            'Colour scale 0-1; brown reference mark is the >='+coverage_label+' comparative coverage rule. No interpolation or imputation.')
