"""Run fresh real-artifact Prefect admission and prove pointer preservation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
workspace=root/'.real'
config=json.loads((workspace/'config.json').read_text())
config['code_revision']=hashlib.sha256((root/'lab.py').read_bytes()).hexdigest()
(workspace/'config.json').write_text(json.dumps(config,indent=2)+'\n')
records=[]
for name,extra in [('real-flow-failure',['--fail-after-prepare']),('real-flow-refusal',[])]:
    before=hashlib.sha256((workspace/'accepted.json').read_bytes()).hexdigest()
    command=[sys.executable,'flow.py','--workspace',str(workspace),'--manifest','manifest-candidate.json','--report','release-report.json',*extra]
    proc=subprocess.run(command,cwd=root,capture_output=True,text=True,env={**os.environ,'PREFECT_HOME':str(root/'.prefect')})
    after=hashlib.sha256((workspace/'accepted.json').read_bytes()).hexdigest()
    (root/'docs/evidence'/f'{name}.log').write_text('$ '+' '.join(command)+'\n'+proc.stdout+proc.stderr+f'\nEXIT_CODE={proc.returncode}\n')
    records.append({'name':name,'command':command,'exit_code':proc.returncode,'accepted_sha256_before':before,'accepted_sha256_after':after})
    assert before==after and proc.returncode!=0
(root/'docs/evidence/real-flow-experiments.json').write_text(json.dumps(records,indent=2)+'\n')
