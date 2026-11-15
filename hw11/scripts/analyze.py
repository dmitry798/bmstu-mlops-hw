"""Analysis reads actual raw data; no success counts or p95 values are hand-entered."""
from pathlib import Path
import json,math,sys,statistics,html,collections,hashlib,time
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/hw11-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':12,'axes.titlesize':12,'axes.labelsize':12,'xtick.labelsize':11,'ytick.labelsize':11})
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from app.core import bucket_quantile
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';plots=R/'plots';plots.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def percentile(xs,q):
 if not xs:return None
 xs=sorted(xs);index=(len(xs)-1)*q;lo=int(index);return xs[lo]+(xs[min(lo+1,len(xs)-1)]-xs[lo])*(index-lo)
def stats(rs):
 ok=[x for x in rs if x['outcome']=='completed'];n=len(rs);intervals=[v for x in ok for v in x['inter_chunk_seconds']]
 return {'inter_chunk_n':len(intervals),'inter_chunk_p50':percentile(intervals,.5),'inter_chunk_p95':percentile(intervals,.95),'sent':n,'completed':len(ok),'rejected':sum(x['outcome']=='rejected' for x in rs),'aborted':sum(x['outcome']=='aborted' for x in rs),'expired':sum(x['outcome']=='expired' for x in rs),'error':sum(x['outcome']=='error' for x in rs),'error_fraction':sum(x['outcome']!='completed' for x in rs)/n if n else 0,'timeout_fraction':sum(x['outcome']=='expired' for x in rs)/n if n else 0,**{f'{metric}_p{int(q*100)}':percentile([x[metric] for x in ok if x[metric] is not None],q) for metric in ['ttfc_seconds','total_seconds','queue_seconds'] for q in [.5,.95]},'send_lag_p95':percentile([x['send_lag_seconds'] for x in rs],.95),'pod_distribution':dict(collections.Counter(x['pod'] for x in rs)),'cache_hit_fraction':sum(bool(x['cache_hit']) for x in ok)/len(ok) if ok else None}
attribution={}
for path in (R/'pod-logs').glob('*.log'):
 for line in path.read_text().splitlines():
  try:event=json.loads(line)
  except ValueError:continue
  if event.get('event')=='request_received':attribution[event['request_id']]=event
allrows=[];summaries={};compare=[]
for p in sorted(R.glob('*-requests.jsonl')):
 rs=rows(p)
 for row in rs:
  if row['pod'] is None and row['request_id'] in attribution:
   e=attribution[row['request_id']];row['client_observed_pod']=None;row['pod']=e['pod'];row['model_id']=e['model_id'];row['attribution_source']='backend_request_log'
 allrows+=rs;name=p.name.removesuffix('-requests.jsonl');summaries[name]=stats(rs)
 spec=load(R/(name+'-schedule.json'));summaries[name]['planned']=len(spec['items']);summaries[name]['unsent']=len(spec['items'])-len(rs)
with (R/'requests.jsonl').open('w') as f:
 for row in allrows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
(R/'statistics.json').write_text(json.dumps(summaries,indent=2))
for name,s in summaries.items():
 if not name.startswith('b_'):continue
 prom=load(R/(name+'-prometheus.json'));metrics=prom['data']['result'];buckets=collections.defaultdict(float);count=0
 for m in metrics:
  if m['metric']['__name__']=='hw11_ttfc_seconds_bucket':buckets[float(m['metric']['le'])]+=float(m['value'][1])
  if m['metric']['__name__']=='hw11_ttfc_seconds_count':count+=float(m['value'][1])
 compare.append({'phase':name,'client_n':s['completed'],'prometheus_n':count,'client_ttfc_p95':s['ttfc_seconds_p95'],'server_exact_ttfc_p95':percentile([r['server_ttfc_seconds'] for r in rows(R/(name+'-requests.jsonl')) if r['done']],.95),'prometheus_bucket_ttfc_p95':bucket_quantile(list(buckets.items()),.95),'buckets':dict(buckets)})
(R/'histogram-comparison.json').write_text(json.dumps(compare,indent=2))
# All policy repetitions shown, including non-skew sticky uniform results.
fig,ax=plt.subplots(1,2,figsize=(13,5))
for j,traffic in enumerate(['uniform','skew']):
 for i,policy in enumerate(['none','sticky','fixed']):
  vals=[summaries[f'b_{policy}_{traffic}_{r}']['ttfc_seconds_p95'] for r in range(1,4)]
  ax[j].scatter([i-.1,i,i+.1],vals,label=policy,s=65);ax[j].plot([i-.1,i+.1],[statistics.mean(vals)]*2,color='black')
 ax[j].set(xticks=range(3),xticklabels=['None','ClientIP','Fixed=None'],ylabel='Completed client TTFC p95 (s)',title=f'{traffic}: 3 repetitions × 120 s; 6 requests/s');ax[j].grid(alpha=.3)
