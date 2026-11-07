# %% [markdown]
# ## Reproducibility and decisions actually used
# The database is read-only. This footer hashes every M2/M3 table and writes the
# parameters, explicit look log and stage results outside the database.
# %%
after = snapshot_all(con)
if before != after:
    raise RuntimeError('Database contents changed during exploration')
results['database_unchanged'] = True
write_json(EVIDENCE_DIR,'m4_cagatay_results.json',results)
write_json(EVIDENCE_DIR,'m4_readonly_hashes.json',{'before':before,'after':after,'equal':before==after})
look_log.write(EVIDENCE_DIR)
print('All table hashes unchanged:',len(after))
print('Recorded configuration looks:',len(look_log.entries))
print('Parameters used:',json.dumps(asdict(PARAMS),sort_keys=True))
print('Stage complete: Cagatay source cells executed. Full M4 remains pending until Egemen and final integration.')
con.close()
