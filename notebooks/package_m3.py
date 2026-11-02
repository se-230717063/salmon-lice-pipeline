"""Build ignored local DYS deliverables from a validated DB. Does not tag or upload."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect, snapshot
from validate import validate


def package():
    quality = validate(DB_PATH)
    if any(item['level']=='STOP' for item in quality):
        raise RuntimeError('Resolve STOP results before packaging')
    output = ROOT/'output/m3_submission'
    output.mkdir(parents=True,exist_ok=True)
    files = sorted(path for path in (ROOT/'data/raw').rglob('*') if path.is_file())
    if not any(path.suffix=='.json' for path in files):
        raise RuntimeError('Raw JSON files missing')
    with zipfile.ZipFile(output/'raw_data.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path,path.relative_to(ROOT/'data').as_posix())
    with zipfile.ZipFile(output/'raw_data.zip') as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Raw ZIP integrity failure')
    source = connect(DB_PATH,read_only=True)
    target = connect(output/'salmon_lice.db')
    try:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Packaged database integrity failure')
        m2 = snapshot(source)
    finally:
        source.close()
        target.close()
    for name in ('m3_clean_run1.txt','m3_clean_run2.txt','m3_validate.txt'):
        shutil.copyfile(ROOT/'docs/evidence'/name,output/name)
    repository = 'https://github.com/se-230717063/salmon-lice-pipeline'
    (output/'repository_url.txt').write_text(repository+'\n',encoding='utf-8')
    commit = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    artifacts = ('raw_data.zip','salmon_lice.db','m3_clean_run1.txt','m3_clean_run2.txt','m3_validate.txt','repository_url.txt')
    manifest = {'source_commit':commit,'repository':repository,
                'tag':'Not created; explicit user instruction required',
                'course_upload':'Not performed','validation':dict(Counter(item['level'] for item in quality)),
                'raw_json_files':sum(path.suffix=='.json' for path in files),
                'raw_archive_entries':len(files),'m2_snapshot':m2,
                'sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in artifacts}}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(output)
    print(json.dumps({key:manifest[key] for key in ('source_commit','validation','raw_json_files','tag')},indent=2))


if __name__=='__main__':
    package()
