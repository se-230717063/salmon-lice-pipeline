"""Fresh M2/M3 build + real Jupyter execution + all-table/figure reproducibility proof."""
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'notebooks'))
from build_m4 import build
from db import connect
from load import run_load
from clean import run_clean
from validate import validate
from explore import connect_ro, snapshot_all


def verify():
    source = connect_ro()
    original = snapshot_all(source)
    source.close()
    base = (ROOT/'tmp/m4').resolve()
    base.relative_to(ROOT.resolve())
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as directory:
        directory = Path(directory)
        database = directory/'fresh.db'
        run_load(db_path=database,quiet=True)
        run_clean(database,quiet=True,require_categories=True)
        quality = validate(database)
        if any(r['level']=='STOP' for r in quality):
            raise RuntimeError('Fresh M3 validation STOP')
        con = connect_ro(database)
        before = snapshot_all(con)
        rejected = []
        for sql in ('UPDATE municipality SET name=name', 'UPDATE lice_weekly_clean SET avg_adult_female_lice=avg_adult_female_lice'):
            try:
                con.execute(sql)
            except Exception as exc:
                if 'readonly' not in str(exc).lower():
                    raise
                rejected.append(True)
            else:
                raise RuntimeError('Read-only connection accepted a write')
        con.close()
        target = directory/'m4_fresh.ipynb'
        build(target)
        environment = dict(os.environ,M4_DB_PATH=str(database),M4_FIGURE_DIR=str(directory/'figures'),M4_EVIDENCE_DIR=str(directory/'evidence'))
        completed = subprocess.run([sys.executable,'-m','nbconvert','--to','notebook','--execute','--inplace',str(target),
                                    '--ExecutePreprocessor.timeout=180'],cwd=ROOT,env=environment,
                                   capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
        if completed.returncode:
            raise RuntimeError('Fresh notebook execution failed:\n'+completed.stdout+completed.stderr)
        con = connect_ro(database)
        after = snapshot_all(con)
        con.close()
        if before!=after:
            raise RuntimeError('Fresh notebook modified a table')
        current = json.loads((ROOT/'docs/evidence/m4_cagatay_results.json').read_text(encoding='utf-8'))
        rebuilt = json.loads((directory/'evidence/m4_cagatay_results.json').read_text(encoding='utf-8'))
        if current!=rebuilt:
            raise RuntimeError('Fresh result payload differs from committed-workspace run')
        figure_checks = {}
        for path in sorted((directory/'figures').glob('*.png')):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            expected = ROOT/'figures'/path.name
            if not expected.is_file() or hashlib.sha256(expected.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Regenerated figure differs: '+path.name)
            figure_checks[path.name] = digest
        full_stage=(ROOT/'notebooks/m4_egemen.py').exists()
        if (full_stage and not 4<=len(figure_checks)<=8) or (not full_stage and len(figure_checks)!=3):
            raise RuntimeError('Unexpected figure count for the current stage')
        if set(figure_checks)!={path.name for path in (ROOT/'figures').glob('*.png')}:
            raise RuntimeError('Workspace contains a figure not reproduced by the notebook')
        sql_problems = []
        paths = list((ROOT/'src').glob('*.py'))+list((ROOT/'notebooks').glob('*.py'))
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('execute','executemany','executescript') and node.args and isinstance(node.args[0],(ast.JoinedStr,ast.BinOp)):
                    sql_problems.append([path.relative_to(ROOT).as_posix(),node.lineno])
        if sql_problems:
            raise RuntimeError('Formatted SQL arguments: '+str(sql_problems))
        source = connect_ro()
        unchanged_original = snapshot_all(source)==original
        source.close()
        if not unchanged_original:
            raise RuntimeError('Original database changed during verification')
        result = {'scope':'Full M4 exploration' if full_stage else 'Cagatay sections 2.1-2.4',
                  'fresh_notebook_exit_code':completed.returncode,'all_17_table_hashes_unchanged':before==after,
                  'workspace_database_unchanged':unchanged_original,'fresh_results_match':current==rebuilt,
                  'read_only_write_attempts_rejected':len(rejected),'figure_sha256':figure_checks,
                  'sql_formatted_arguments':sql_problems,'fresh_validation':quality,
                  'fresh_before':before,'fresh_after':after,
                  'versions':{name:importlib.metadata.version(name) for name in ('numpy','scipy','matplotlib','nbformat','nbclient','nbconvert','ipykernel')}}
        (ROOT/'docs/evidence/m4_cagatay_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (ROOT/'docs/evidence/m4_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return {key:result[key] for key in ('fresh_notebook_exit_code','all_17_table_hashes_unchanged','fresh_results_match','read_only_write_attempts_rejected','figure_sha256')}


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
