# %% [markdown]
# ## 2.5 Time - weekly reporting clock, edges and calendar
# Question: how much do reporting coverage and source-week seasonality change summaries?
# Reports have year/week, not a measurement hour. UTC retrieved_at is provenance only;
# no timezone conversion is invented. ISO Monday positions are a display convention.
# The provider confirms weekly reporting but does not explicitly name ISO 8601 in the consulted pages.
# Thirteen-week source-year blocks are not Gregorian quarters.
# %%
from datetime import date
from explore_egemen import time_tables, paired_reports, correlation, within_group
egemen_results={}
time_results={}
calendar_results=[]
for threshold in PARAMS.thresholds:
    weekly,blocks=time_tables(con,PARAMS,threshold)
    time_results[str(threshold)]={'weekly':weekly,'blocks':blocks}
    print('Analytical threshold',threshold,'weekly n range',min(r['n'] for r in weekly),max(r['n'] for r in weekly),
          'shown weeks',sum(r['shown'] for r in weekly),'of',len(weekly))
    table(blocks,['year','block','n','expected','shown','share'])
    for window in PARAMS.spring_windows:
        members=[r for r in weekly if window[0]<=r['week']<=window[1]]
        n=sum(r['n'] for r in members); reaching=sum(r['reaching_threshold'] for r in members)
        print('Calendar window only, no region assigned:',window,'n',n,'reaching',reaching,'share',reaching/n)
        calendar_results.append({'threshold':threshold,'weeks':window,'n':n,'reaching':reaching,'share':reaching/n})
        look_log.add('E-CALENDAR-'+str(threshold)+'-'+str(window),
                     'What is the descriptive frequency in a documented spring calendar window?',
                     {'threshold':threshold,'weeks':window,'n':n,'flag_filter':list(PARAMS.primary_lice_flags),
                      'coverage_rule':'available reports; windows overlap in week 21; no legal regime assigned'},owner='Mehmet Egemen Karagoz')
    look_log.add('E-TIME-'+str(threshold),'Does a reporting-coverage rule hide thin weekly/block time points?',
                 {'threshold':threshold,'min_weekly_farms':PARAMS.min_time_farms,'min_block_coverage':PARAMS.min_block_coverage,
                  'flag_filter':list(PARAMS.primary_lice_flags),'weekly_shown':sum(r['shown'] for r in weekly)},owner='Mehmet Egemen Karagoz')
edge_rows=con.execute('SELECT year,MIN(week),MAX(week),COUNT(*) FROM lice_weekly_clean GROUP BY year ORDER BY year').fetchall()
print('Source lice edges by year (no filtering for this inventory):',edge_rows)
edge_details=[{'year':year,'first_week_n':next(r['n'] for r in time_results[str(PARAMS.thresholds[0])]['weekly'] if r['year']==year and r['week']==1),
               'last_week_n':next(r['n'] for r in time_results[str(PARAMS.thresholds[0])]['weekly'] if r['year']==year and r['week']==date(year,12,28).isocalendar().week),
               'cohort_farms':len(PARAMS.cohort)} for year in range(PARAMS.start_year,PARAMS.end_year+1)]
table(edge_details,['year','first_week_n','last_week_n','cohort_farms'])
egemen_results['time']={'thresholds':time_results,'source_edges':edge_rows,'edge_coverage':edge_details,'calendar_windows':calendar_results}
main_time=time_results[str(PARAMS.thresholds[0])]
fig,axes=plt.subplots(2,1,figsize=(14,8))
weekly=main_time['weekly']; blocks=main_time['blocks']
axes[0].plot([date.fromisocalendar(r['year'],r['week'],1) for r in weekly],
             [r['share'] if r['shown'] else np.nan for r in weekly],color='#237a97',linewidth=1.2)
axes[0].set(xlabel='Source ISO week [Monday display position; no hour/timezone]',ylabel='Reported share >= threshold [0-1]',ylim=(0,1))
axes[0].axhline(next(r['share'] for r in key_results if r['layer']=='clean_primary' and r['threshold']==PARAMS.thresholds[0]),
                color='#9c4524',linestyle='--',label='Pooled available-report baseline')
