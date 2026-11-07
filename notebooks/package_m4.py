"""Package validated M4 DYS deliverables locally, without tagging or uploading."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect
from explore import connect_ro, snapshot_all
from validate import validate


def package():
    validation=validate(DB_PATH)
    if any(row['level']=='STOP' for row in validation):
        raise RuntimeError('Resolve validation STOP before packaging')
    proof=json.loads((ROOT/'docs/evidence/m4_verification.json').read_text(encoding='utf-8'))
    if proof['scope']!='Full M4 exploration' or proof['fresh_notebook_exit_code']!=0 or not proof['fresh_results_match']:
        raise RuntimeError('Full M4 fresh execution proof required')
    notebook=json.loads((ROOT/'notebooks/m4_eda.ipynb').read_text(encoding='utf-8'))
    if any(c['execution_count'] is None or any(o['output_type']=='error' for o in c['outputs']) for c in notebook['cells'] if c['cell_type']=='code'):
        raise RuntimeError('Execute every notebook cell successfully before packaging')
    for name,digest in proof['figure_sha256'].items():
        if hashlib.sha256((ROOT/'figures'/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Figure changed since verification: '+name)
    source=connect_ro()
    if snapshot_all(source)!=proof['fresh_after']:
        source.close()
        raise RuntimeError('Database differs from verified build')
    output=ROOT/'output/m4_submission'
    output.mkdir(parents=True,exist_ok=True)
    target=connect(output/'salmon_lice.db')
    try:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Packaged DB integrity failed')
    finally:
        source.close(); target.close()
    raw_files=sorted(p for p in (ROOT/'data/raw').rglob('*') if p.is_file())
    if not any(p.suffix=='.json' for p in raw_files):
        raise RuntimeError('Landed raw JSON files missing')
    with zipfile.ZipFile(output/'raw_data.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in raw_files:
            archive.write(path,path.relative_to(ROOT/'data').as_posix())
    with zipfile.ZipFile(output/'raw_data.zip') as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Packaged raw ZIP integrity failed')
    repository='https://github.com/se-230717063/salmon-lice-pipeline'
    (output/'repository_url.txt').write_text(repository+'\n',encoding='utf-8')
    (output/'m4_validate.txt').write_text('\n'.join(r['level']+' '+r['id']+' '+r['detail'] for r in validation)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'docs/evidence/m4_verification.json',output/'m4_verification.json')
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    tagged=subprocess.run(['git','rev-parse','--verify','refs/tags/m4^{commit}'],cwd=ROOT,capture_output=True,text=True)
    submission_tag='m4' if tagged.returncode==0 and tagged.stdout.strip()==commit else None
    names=('salmon_lice.db','raw_data.zip','repository_url.txt','m4_validate.txt','m4_verification.json')
    manifest={'milestone':'M4','source_commit':commit,'repository':repository,'tag':submission_tag,
              'required_uploads':['repository_url.txt','salmon_lice.db','raw_data.zip'],
              'validation':dict(Counter(r['level'] for r in validation)),
              'raw_json_files':sum(p.suffix=='.json' for p in raw_files),'figure_count':len(proof['figure_sha256']),
              'sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in names}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(output)
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    package()
