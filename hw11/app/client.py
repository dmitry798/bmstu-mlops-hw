"""Open-loop load originates here, inside four independent Kubernetes Pods."""
import asyncio,json,time,os,uuid
import httpx
from fastapi import FastAPI
from app.core import classify
app=FastAPI();jobs={}
async def attempt(client,item,start,phase,url):
    planned=start+item['offset'];await asyncio.sleep(max(0,planned-time.time()))
    sent=time.monotonic();wall=time.time();first=None;last=None;gaps=[];parts=[];status=None;done=False;error=None;deadline=False;end={}
    rid=str(uuid.uuid4());payload={**item['payload'],'phase':phase,'request_id':rid}
    headers={}
    try:
        async with client.stream('POST',url+'/generate',json=payload,headers={'Connection':'close'}) as response:
            status=response.status_code;headers=dict(response.headers)
            if status==200:
                async for line in response.aiter_lines():
                    if not line:continue
                    value=json.loads(line);now=time.monotonic()
                    if value.get('type')=='chunk':
                        if first is None:first=now
                        if last is not None:gaps.append(now-last)
                        last=now;parts.append(value)
                    if value.get('done'):done=True;end=value
            else:await response.aread()
    except httpx.TimeoutException as exc:deadline=True;error=type(exc).__name__
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    finish=time.monotonic()
    return {'logical_id':item['id'],'request_id':rid,'attempt':1,'phase':phase,'client_pod':os.getenv('POD_NAME'),'client_ip':os.getenv('POD_IP'),'url':url,'planned_wall':planned,'send_wall':wall,'send_lag_seconds':wall-planned,'send_monotonic':sent,'first_monotonic':first,'finish_monotonic':finish,'ttfc_seconds':None if first is None else first-sent,'total_seconds':finish-sent,'inter_chunk_seconds':gaps,'status':status,'done':done,'outcome':classify(status,done,deadline),'error':error,'pod':headers.get('x-pod-name') or (parts[0]['pod'] if parts else None),'model_id':headers.get('x-model-id'),'backend_mode':headers.get('x-backend-mode','simulated'),'chunks':len(parts),'expected_chunks':payload.get('chunks',4),'queue_seconds':end.get('queue_seconds'),'server_ttfc_seconds':end.get('ttfc_seconds'),'cache_hit':parts[0].get('cache_hit') if parts else None,'context_sha256':end.get('context_sha256'),'text':parts[0].get('text') if parts else None,'payload':payload}
async def run_job(spec):
    name=spec['name'];jobs[name]={'done':False,'rows':[],'spec':spec}
    async with httpx.AsyncClient(timeout=httpx.Timeout(90),limits=httpx.Limits(max_connections=256,max_keepalive_connections=0),trust_env=False) as client:
        tasks=[asyncio.create_task(attempt(client,item,spec['start_wall'],spec['phase'],spec['url'])) for item in spec['items']]
        jobs[name]['rows']=await asyncio.gather(*tasks)
    jobs[name]['done']=True
@app.post('/run')
async def start(spec:dict):
    if spec['name'] in jobs:return {'error':'duplicate job'}
    jobs[spec['name']]={'done':False,'rows':[]};asyncio.create_task(run_job(spec));return {'started':spec['name']}
@app.get('/status/{name}')
def status(name:str):
    job=jobs.get(name);return {'exists':job is not None,'done':job['done'] if job else False}
@app.get('/results/{name}')
def results(name:str):return jobs.get(name,{})
@app.post('/request')
async def single(spec:dict):
    async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
        response=await client.request(spec.get('method','GET'),spec['url'],json=spec.get('payload'));return {'status':response.status_code,'body':response.text}