fig.tight_layout();fig.savefig(plots/'3-policies.png',dpi=140);plt.close(fig)
# Hot replica vs spare capacity: queue/TTFC individual requests and per-Pod shares.
fig,ax=plt.subplots(2,1,figsize=(12,8),sharex=True)
rs=rows(R/'b_sticky_skew_1-requests.jsonl');start=min(r['planned_wall'] for r in rs)
for pod in sorted({r['pod'] for r in rs if r['pod']}):
 data=[r for r in rs if r['pod']==pod and r['done']]
 ax[0].scatter([r['send_wall']-start for r in data],[r['ttfc_seconds'] for r in data],s=8,label=f'{pod}: {len(data)} done / {sum(r["pod"]==pod for r in rs)} sent')
 ax[1].scatter([r['send_wall']-start for r in data],[r['queue_seconds'] for r in data],s=8,label=pod)
ax[0].set(ylabel='TTFC (s)',title='ClientIP, 80% one client; completed only; 6 req/s; running<=1, waiting<=6 / Pod');ax[1].set(ylabel='Queue (s)',xlabel='Elapsed send time (s)');ax[0].legend(fontsize=8);ax[1].legend(fontsize=8)
for a in ax:a.grid(alpha=.3)
fig.tight_layout();fig.savefig(plots/'2-per-pod.png',dpi=140);plt.close(fig)
# Compact real Ready / EndpointSlice timeline, tied to request arrivals and rollout.
snaps=rows(R/'kubernetes-timeline.jsonl');snaps.sort(key=lambda x:x['wall_time'])
a_names=['a-broken-proof','a-fixed-proof','a-healthy-rollout'];ar=sum([rows(R/(n+'-requests.jsonl')) for n in a_names],[]);a0=min(x['planned_wall'] for x in ar);a1=max(x['send_wall']+x['total_seconds'] for x in ar)
sel=[s for s in snaps if a0-5<=s['wall_time']<=a1+5]
fig,ax=plt.subplots(2,1,figsize=(13,8),sharex=True)
def ready(p):return any(x['type']=='Ready' and x['status']=='True' for x in p['status'].get('conditions',[]))
ax[0].step([(s['wall_time']-a0) for s in sel],[sum(ready(p) for p in s['pods']['items'] if p['metadata']['labels'].get('app')=='hw11-api') for s in sel],where='post',label='Kubernetes Ready')
ax[0].step([(s['wall_time']-a0) for s in sel],[sum(e.get('conditions',{}).get('ready',False) for item in s['endpoints']['items'] if item['metadata']['labels'].get('kubernetes.io/service-name')=='hw11-api' for e in (item.get('endpoints') or [])) for s in sel],where='post',label='Service ready endpoints',linestyle='--')
for n in a_names:
 rs=rows(R/(n+'-requests.jsonl'));ax[1].scatter([r['send_wall']-a0 for r in rs],[r['status'] or 0 for r in rs],s=12,label=n)
roll=next(x['rollout_start_wall'] for x in load(R/'checks-a-repeat.json') if x['name']=='healthy_rollout_zero_errors')
for a in ax:a.axvline(roll-a0,color='red',linestyle=':',label='A→B rollout' if a==ax[0] else None);a.grid(alpha=.3);a.legend(fontsize=8)
ax[0].set(ylabel='Count',title='20 s warmup: broken / fixed cold start, then healthy A→B; .2 req/s + 2 long streams');ax[1].set(ylabel='HTTP status (0 = no endpoint)',xlabel='Elapsed time (s)');fig.tight_layout();fig.savefig(plots/'1-ready-rollout.png',dpi=140);plt.close(fig)
# HPA actual state, sampled from Kubernetes rather than inferring replicas from CPU.
events=load(R/'c-events.json');c0=events[0]['wall_time'];c1=events[-1]['wall_time'];sel=[s for s in snaps if c0-5<=s['wall_time']<=c1+5]
fig,ax=plt.subplots(2,1,figsize=(13,8),sharex=True)
xs=[s['wall_time']-c0 for s in sel]
for field in ['currentReplicas','desiredReplicas']:
 ax[0].step(xs,[s['hpa']['items'][0].get('status',{}).get(field,2) if s['hpa']['items'] else 2 for s in sel],where='post',label=field)
ax[0].step(xs,[sum(ready(p) for p in s['pods']['items'] if p['metadata']['labels'].get('app')=='hw11-api') for s in sel],where='post',label='Ready',linestyle=':')
cr=[r for r in allrows if r['phase'] in ['c_hpa','c_hot','c_alerts']];bins=collections.Counter(int(r['send_wall']-c0) for r in cr);ax[1].plot(sorted(bins),[bins[x] for x in sorted(bins)],label='Actual sent req/s')
for e in events:
 if e['kind'].endswith('start') or e['kind'].endswith('load_stopped'):
  for a in ax:a.axvline(e['wall_time']-c0,linestyle=':',alpha=.4)
ax[0].set(ylabel='Replicas',title='HPA CPU target 65% of 250m requests; min2/max3; down stabilization 30s');ax[1].set(ylabel='Requests / s',xlabel='Elapsed time (s)');
for a in ax:a.legend();a.grid(alpha=.3)
fig.tight_layout();fig.savefig(plots/'4-hpa.png',dpi=140);plt.close(fig)
print('Analyzed',len(allrows),'requests;',len(compare),'histogram cohorts')
