"""Five independent acceptance checks invoke the live Kubernetes service."""
import threading,time,json,subprocess
from experiments import *
processes=launch_clients();stop=threading.Event();thread=threading.Thread(target=capture,args=(stop,),daemon=True);thread.start();checks=[]
def check(name,value,evidence):
 checks.append({'name':name,'passed':bool(value),'evidence':evidence});(RESULTS/'kubernetes-checks.json').write_text(json.dumps(checks,indent=2));print(checks[-1],flush=True)
try:
 wait_ready(2,'A')
 # Warmup verified against the independently saved RED and fixed repeat runs.
 red=[json.loads(x) for x in (RESULTS/'a-broken-proof-requests.jsonl').read_text().splitlines()]
 green=[json.loads(x) for x in (RESULTS/'a-fixed-proof-requests.jsonl').read_text().splitlines()]
 check('warmup_RED_GREEN',any(r['status']==503 for r in red) and any(r['outcome']=='completed' for r in green) and not any(r['status']==503 for r in green),{'red':'a-broken-proof-requests.jsonl','green':'a-fixed-proof-requests.jsonl'})
 rows=collect(begin('check-rollback','test',schedule(5,2)))
 check('loaded_version_after_rollback',all(r['model_id']=='A' and r['done'] for r in rows),{'file':'check-rollback-requests.jsonl'})
 # Congest the bounded queue; every planned request must receive a terminal state.
 reset();rows=collect(begin('check-accounting','test',schedule(8,25,'skew')))
 victim=pods()[0];name=victim['metadata']['name'];ip=victim['status']['podIP']
 spec=begin('check-force-kill','a_kill',schedule(1,1,chunks=64,delay=.5),'http://'+ip+':8000');time.sleep(6);killed=time.time()
 container_id=victim['status']['containerStatuses'][0]['containerID'].split('://')[1]
 inspect=json.loads(subprocess.check_output(['docker','exec','hw11-control-plane','crictl','inspect',container_id],text=True))
 target_pid=str(inspect['info']['pid'])
 proc=subprocess.run(['docker','exec','hw11-control-plane','kill','-KILL',target_pid],capture_output=True,text=True)
 aborted=collect(spec);wait_ready(2,'A')
 check('rejection_and_partial_stream_accounting',len(rows)==200 and any(r['outcome']=='rejected' for r in rows) and aborted[0]['status']==200 and aborted[0]['chunks']>0 and aborted[0]['outcome']=='aborted',{'rejections':sum(r['outcome']=='rejected' for r in rows),'crash_row':aborted[0],'kill_wall':killed,'exec_exit':proc.returncode,'recovery_wall':time.time()})
 ma='DIALOGUE-A-41f9';mb='DIALOGUE-B-8e21';items=schedule(1,2)
 for i,it in enumerate(items):it['payload']['messages']=[{'role':'user','content':ma if i==0 else mb}];it['payload']['session_id']='dialogue-'+str(i)
 rows=collect(begin('check-dialogues','test',items))
 check('two_dialogues_isolated',ma in rows[0]['text'] and mb not in rows[0]['text'] and mb in rows[1]['text'] and ma not in rows[1]['text'],{'file':'check-dialogues-requests.jsonl'})
 old=rows[0]['pod'];before={p['metadata']['name'] for p in pods()};old_debug=json.loads(request('http://'+next(p for p in pods() if p['metadata']['name']==old)['status']['podIP']+':8000/debug')['body'])
 kub('delete','pod',old,'--wait=false',raw=True);wait_ready(2,'A');new=next(p for p in pods() if p['metadata']['name'] not in before)
 it=schedule(1,1);it[0]['payload']['messages']=[{'role':'user','content':ma},{'role':'assistant','content':'history is external'},{'role':'user','content':'continue'}]
 row=collect(begin('check-replacement','test',it,'http://'+new['status']['podIP']+':8000'))[0];debug=json.loads(request('http://'+new['status']['podIP']+':8000/debug')['body'])
 check('replacement_same_artifact_and_dialogue',old!=row['pod'] and row['model_id']=='A' and ma in row['text'] and mb not in row['text'] and old_debug['artifact_sha256']==debug['artifact_sha256'] and debug['error'] is None,{'old_pod':old,'new_pod':row['pod'],'old_debug':old_debug,'new_debug':debug})
finally:
 stop.set();thread.join(5)
 for p in processes:p.terminate()
 assert len(checks)==5 and all(x['passed'] for x in checks),checks
