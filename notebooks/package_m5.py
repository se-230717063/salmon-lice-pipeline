"""Create DYS files locally; --final requires actual days, recovery and fresh-clone proof."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from db import DB_PATH, connect
from monitor import monitor
from pipeline_evidence import fingerprint, run_summary
from pipeline_runtime import iso_time, run_clock
from run_pipeline import LOG_PATH, LOCK_PATH
from validate import validate


def package(final=False):
    descriptor = os.open(LOCK_PATH,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(descriptor)
    try:
        clock = run_clock()
        checks = validate(DB_PATH,run_time=clock)
        if any(row['level']=='STOP' for row in checks):
            raise RuntimeError('Resolve validation STOPs before packaging')
        summary = run_summary(LOG_PATH)
        proof_path = ROOT/'docs/evidence/m5_fresh_clone.json'
        proof = json.loads(proof_path.read_text(encoding='utf-8')) if proof_path.exists() else {}
        fresh = (proof.get('source_fingerprint')==fingerprint() and proof.get('raw_fingerprint')==fingerprint(raw=True)
                 and proof.get('offline_runner_exit_code')==0 and proof.get('m4_notebook_exit_code')==0)
        recovered = ROOT/'docs/evidence/m5_missed_run_recovery.json'
        recovery = json.loads(recovered.read_text(encoding='utf-8')) if recovered.exists() else {}
        ready = (summary['longest_consecutive_local_days']>=7 and fresh and
                 recovery.get('status')=='real_missed_run_recovery_verified')
        if final and not ready:
            raise RuntimeError('Final package needs seven real scheduled days, verified real recovery, and fresh source/raw clone proof')
        output = ROOT/'output/m5_submission'
        output.mkdir(parents=True,exist_ok=True)
        for source_path,name in ((DB_PATH,'salmon_lice.db'),(LOG_PATH,'pipeline_log.db')):
            source = connect(source_path,read_only=True)
            target = connect(output/name,create=True)
            try:
                source.backup(target)
                assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            finally:
                source.close()
                target.close()
        with zipfile.ZipFile(output/'raw_data.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((ROOT/'data/raw').glob('*/*.json')):
                archive.write(path,path.relative_to(ROOT/'data').as_posix())
        with zipfile.ZipFile(output/'raw_data.zip') as archive:
            assert archive.testzip() is None
        repository = 'https://github.com/se-230717063/salmon-lice-pipeline'
        (output/'repository_url.txt').write_text(repository+'\n',encoding='utf-8')
        health = monitor(now=clock)
        (output/'m5_monitor.txt').write_text('\n'.join(row['status']+' '+row['check']+' '+json.dumps(row['detail']) for row in health)+'\n',encoding='utf-8')
        (output/'m5_validate.txt').write_text('\n'.join(row['level']+' '+row['id']+' '+row['detail'] for row in checks)+'\n',encoding='utf-8')
        (output/'m5_run_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        if proof:
            shutil.copyfile(proof_path,output/'m5_fresh_clone.json')
        commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        tag = subprocess.run(['git','rev-parse','--verify','refs/tags/m5^{commit}'],cwd=ROOT,capture_output=True,text=True)
        files = ['repository_url.txt','salmon_lice.db','pipeline_log.db','raw_data.zip',
                 'm5_monitor.txt','m5_validate.txt','m5_run_summary.json']
        if proof:
            files.append('m5_fresh_clone.json')
        manifest = {'milestone':'M5','packaged_at':iso_time(clock),'source_commit':commit,
                    'tag':'m5' if tag.returncode==0 and tag.stdout.strip()==commit else None,
                    'final_requested':final,'ready_for_final':ready,'fresh_clone_matches':fresh,
                    'scheduled_consecutive_local_days':summary['longest_consecutive_local_days'],
                    'real_recovery_verified':recovery.get('status')=='real_missed_run_recovery_verified',
                    'monitor_alarms':[row['check'] for row in health if row['status']=='ALARM'],
                    'validation':dict(Counter(row['level'] for row in checks)),
                    'required_uploads':['repository_url.txt','pipeline_log.db','salmon_lice.db','raw_data.zip'],
                    'sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in files}}
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        with zipfile.ZipFile(ROOT/'output/m5_submission.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name in [*files,'manifest.json']:
                archive.write(output/name,'m5_submission/'+name)
        print(json.dumps(manifest,indent=2))
        return manifest
    finally:
        LOCK_PATH.unlink()


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final',action='store_true')
    package(parser.parse_args().final)
