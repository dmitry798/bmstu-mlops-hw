"""HW8–10 backend contract continued with observable CPU streaming simulation."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,Response,StreamingResponse
from prometheus_client import CollectorRegistry,Counter,Gauge,Histogram,generate_latest
from app.core import Admission,Rejected,PrefixCache,cpu_burn,validate_payload

# Reuse the previous homework's actual artifact verification and loaded-state contract.
PREVIOUS=Path(os.getenv('HW8910_SOURCE',str(Path(__file__).resolve().parents[2]/'hw8910-broken')))
sys.path.insert(0,str(PREVIOUS))
from service_core import StubBackend,ServiceState
import release

BUCKETS=(.01,.025,.05,.1,.2,.3,.5,.8,1.2,2,3,5,8,12,20,40)
PHASES={'other','a_broken','a_fixed','a_rollout','a_bad_b','a_rollback','a_kill','c_hpa','c_hot','c_alerts','test'}|{f'b_{p}_{t}_{r}' for p in ['none','sticky','fixed'] for t in ['uniform','skew'] for r in range(1,4)}

class SimulatedBackend(StubBackend):
    label='simulated'
    def __init__(self,manifest):
        super().__init__(manifest)
        self.cache=PrefixCache(int(os.getenv('CACHE_CAPACITY','8')))
    def warmup(self):pass

def event(kind,**data):
    print(json.dumps({'event':kind,'wall_time':time.time(),'pod':os.getenv('POD_NAME','local'),'backend_mode':'simulated',**data},ensure_ascii=False),flush=True)

def create_app():
    registry=CollectorRegistry();labels=['phase','model_id']
    requests=Counter('hw11_requests_total','Terminal request outcomes',labels+['outcome'],registry=registry)
    accepted=Counter('hw11_admitted_total','Accepted requests',labels,registry=registry)
    cold=Counter('hw11_cold_requests_total','Requests delivered to a cold process',registry=registry)
    queue=Histogram('hw11_queue_seconds','Queue duration of completed streams',labels,buckets=BUCKETS,registry=registry)
    ttfc=Histogram('hw11_ttfc_seconds','Time to first response chunk, completed only',labels,buckets=BUCKETS,registry=registry)
    duration=Histogram('hw11_duration_seconds','Completed stream duration',labels,buckets=BUCKETS,registry=registry)
    running=Gauge('hw11_running','Currently computing requests',registry=registry)
    waiting=Gauge('hw11_waiting','Requests waiting for admission',registry=registry)
    readiness=Gauge('hw11_backend_ready','Actual backend warmup complete',registry=registry)
    hits=Counter('hw11_prefix_cache_total','Explicitly simulated local prefix cache', ['result'],registry=registry)
    state_holder={};gate=Admission(int(os.getenv('MAX_RUNNING','1')),int(os.getenv('MAX_WAITING','6')))
    @asynccontextmanager
    async def lifespan(app):
        state_holder['state']=ServiceState(Path(os.getenv('MODEL_ROOT','/models')),float(os.getenv('WARMUP_SECONDS','20')),SimulatedBackend)
        state_holder['draining']=False
        event('startup',warmup_seconds=os.getenv('WARMUP_SECONDS','20'))
        yield
    app=FastAPI(lifespan=lifespan)
    def state():return state_holder['state']
    def metadata(request_id=None):
        st=state();m=st.manifest
        return {'backend_mode':'simulated','pod':os.getenv('POD_NAME','local'),'model_id':m['model_id'],'artifact_sha256':m['model_sha256'],'runtime_sha256':m['runtime_sha256'],'request_id':request_id}
    @app.get('/health')
    def health():return {'alive':True,'backend_mode':'simulated'}
    @app.get('/startup')
    @app.get('/ready')
    def ready():
        value=state().ready and not state_holder['draining'] and not os.getenv('NEVER_READY','').lower()=='true'
        readiness.set(int(state().ready))
        return JSONResponse({**metadata(),'ready':value,'error':state().error},status_code=200 if value else 503)
    @app.get('/metrics')
    def metrics():
        running.set(gate.running);waiting.set(gate.waiting);readiness.set(int(state().ready))
        return Response(generate_latest(registry),media_type='text/plain; version=0.0.4')
    @app.get('/debug')
    def debug():return {**metadata(),**state().debug(),'running':gate.running,'waiting':gate.waiting,'cache_entries':len(state().backend.cache.entries) if state().backend else 0,'draining':state_holder['draining']}
    @app.post('/admin/reset')
    def reset():
        if gate.running or gate.waiting:return JSONResponse({'error':'active requests'},status_code=409)
        state().backend.cache.clear();return {'reset':True,**metadata()}
    @app.get('/drain')
    async def drain():
        state_holder['draining']=True;event('drain_start',running=gate.running,waiting=gate.waiting,**metadata())
        await asyncio.sleep(float(os.getenv('DRAIN_SECONDS','5')))
        return {'draining':True}
    @app.post('/generate')
    async def generate(request:Request):
        try:
            payload=validate_payload(await request.json())
        except (ValueError,TypeError) as exc:return JSONResponse({'error':str(exc),'backend_mode':'simulated'},status_code=400)
        phase=payload['phase'] if payload['phase'] in PHASES else 'other'
        request_id=payload['request_id'];meta=metadata(request_id);key=(phase,meta['model_id'])
        started=time.monotonic();peer=request.client.host
        event('request_received',**meta,phase=phase,session_id=payload['session_id'],peer_ip=peer,warmup_finished=state().ready)
        if not state().ready:
            cold.inc();requests.labels(*key,'rejected').inc()
            event('cold_backend_received',**meta,phase=phase,peer_ip=peer)
            return JSONResponse({**meta,'error':'warming','warmup_finished':False},status_code=503,headers={'X-Request-ID':request_id,'X-Pod-Name':meta['pod'],'X-Model-ID':meta['model_id'],'X-Backend-Mode':'simulated'})
        try:
            acquire=asyncio.create_task(gate.acquire())
            # Let the wait gauge reflect actual queued requests, not just completed waits.
            await asyncio.sleep(0);running.set(gate.running);waiting.set(gate.waiting)
            await acquire
        except Rejected:
            requests.labels(*key,'rejected').inc();event('request_rejected',**meta,phase=phase,peer_ip=peer)
            return JSONResponse({**meta,'error':'queue_full'},status_code=429,headers={'X-Request-ID':request_id,'X-Pod-Name':meta['pod'],'X-Model-ID':meta['model_id'],'X-Backend-Mode':'simulated'})
        except asyncio.CancelledError:
            acquire.cancel();raise
        queued=time.monotonic()-started;accepted.labels(*key).inc();running.set(gate.running);waiting.set(gate.waiting)
        async def stream():
            finished=False;first=None;parts=0;result='aborted'
            try:
                backend=state().backend;backend.calls+=1
                # Cost cache only: never stores user responses or conversation state.
                prefix=str(payload.get('prefix',payload['messages'][-1]['content'][:40]))
                hit=backend.cache.lookup(hashlib.sha256(prefix.encode()).hexdigest());hits.labels('hit' if hit else 'miss').inc()
                cpu=float(os.getenv('CACHE_HIT_CPU','0.015') if hit else os.getenv('CACHE_MISS_CPU','0.14'))
                await asyncio.to_thread(cpu_burn,cpu*payload['work_multiplier'])
                context=json.dumps(payload['messages'],ensure_ascii=False,sort_keys=True)
                context_hash=hashlib.sha256(context.encode()).hexdigest()
                answer='SIMULATED: '+context
                for index in range(payload['chunks']):
                    if await request.is_disconnected():break
                    await asyncio.to_thread(cpu_burn,float(os.getenv('CHUNK_CPU','0.01'))*payload['work_multiplier'])
                    await asyncio.sleep(payload['chunk_delay'])
                    if first is None:first=time.monotonic()
                    parts+=1
                    yield json.dumps({**meta,'type':'chunk','index':index,'text':answer if index==0 else f'part-{index}','context_sha256':context_hash,'cache_hit':hit,'queue_seconds':queued},ensure_ascii=False)+'\n'
                else:
                    finished=True;result='completed';elapsed=time.monotonic()-started
                    queue.labels(*key).observe(queued);ttfc.labels(*key).observe(first-started);duration.labels(*key).observe(elapsed)
                    yield json.dumps({**meta,'type':'end','done':True,'chunks':parts,'total_seconds':elapsed,'ttfc_seconds':first-started,'queue_seconds':queued,'context_sha256':context_hash})+'\n'
            except asyncio.CancelledError:raise
            except Exception as exc:
                result='error';event('backend_error',**meta,error=str(exc))
                raise
            finally:
                requests.labels(*key,result).inc()
                event('request_finished',**meta,phase=phase,outcome=result,parts=parts,queue_seconds=queued,ttfc_seconds=None if first is None else first-started,total_seconds=time.monotonic()-started,peer_ip=peer)
                await gate.release();running.set(gate.running);waiting.set(gate.waiting)
        return StreamingResponse(stream(),media_type='application/x-ndjson',headers={'X-Request-ID':request_id,'X-Pod-Name':meta['pod'],'X-Model-ID':meta['model_id'],'X-Backend-Mode':'simulated','Cache-Control':'no-store'})
    return app

app=create_app()
