"""Correlate an observed hot queue with spare capacity on the same two Pods."""
import json,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results'
def read(n):return json.loads((R/n).read_text())
def series(name):
 result=read('prometheus-series/'+name+'.json')['result']['data']['result'];return {x['metric']['pod']:{float(t):float(v) for t,v in x['values']} for x in result}
waiting,running=series('waiting'),series('running');evidence=[]
for rep in range(1,4):
 name=f'b_sticky_skew_{rep}';summary=read(name+'-summary.json');rows=[json.loads(x) for x in (R/(name+'-requests.jsonl')).read_text().splitlines()];counts=collections.Counter(r['pod'] for r in rows);hot=counts.most_common(1)[0][0];baseline={p['metadata']['name'] for p in read('preflight/pods-stable-b.json')['items'] if p['metadata']['labels'].get('app')=='hw11-api'};others=[p for p in running if p!=hot and p in baseline]
 samples=[]
 for t,q in waiting[hot].items():
  if summary['start_wall']<=t<summary['start_wall']+120 and q>=1:
   for other in others:
    if running[other].get(t)==0 and waiting[other].get(t)==0:samples.append({'wall_time':t,'hot_pod':hot,'hot_waiting':q,'spare_pod':other,'spare_running':0,'spare_waiting':0})
 evidence.append({'phase':name,'distribution':dict(counts),'observed_queue_while_other_idle_samples':len(samples),'sampling_seconds':2,'examples':samples[:10]})
(R/'b-hot-spare-capacity.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(evidence,indent=2))
