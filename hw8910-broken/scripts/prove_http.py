"""Save explicit HTTP A -> B -> A and validation transcript, in fresh STUB workspace."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('incident_http_tests',root/'integration_tests/test_integration.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
os.environ['SERVICE_FRAMEWORK']='fastapi'
case=module.IntegrationTests('test_http_loaded_version_restart_and_rollback')
case.setUp()
records=[]
def capture(label,path,payload=None):
    status,body=case.http(path,payload)
    records.append({'label':label,'path':path,'request':payload,'status':status,'body':body})
    return status,body
try:
    proc=case.start_service(2)
    assert capture('alive during warmup','/health')[0]==200
    assert capture('not ready during warmup','/ready')[0]==503
    assert capture('blocked during warmup','/generate',{'prompt':'hello'})[0]==503
    case.await_ready()
    assert capture('loaded A','/generate',{'prompt':'hello'})[1]['model_id']=='fixture-A'
    before=capture('before invalid','/debug')[1]['calls']
    assert capture('invalid limit','/generate',{'prompt':'hello','max_new_tokens':100000})[0]==400
    assert capture('after invalid','/debug')[1]['calls']==before
    publish=case.command('run')
    records.append({'label':'publish B','exit_code':publish.returncode,'stdout':publish.stdout,'stderr':publish.stderr})
    assert publish.returncode==0
    assert capture('B published, still A in memory','/generate',{'prompt':'hello'})[1]['model_id']=='fixture-A'
    proc.terminate();proc.wait(timeout=10)
    proc=case.start_service();case.await_ready()
    assert capture('restart loaded B','/generate',{'prompt':'hello'})[1]['model_id']=='fixture-B'
    command=[sys.executable,'-c','import lab,release;from pathlib import Path;import sys;r=Path(sys.argv[1]);release.publish_event(lab.read(r/"manifest-A.json"),lab.read(r/"report-A.json"),r)',str(case.root)]
    rollback=subprocess.run(command,cwd=root,capture_output=True,text=True)
    records.append({'label':'controlled rollback accepted A','exit_code':rollback.returncode,'stderr':rollback.stderr})
    assert rollback.returncode==0
    proc.terminate();proc.wait(timeout=10)
    case.start_service();case.await_ready()
    assert capture('restart rollback loaded A','/generate',{'prompt':'hello'})[1]['model_id']=='fixture-A'
    (root/'docs/evidence/http-lifecycle.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(records,ensure_ascii=False,indent=2))
finally:case.doCleanups()
