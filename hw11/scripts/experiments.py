"""Real Kubernetes workloads; every attempted request retained, no retries hidden."""
import asyncio,hashlib,httpx,json,time,sys,threading,subprocess
from pathlib import Path
from cluster import *
RESULTS=ROOT/'results';RESULTS.mkdir(exist_ok=True)
client=httpx.Client(timeout=120,trust_env=False)
ports=[19100+i for i in range(4)]
def launch_clients():
 processes=[proxy(p,f'hw11-client-{i}',9000) for i,p in enumerate(ports)];time.sleep(2);return processes
def request(url,method='GET',payload=None,i=0):
 return client.post(f'http://127.0.0.1:{ports[i]}/request',json={'url':url,'method':method,'payload':payload}).json()
def schedule(seconds=120,rps=6,traffic='uniform',chunks=4,delay=.04,multiplier=1):
 items=[]
 for k in range(int(seconds*rps)):
  owner=k%4 if traffic=='uniform' else (0 if k%10<8 else (1+(k//10)%3))
  items.append({'id':f'r{k:05d}','client':owner,'offset':k/rps,'payload':{'messages':[{'role':'user','content':f'input-{k%32:02d}-'+'x'*100}],'prefix':f'prefix-{k%32:02d}','chunks':chunks,'chunk_delay':delay,'work_multiplier':multiplier}})
 return items
def begin(name,phase,items,url='http://hw11-api:8000',start=None):
 start=start or time.time()+3
 spec={'name':name,'phase':phase,'start_wall':start,'url':url,'items':items}
 (RESULTS/(name+'-schedule.json')).write_text(json.dumps(spec))
 for i,p in enumerate(ports):
  response=client.post(f'http://127.0.0.1:{p}/run',json={**spec,'items':[x for x in items if x['client']==i]});response.raise_for_status();assert response.json().get('started')==name,response.text
 print('START',name,'scheduled',len(items),'wall',start,flush=True);return spec

def collect(spec):
 name=spec['name']
 while True:
  statuses=[client.get(f'http://127.0.0.1:{p}/status/{name}').json() for p in ports]
  if all(x.get('done') for x in statuses):break
  time.sleep(1)
 rows=[]
 for p in ports:rows+=client.get(f'http://127.0.0.1:{p}/results/{name}').json()['rows']
 rows.sort(key=lambda r:r['planned_wall'])
 with (RESULTS/(name+'-requests.jsonl')).open('w') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 summary={'name':name,'phase':spec['phase'],'planned':len(spec['items']),'sent':len(rows),'outcomes':{k:sum(r['outcome']==k for r in rows) for k in ['completed','rejected','aborted','expired','error']},'start_wall':spec['start_wall'],'measured_schedule_seconds':max(x['offset'] for x in spec['items'])+ (spec['items'][1]['offset'] if len(spec['items'])>1 else 0),'last_finish_wall':max(r['send_wall']+r['total_seconds'] for r in rows)}
 (RESULTS/(name+'-summary.json')).write_text(json.dumps(summary,indent=2));print('END',summary,flush=True);return rows

def capture(stop):
 with (RESULTS/'kubernetes-timeline.jsonl').open('a') as f:
  while not stop.is_set():
   try:
    snap={'wall_time':time.time(),'pods':kub('get','pods','-o','json'),'endpoints':kub('get','endpointslices','-o','json'),'hpa':kub('get','hpa','-o','json')}
    f.write(json.dumps(snap)+'\n');f.flush()
   except Exception as e:print('snapshot error',e,flush=True)
   stop.wait(2)
def reset():
 for p in pods():
  if p['metadata'].get('deletionTimestamp'):continue
  result=request('http://'+p['status']['podIP']+':8000/admin/reset','POST',{})
  assert result['status']==200,result
if __name__=='__main__':
 processes=launch_clients();stop=threading.Event();thread=threading.Thread(target=capture,args=(stop,),daemon=True);thread.start()
 try:
  mode=sys.argv[1]
  if mode=='B':
   wait_ready()
   for policy in ['none','sticky','fixed']:
    for traffic in ['uniform','skew']:
     items=schedule(traffic=traffic)
     for rep in range(1,4):
      reset();name=f'b_{policy}_{traffic}_{rep}';url='http://'+{'none':'hw11-api','sticky':'hw11-sticky','fixed':'hw11-fixed'}[policy]+':8000'
      rows=collect(begin(name,name,items,url));time.sleep(3)
      prom=client.get('http://127.0.0.1:19090/api/v1/query',params={'query':f'{{__name__=~"hw11_(ttfc|duration|queue)_seconds_(bucket|count|sum)",phase="{name}"}}'}).json()
      (RESULTS/(name+'-prometheus.json')).write_text(json.dumps(prom))
  elif mode=='pilot':
   wait_ready();reset();collect(begin('pilot','test',schedule(20,6,'skew'),'http://hw11-sticky:8000'))
 finally:
  stop.set();thread.join(5)
  for p in processes:p.terminate()
