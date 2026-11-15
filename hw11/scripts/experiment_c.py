import threading,time,json,subprocess
from experiments import *
processes=launch_clients();stop=threading.Event();thread=threading.Thread(target=capture,args=(stop,),daemon=True);thread.start();events=[]
def state_event(kind,**data):
 event={'kind':kind,'wall_time':time.time(),**data};events.append(event);(RESULTS/'c-events.json').write_text(json.dumps(events,indent=2));print(event,flush=True)
def watch_alerts():
 with (RESULTS/'c-alert-states.jsonl').open('w') as f:
  while not stop.is_set():
   try:
    data=client.get('http://127.0.0.1:19090/api/v1/alerts').json();f.write(json.dumps({'wall_time':time.time(),'data':data})+'\n');f.flush()
   except Exception as e:print(e,flush=True)
   stop.wait(2)
def settle():
 end=time.time()+240
 while time.time()<end:
  h=kub('get','hpa','hw11-api','-o','json')
  if h['status'].get('currentReplicas')==2 and h['status'].get('desiredReplicas')==2:
   wait_ready(2);return time.time()
  time.sleep(2)
 raise TimeoutError('HPA downscale to 2')
alerts=threading.Thread(target=watch_alerts,daemon=True);alerts.start()
try:
 # Let prior B windows expire so pending is observed from a genuine inactive baseline.
 state_event('baseline_quiescence_start');time.sleep(45);state_event('baseline_quiescent')
 # Preserve metrics API evidence and exact CPU requests before enabling autoscale.
 (RESULTS/'metrics-api.json').write_text(kub('get','--raw','/apis/metrics.k8s.io/v1beta1/namespaces/hw11/pods',raw=True))
 (RESULTS/'api-resource-requests.json').write_text(json.dumps(pods()))
 kub('apply','-f',str(ROOT/'monitoring/hpa.yaml'),raw=True);wait_ready(2)
 state_event('hpa_enabled',configuration=kub('get','hpa','hw11-api','-o','json'))
 for name,traffic,url,phase in [('c-compute','uniform','http://hw11-api:8000','c_hpa'),('c-hot','skew','http://hw11-sticky:8000','c_hot')]:
  reset();before={p['metadata']['name'] for p in pods()};state_event(name+'_start',pods=list(before))
  spec=begin(name,phase,schedule(100,16,traffic,chunks=4,delay=.04,multiplier=4),url)
  # Snapshot thread records pod creation and Ready; require three truly ready while load runs.
  wait_ready(3,timeout=150);state_event(name+'_three_ready',pods=[p['metadata']['name'] for p in pods()])
  rows=collect(spec);state_event(name+'_load_stopped',wall_time=max(r['send_wall'] for r in rows),drain_finished_wall=time.time(),outcomes={x:sum(r['outcome']==x for r in rows) for x in ['completed','rejected','aborted','expired','error']})
  returned=settle();state_event(name+'_two_restored',elapsed_after_load=returned-events[-1]['wall_time'])
 # Alerts are also exercised by sustained hot queues and explicit queue rejection above.
 # A separate calibrated phase provides >=20 completed observations / 30s plus overload.
 reset();state_event('alerts_load_start')
 rows=collect(begin('c-alerts','c_alerts',schedule(65,14,'skew',chunks=4,delay=.08,multiplier=1)))
 state_event('alerts_load_stopped',wall_time=max(r['send_wall'] for r in rows),drain_finished_wall=time.time());settle();time.sleep(45);state_event('alerts_recovery_observed')
 (RESULTS/'hpa-final.json').write_text(json.dumps(kub('get','hpa','hw11-api','-o','json'),indent=2))
finally:
 stop.set();thread.join(5);alerts.join(5)
 for p in processes:p.terminate()
