import threading,time,json,subprocess
from experiments import *
processes=launch_clients();stop=threading.Event();thread=threading.Thread(target=capture,args=(stop,),daemon=True);thread.start();checks=[]
def check(name,value,detail):
 checks.append({'name':name,'passed':bool(value),'detail':detail});(RESULTS/'checks-a.json').write_text(json.dumps(checks,indent=2));print('CHECK',checks[-1],flush=True)
def scaling(n):kub('scale','deployment/hw11-api',f'--replicas={n}',raw=True)
try:
 # A RED: isolate two fresh broken-probe Pods. They become endpoints before warmup.
 scaling(0)
 while pods():time.sleep(1)
 scaling(2)
 rows=collect(begin('a-broken','a_broken',schedule(32,2)))
 cold=[r for r in rows if r['status']==503]
 check('original_readiness_is_unsafe',len(cold)>0,{'cold_responses':len(cold),'expected_red':True})
 print(helm(brokenProbes=False),flush=True)
 # new fixed Pods warm up while old warm Pods keep serving.
 rows=collect(begin('a-fixed','a_fixed',schedule(55,2)))
 wait_ready(2,'A')
 check('fixed_service_never_reaches_cold_backend',all(r['outcome']=='completed' for r in rows),{'outcomes':{x:sum(r['outcome']==x for r in rows) for x in ['completed','rejected','aborted','expired','error']}})
 # Force long requests to both old Pods; normal background uses Service.
 ps=pods();long_specs=[]
 for i,p in enumerate(ps):
  items=schedule(1,1,chunks=64,delay=.5);items[0]['client']=i
  long_specs.append(begin('a-long-'+str(i),'a_rollout',items,'http://'+p['status']['podIP']+':8000'))
 time.sleep(6) # already emitted before rollout begins
 roll_start=time.time();(RESULTS/'a-rollout-start.json').write_text(json.dumps({'wall_time':roll_start,'old_pods':[p['metadata']['name'] for p in ps]}))
 print(helm(modelVersion='B'),flush=True)
 rows=collect(begin('a-rollout','a_rollout',schedule(65,.2)))
 long_rows=sum([collect(s) for s in long_specs],[]);wait_ready(2,'B')
 check('healthy_rollout_zero_errors',all(r['outcome']=='completed' for r in rows+long_rows),{'background':len(rows),'long':len(long_rows)})
 check('preexisting_stream_crosses_rollout',all(r['send_wall']+r['ttfc_seconds']<roll_start<r['send_wall']+r['total_seconds'] for r in long_rows),{'rollout_wall':roll_start,'streams':[{'send':r['send_wall'],'first':r['send_wall']+r['ttfc_seconds'],'finish':r['send_wall']+r['total_seconds']} for r in long_rows]})
 # Return A, then deliberately block B readiness and prove A stays production.
 print(helm(modelVersion='A'),flush=True);wait_ready(2,'A')
 print(helm(modelVersion='B',neverReady=True),flush=True)
 rows=collect(begin('a-bad-b','a_bad_b',schedule(30,1)))
 bad=[p for p in pods() if p['metadata']['labels']['model']=='B']
 check('unready_B_excluded',bool(bad) and not any(ready(p) for p in bad) and all(r['model_id']=='A' and r['outcome']=='completed' for r in rows),{'bad_pods':[p['metadata']['name'] for p in bad],'observed_versions':list({r['model_id'] for r in rows})})
 print(helm(modelVersion='A'),flush=True);wait_ready(2,'A')
 rows=collect(begin('a-rollback','a_rollback',schedule(5,2)))
 check('rollback_actual_version_A',all(r['model_id']=='A' and r['outcome']=='completed' for r in rows),{'observed_versions':list({r['model_id'] for r in rows})})
 # Abrupt crash after HTTP200 and emitted chunks: retain aborted outcome.
 victim=pods()[0];ip=victim['status']['podIP'];name=victim['metadata']['name']
 spec=begin('a-kill','a_kill',schedule(1,1,chunks=64,delay=.5),'http://'+ip+':8000');time.sleep(6)
 killed=time.time();kub('exec',name,'--','/bin/sh','-c','kill -KILL 1',raw=True)
 rows=collect(spec);wait_ready(2,'A')
 check('force_kill_partial_200_is_aborted',rows[0]['status']==200 and rows[0]['chunks']>0 and rows[0]['outcome']=='aborted',{'kill_wall':killed,'row':rows[0]})
 check('same_artifact_after_process_recovery',request('http://'+ip+':8000/debug')['status']==200,{'pod':name,'recovered_wall':time.time(),'debug':request('http://'+ip+':8000/debug')})
 # Two histories with distinct markers, then replace selected worker, resend full history.
 markerA='DIALOGUE-A-41f9';markerB='DIALOGUE-B-8e21'
 items=schedule(1,2)
 for i,item in enumerate(items):item['payload']['messages']=[{'role':'user','content':markerA if i==0 else markerB}];item['payload']['session_id']='dialogue-'+str(i)
 rows=collect(begin('dialogues-before','test',items))
 check('two_dialogues_isolated',markerA in rows[0]['text'] and markerB not in rows[0]['text'] and markerB in rows[1]['text'] and markerA not in rows[1]['text'],{'markers':[markerA,markerB]})
 old=rows[0]['pod'];kub('delete','pod',old,'--wait=false',raw=True);wait_ready(2,'A')
 current=[p for p in pods() if p['metadata']['name']!=old and ready(p)];new=next((p for p in current if p['metadata']['name'] not in [x['metadata']['name'] for x in ps]),current[0])
 items=schedule(1,1);items[0]['payload']['messages']=[{'role':'user','content':markerA},{'role':'assistant','content':'remembered externally'},{'role':'user','content':'continue'}]
 row=collect(begin('dialogue-after-replacement','test',items,'http://'+new['status']['podIP']+':8000'))[0]
 debug=json.loads(request('http://'+new['status']['podIP']+':8000/debug')['body'])
 check('pod_replacement_context_and_model_recovery',markerA in row['text'] and markerB not in row['text'] and row['model_id']=='A' and old!=row['pod'] and debug['error'] is None,{'old_pod':old,'new_pod':row['pod'],'debug':debug})
finally:
 for p in pods():
  (RESULTS/(p['metadata']['name']+'.log')).write_text(kub('logs',p['metadata']['name'],raw=True))
 stop.set();thread.join(5)
 for p in processes:p.terminate()
