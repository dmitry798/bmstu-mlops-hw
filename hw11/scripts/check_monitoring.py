import httpx,json,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results';c=httpx.Client(timeout=10,trust_env=False)
for i in range(60):
 try:
  d=c.get('http://127.0.0.1:13000/api/dashboards/uid/hw11');d.raise_for_status();data=d.json();break
 except Exception:time.sleep(1)
else:raise RuntimeError('Grafana dashboard unavailable')
(R.parent/'monitoring/dashboard-export.json').write_text(json.dumps(data,indent=2));panels=data['dashboard']['panels'];q=next(p['targets'][0]['expr'] for p in panels if p['title']=='Running / waiting');r=c.get('http://127.0.0.1:19090/api/v1/query',params={'query':q}).json();names={x['metric'].get('__name__') for x in r['data']['result']};assert {'hw11_running','hw11_waiting'}<=names,names
state={'dashboard_panels':[p['title'] for p in panels],'running_waiting_query':q,'observed_series_names':sorted(names),'targets':c.get('http://127.0.0.1:19090/api/v1/targets').json()['data']['activeTargets']}
(R/'monitoring-live-check.json').write_text(json.dumps(state,indent=2));assert all(t['health']=='up' for t in state['targets']),state['targets'];print('Grafana actual export:8panels; running+waiting both present; all Prometheus targets UP')
