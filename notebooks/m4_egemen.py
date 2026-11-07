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
        look_log.add('E-CALENDAR-'+str(threshold)+'-'+str(window),
                     'What is the descriptive frequency in a documented spring calendar window?',
                     {'threshold':threshold,'weeks':window,'n':n,'flag_filter':list(PARAMS.primary_lice_flags),
                      'coverage_rule':'available reports; windows overlap in week 21; no legal regime assigned'},owner='Mehmet Egemen Karagoz')
    look_log.add('E-TIME-'+str(threshold),'Does a reporting-coverage rule hide thin weekly/block time points?',
                 {'threshold':threshold,'min_weekly_farms':PARAMS.min_time_farms,'min_block_coverage':PARAMS.min_block_coverage,
                  'flag_filter':list(PARAMS.primary_lice_flags),'weekly_shown':sum(r['shown'] for r in weekly)},owner='Mehmet Egemen Karagoz')
edge_rows=con.execute('SELECT year,MIN(week),MAX(week),COUNT(*) FROM lice_weekly_clean GROUP BY year ORDER BY year').fetchall()
print('Source lice edges by year (no filtering for this inventory):',edge_rows)
egemen_results['time']={'thresholds':time_results,'source_edges':edge_rows}
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
