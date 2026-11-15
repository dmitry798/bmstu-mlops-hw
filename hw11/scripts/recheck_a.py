"""Repeat both warmup configurations identically and a bounded-load healthy rollout.
Original initial experiment results remain in results/experiment-a.* unchanged.
"""
import threading,time,json
from experiments import *
processes=launch_clients();stop=threading.Event();thread=threading.Thread(target=capture,args=(stop,),daemon=True);thread.start();checks=[]
try:
 for broken in [True,False]:
  helm(brokenProbes=broken,replicas=0)
  while pods():time.sleep(1)
  helm(brokenProbes=broken,replicas=2)
  name='a-broken-proof' if broken else 'a-fixed-proof'
  rows=collect(begin(name,'a_broken' if broken else 'a_fixed',schedule(32,2)))
  checks.append({'name':name,'passed':any(r['status']==503 for r in rows) if broken else not any(r['status']==503 for r in rows) and any(r['outcome']=='completed' for r in rows),'outcomes':{x:sum(r['outcome']==x for r in rows) for x in ['completed','rejected','aborted','expired','error']}})
  wait_ready(2,'A')
 # Healthy rollout admitted load .2 req/s plus one long stream per old replica.
 long=[]
 for i,p in enumerate(pods()):
  items=schedule(1,1,chunks=64,delay=.5);items[0]['client']=i
  long.append(begin('a-healthy-long-'+str(i),'a_rollout',items,'http://'+p['status']['podIP']+':8000'))
 time.sleep(6);roll=time.time();helm(modelVersion='B')
 rows=collect(begin('a-healthy-rollout','a_rollout',schedule(65,.2)));lr=sum([collect(s) for s in long],[]);wait_ready(2,'B')
 checks.append({'name':'healthy_rollout_zero_errors','passed':all(r['outcome']=='completed' for r in rows+lr),'rollout_start_wall':roll,'planned':len(rows+lr),'http_5xx':sum((r['status'] or 0)>=500 for r in rows+lr),'incomplete':sum(not r['done'] for r in rows+lr)})
 checks.append({'name':'long_streams_cross_update','passed':all(r['send_wall']+r['ttfc_seconds']<roll<r['send_wall']+r['total_seconds'] for r in lr),'rollout_start_wall':roll})
 helm(modelVersion='A');wait_ready(2,'A')
finally:
 (RESULTS/'checks-a-repeat.json').write_text(json.dumps(checks,indent=2));stop.set();thread.join(5)
 for p in processes:p.terminate()