axes[0].legend(loc='upper right')
positions=np.arange(len(blocks))
axes[1].bar(positions,[r['share'] if r['shown'] else np.nan for r in blocks],color='#237a97')
axes[1].set_xticks(positions,[str(r['year'])+' B'+str(r['block']) for r in blocks],rotation=45,ha='right')
axes[1].set(xlabel='Source year and 13-week block [B4 includes week 53 if present]',ylabel='Reported share >= threshold [0-1]',ylim=(0,1))
for i,row in enumerate(blocks):
    axes[1].text(i,(row['share'] or 0)+.02,'n='+str(row['n']) if row['shown'] else 'thin',ha='center',fontsize=7,rotation=90)
save_figure(fig,FIGURE_DIR,'m4_egemen_time.png',
            'Reported frequency varies across weeks and longer source-year blocks',
            'Do patterns persist when reports are pooled over 13-week blocks?',
            'Threshold >= '+str(PARAMS.thresholds[0])+' lice/fish; '+period_caption+'; n='+str(sum(r['n'] for r in weekly))+' available reports. Flags: '+flag_caption+'.\n'
            'Weekly n is '+str(min(r['n'] for r in weekly))+'-'+str(max(r['n'] for r in weekly))+'; show n>='+str(PARAMS.min_time_farms)+' farms, otherwise a gap. Blocks require coverage >= '+str(PARAMS.min_block_coverage)+'.\n'
            'Block n printed above bars; no imputation; dashed line is the pooled frequency, not a legal limit.')
# %% [markdown]
# ## 2.6 Relationship - plot before computing coefficients
# Question: is contemporaneous temperature associated with the reported lice burden?
# A one-to-one weekly join requires both measurements; no absent report is imputed.
# Scatter shows observations; bin medians/IQR show robust conditional summaries, not confidence intervals.
# %%
paired_primary=paired_reports(con,PARAMS)
paired_raw=paired_reports(con,PARAMS,layer='raw')
paired_strict=paired_reports(con,PARAMS,strict=True)
x=np.asarray([r['temperature'] for r in paired_primary]); y=np.asarray([r['lice'] for r in paired_primary])
bin_edges=np.arange(np.floor(x.min()/PARAMS.relationship_bin_c)*PARAMS.relationship_bin_c,
                    np.ceil(x.max()/PARAMS.relationship_bin_c)*PARAMS.relationship_bin_c+PARAMS.relationship_bin_c/2,
                    PARAMS.relationship_bin_c)
bin_summaries=[]
for left,right in zip(bin_edges,bin_edges[1:]):
    sample=y[(x>=left)&(x<right)]
    if len(sample):
        bin_summaries.append({'left':float(left),'right':float(right),'n':len(sample),
                              'median':float(np.median(sample)),'q1':float(np.quantile(sample,.25)),'q3':float(np.quantile(sample,.75))})
fig,axes=plt.subplots(1,2,figsize=(13,7),sharex=True,sharey=True)
axes[0].scatter(x,y,s=7,alpha=.2,color='#237a97',edgecolors='none')
axes[0].set_title('All '+str(len(x))+' observed clean pairs')
for row in bin_summaries:
    centre=(row['left']+row['right'])/2
    axes[1].errorbar(centre,row['median'],yerr=[[row['median']-row['q1']],[row['q3']-row['median']]],fmt='o',color='#237a97',capsize=3)
    axes[1].text(centre,row['q3']+.12,str(row['n']),ha='center',fontsize=7,rotation=90)
axes[1].set_title('Bin median and IQR; labels are n')
for ax in axes:
    ax.set(xlabel='Sea temperature [degrees C]',ylabel='Adult female lice [lice/fish]',xlim=(bin_edges[0],bin_edges[-1]),ylim=(0,np.ceil(y.max())))
    for threshold in PARAMS.thresholds:
        ax.axhline(threshold,color='#9c4524',linestyle='--',linewidth=.8)
