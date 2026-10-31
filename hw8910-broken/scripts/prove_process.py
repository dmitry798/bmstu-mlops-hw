"""Repeatable Prefect experiments; every command/exit/hash preserved."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

root=Path(__file__).resolve().parents[1]
workspace=root/'.experiments'/('proof-'+uuid.uuid4().hex[:8])
evidence=root/'docs/evidence'
env={**os.environ,'PREFECT_HOME':str(root/'.prefect'),'PREFECT_SERVER_ANALYTICS_ENABLED':'false'}
ledger=[]
def run(name,args,expected):
    cmd=[sys.executable,*args]
    proc=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True)
    (evidence/(name+'.log')).write_text('$ '+' '.join(cmd)+'\n'+proc.stdout+proc.stderr+f'\nEXIT_CODE={proc.returncode}\n')
    ledger.append({'name':name,'command':cmd,'exit_code':proc.returncode})
    print(name,'EXIT',proc.returncode,flush=True)
    if expected==0 and proc.returncode!=0:raise RuntimeError(proc.stderr)
    if expected!=0 and proc.returncode==0:raise RuntimeError('Expected refusal/failure')
run('process-init',['lab.py','--workspace',str(workspace),'init'],0)
base=['flow.py','--workspace',str(workspace)]
run('process-failure',base+['--fail-after-prepare'],1)
run('process-recovery',base,0)
run('process-repeat',base,0)
(workspace/'input.txt').write_text('New bytes, same path\n')
run('process-invalidation',base,0)
import hashlib
hashes=[]
for report in ['report-incomplete.json','report-A.json','report-reject.json']:
    before=hashlib.sha256((workspace/'accepted.json').read_bytes()).hexdigest()
    run('process-refusal-'+report[:-5],base+['--report',report],1)
    after=hashlib.sha256((workspace/'accepted.json').read_bytes()).hexdigest()
    hashes.append({'report':report,'before':before,'after':after,'unchanged':before==after})
    assert before==after
run('process-pointer-failure',base+['--fail-after-pointer'],1)
run('process-pointer-recovery',base,0)
assert len((workspace/'publications.jsonl').read_text().splitlines())==1
(evidence/'process-experiments.json').write_text(json.dumps({'workspace':str(workspace),'commands':ledger,'rejections':hashes,'publications':(workspace/'publications.jsonl').read_text()},ensure_ascii=False,indent=2)+'\n')
