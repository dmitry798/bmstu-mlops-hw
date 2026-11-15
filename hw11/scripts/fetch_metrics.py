"""Persist real Prometheus series for queues, spare capacity, CPU and HPA review."""
import httpx,json,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results'
start=json.loads((R/'b_none_uniform_1-summary.json').read_text())['start_wall'];end=time.time()
queries={'running':'hw11_running','waiting':'hw11_waiting','backend_ready':'hw11_backend_ready','cpu':'sum by(pod)(rate(container_cpu_usage_seconds_total{namespace="hw11",container="api"}[20s]))','memory':'sum by(pod)(container_memory_working_set_bytes{namespace="hw11",container="api"})','ready':'sum(kube_pod_status_ready{namespace="hw11",condition="true",pod=~"hw11-api-.*"})','rps':'sum by(pod)(rate(hw11_requests_total[20s]))'}
c=httpx.Client(timeout=60,trust_env=False);out=R/'prometheus-series';out.mkdir(exist_ok=True)
for name,q in queries.items():
 response=c.get('http://127.0.0.1:19090/api/v1/query_range',params={'query':q,'start':start,'end':end,'step':2});response.raise_for_status();data=response.json();assert data['status']=='success';(out/(name+'.json')).write_text(json.dumps({'query':q,'start':start,'end':end,'step':2,'result':data}))
print('Saved',len(queries),'actual time series')
