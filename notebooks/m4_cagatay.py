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

ROOT = Path.cwd()
if not (ROOT/'src/db.py').is_file():
    ROOT = ROOT.parent
if not (ROOT/'src/db.py').is_file():
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
print(json.dumps(asdict(PARAMS),indent=2))
print('Read-only database; initial table hashes:',len(before))
print('Primary period: complete source years 2022-2025; source year/week assumed ISO.')
print('Main groups: locality and year; temperature bands reserved for Egemen, no inferred county groups.')
print('Available-report summaries have no minimum coverage; comparative farm summaries require >=75% per farm-year.')