save_figure(fig,FIGURE_DIR,'m4_egemen_relationship.png',
            'Low lice counts dominate across observed temperatures',
            'Is the scatter compatible with a simple linear or monotone relationship?',
            'n='+str(len(paired_primary))+' paired source weeks; '+period_caption+'. Lice flags: '+flag_caption+'.\n'
            'Temperature flags: '+' + '.join(PARAMS.primary_temperature_flags)+'. Available pairs, no minimum farm-year coverage.\n'
            'Bins '+str(PARAMS.relationship_bin_c)+' C; IQR is spread, not a confidence interval. Common axes; dashed fixed lice thresholds.')
# %% [markdown]
# ### Coefficients and influence checks, after inspecting the plot
# Pearson measures a linear association; Spearman a rank/monotone association. Neither
# demonstrates causation or predicts future counts. No row-independent p-values are reported.
# Removing the top 1% is only a sensitivity diagnostic; it never modifies M3 or the primary estimate.
# %%
tail_cutoff=float(np.quantile(y,PARAMS.upper_tail_quantile))
without_tail=[r for r in paired_primary if r['lice']<=tail_cutoff]
lice_flag_by_key={(r['locality_no'],r['year'],r['week']):r['flag'] for r in primary_rows}
strict_lice_only=[r for r in paired_primary if lice_flag_by_key[(r['locality_no'],r['year'],r['week'])] in PARAMS.strict_lice_flags]
variants=[('primary clean pairs',paired_primary),('raw pairs including extreme temperature',paired_raw),
          ('strict lice and temperature flags',paired_strict),('strict lice only; broad temperature',strict_lice_only),
          ('remove upper lice tail',without_tail),('within farm-year centred',within_group(paired_primary,('locality_no','year'))),
          ('within year-week centred',within_group(paired_primary,('year','week')))]
correlations=[]
for label,members in variants:
    estimate=correlation(members,label)
    correlations.append(estimate)
    look_log.add('E-CORR-'+label,'How sensitive are temperature/lice coefficients to flags, extremes and shared structure?',
                 dict(estimate,tail_quantile=PARAMS.upper_tail_quantile,tail_cutoff=tail_cutoff,
                      primary_lice_flags=list(PARAMS.primary_lice_flags),primary_temperature_flags=list(PARAMS.primary_temperature_flags)),owner='Mehmet Egemen Karagoz')
for block in range(1,5):
    members=[r for r in paired_primary if min(3,(r['week']-1)//PARAMS.time_block_weeks)+1==block]
    estimate=correlation(members,'within source-year block '+str(block))
    correlations.append(estimate)
    look_log.add('E-CORR-BLOCK-'+str(block),'Is a pooled association also visible within season blocks?',estimate,owner='Mehmet Egemen Karagoz')
leave_one_out=[]
for number in PARAMS.cohort:
    estimate=correlation([r for r in paired_primary if r['locality_no']!=number],'exclude locality '+str(number))
    leave_one_out.append(dict(estimate,excluded_locality=number))
    look_log.add('E-CORR-EXCLUDE-'+str(number),'Can one locality explain the pooled coefficient?',estimate,owner='Mehmet Egemen Karagoz')
table(correlations,['label','n','pearson','spearman'])
print('Leave-one-farm-out coefficient ranges:',
      {metric:[min(r[metric] for r in leave_one_out),max(r[metric] for r in leave_one_out)] for metric in ('pearson','spearman')})
egemen_results['relationships']={'correlations':correlations,'leave_one_farm_out':leave_one_out,
    'tail_quantile':PARAMS.upper_tail_quantile,'tail_cutoff':tail_cutoff,'tail_removed':len(paired_primary)-len(without_tail),
    'temperature_bins':bin_summaries,'raw_pairs':len(paired_raw),'primary_pairs':len(paired_primary)}
results['egemen']=egemen_results
