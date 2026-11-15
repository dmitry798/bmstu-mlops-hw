import json,subprocess,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
K=[str(ROOT/'.tools/kubectl'),'--kubeconfig',str(ROOT/'.local/kubeconfig'),'-n','hw11']
def kub(*args,raw=False):
 out=subprocess.check_output(K+list(args),text=True);return out if raw else json.loads(out)
def helm(**values):
 cmd=[str(ROOT/'.tools/helm'),'upgrade','--install','hw11',str(ROOT/'charts/hw11'),'--kubeconfig',str(ROOT/'.local/kubeconfig'),'--namespace','hw11']
 for k,v in values.items():cmd+=['--set',f'{k}={str(v).lower() if type(v) is bool else v}']
 return subprocess.check_output(cmd,text=True)
def pods():return kub('get','pods','-l','app=hw11-api','-o','json')['items']
def ready(p):return any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[]))
def wait_ready(n=2,version=None,timeout=150):
 end=time.time()+timeout
 while time.time()<end:
  ps=[p for p in pods() if not p['metadata'].get('deletionTimestamp')]
  if len(ps)==n and all(ready(p) and (version is None or p['metadata']['labels']['model']==version) for p in ps):return ps
  time.sleep(1)
 raise TimeoutError('ready replicas')
def proxy(port,service,remote):
 return subprocess.Popen(K+['port-forward','svc/'+service,f'{port}:{remote}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
