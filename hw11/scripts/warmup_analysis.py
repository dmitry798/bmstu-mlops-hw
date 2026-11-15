"""Correlate actual requests, backend startup and Kubernetes EndpointSlice/Ready."""
import json,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results'
logs={}
for path in (R/'pod-logs').glob('*.log'):
 for line in path.read_text().splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  logs[(r.get('pod'),r.get('event'),r.get('request_id'),r.get('wall_time'))]=r
logs=list(logs.values());snaps=sorted([json.loads(x) for x in (R/'kubernetes-timeline.jsonl').read_text().splitlines()],key=lambda x:x['wall_time'])
def ready(p):return any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[]))
def endpoints(s):return {e.get('targetRef',{}).get('name') for es in s['endpoints']['items'] if es['metadata']['labels'].get('kubernetes.io/service-name')=='hw11-api' for e in es['endpoints'] if e.get('conditions',{}).get('ready')}
out=[]
for name in ['a-broken-proof','a-fixed-proof']:
 rs=[json.loads(x) for x in (R/(name+'-requests.jsonl')).read_text().splitlines()];ids={r['request_id'] for r in rs};received=[r for r in logs if r.get('request_id') in ids and r['event']=='request_received'];cold=[r for r in received if not r['warmup_finished']];podnames={r['pod'] for r in received};starts={p:next(r['wall_time'] for r in logs if r['pod']==p and r['event']=='startup') for p in podnames};early=[]
 for s in snaps:
  for p in s['pods']['items']:
   pn=p['metadata']['name']
   if pn in starts and starts[pn]<=s['wall_time']<starts[pn]+19:
    early.append({'wall_time':s['wall_time'],'pod':pn,'Ready':ready(p),'EndpointSlice_ready':pn in endpoints(s)})
 out.append({'run':name,'received_by_backend':len(received),'cold_backend_received':len(cold),'no_cold_delivery_property_passed':not cold,'expected_property':True,'early_warmup_observations':early,'ready_before_warmup':sum(x['Ready'] for x in early),'endpoint_before_warmup':sum(x['EndpointSlice_ready'] for x in early),'transport_errors_before_endpoints':sum(r['status'] is None for r in rs),'request_ids_cold':[r['request_id'] for r in cold]})
(R/'warmup-correlations.json').write_text(json.dumps(out,indent=2));assert out[0]['cold_backend_received']>0 and out[0]['ready_before_warmup']>0 and out[0]['endpoint_before_warmup']>0;assert out[1]['received_by_backend']>0 and out[1]['cold_backend_received']==0 and out[1]['ready_before_warmup']==0 and out[1]['endpoint_before_warmup']==0
print(json.dumps([{k:v for k,v in x.items() if k not in ['early_warmup_observations','request_ids_cold']} for x in out],indent=2))
