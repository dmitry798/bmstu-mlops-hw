import json,datetime,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results'
events=json.loads((R/'c-events.json').read_text());snaps=[json.loads(x) for x in (R/'kubernetes-timeline.jsonl').read_text().splitlines()];snaps.sort(key=lambda x:x['wall_time'])
analysis=[]
for prefix in ['c-compute','c-hot']:
 start=next(x for x in events if x['kind']==prefix+'_start');stop=next(x for x in events if x['kind']==prefix+'_load_stopped');returned=next(x for x in events if x['kind']==prefix+'_two_restored');before=set(start['pods']);new={};trace=[]
 for s in snaps:
  if not start['wall_time']<=s['wall_time']<=returned['wall_time']:continue
  for p in s['pods']['items']:
   if p['metadata']['labels'].get('app')!='hw11-api' or p['metadata']['name'] in before:continue
   name=p['metadata']['name'];r=new.setdefault(name,{'pod':name,'creation_timestamp':p['metadata']['creationTimestamp'],'first_observed_wall':s['wall_time'],'first_ready_wall':None})
   if any(c['type']=='Ready' and c['status']=='True' for c in p['status'].get('conditions',[])) and r['first_ready_wall'] is None:r['first_ready_wall']=s['wall_time']
  if s['hpa']['items']:
   status=s['hpa']['items'][0].get('status',{});trace.append({'wall_time':s['wall_time'],'current':status.get('currentReplicas'),'desired':status.get('desiredReplicas'),'cpu':status.get('currentMetrics'),'conditions':status.get('conditions')})
 rows=[json.loads(x) for x in (R/(prefix+'-requests.jsonl')).read_text().splitlines()]
 dist=collections.Counter(r['pod'] for r in rows);scale_down=next((s['wall_time'] for s in trace if s['wall_time']>=stop['wall_time'] and s['desired']==2),None)
 analysis.append({'scenario':prefix,'new_pods':list(new.values()),'total_pod_distribution':dict(dist),'new_pod_requests':{p:dist.get(p,0) for p in new},'load_stop_wall':stop['wall_time'],'desired_two_after_stop_seconds':None if scale_down is None else scale_down-stop['wall_time'],'two_ready_after_stop_seconds':returned['wall_time']-stop['wall_time'],'configured_stabilization_seconds':30,'hpa_trace':trace})
(R/'c-hpa-analysis.json').write_text(json.dumps(analysis,indent=2));print(json.dumps([{k:v for k,v in x.items() if k!='hpa_trace'} for x in analysis],indent=2))
