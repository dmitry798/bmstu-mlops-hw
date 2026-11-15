"""Readable views of saved real evidence for screen demonstration."""
import json,sys,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results'
def read(n):return json.loads((R/n).read_text())
mode=sys.argv[1]
if mode=='A':
 for c in read('checks-a-repeat.json'):
  print(c['name'],':','PASS' if c['passed'] else 'FAIL')
  print(json.dumps({k:v for k,v in c.items() if k not in ['name','passed']},indent=2))
 for c in read('checks-a.json'):
  if c['name'] in ['unready_B_excluded','rollback_actual_version_A']:print(c['name'],c['passed'],c['detail'])
elif mode=='checks':
 for c in read('kubernetes-checks.json'):
  print(c['name'],':','PASS' if c['passed'] else 'FAIL')
 crash=next(c for c in read('kubernetes-checks.json') if c['name']=='rejection_and_partial_stream_accounting')['evidence'];r=crash['crash_row'];print(json.dumps({k:r[k] for k in ['request_id','status','pod','model_id','chunks','expected_chunks','done','outcome','error']},indent=2));print('kill→recovered seconds:',round(crash['recovery_wall']-crash['kill_wall'],2))
elif mode=='B':
 stats=read('statistics.json');print('phase                         sent done reject TTFC_p95_s queue_p95_s sendlag_p95_s')
 for name,s in stats.items():
  if name.startswith('b_'):print(f"{name:29} {s['sent']:4} {s['completed']:4} {s['rejected']:4} {s['ttfc_seconds_p95']:10.3f} {s['queue_seconds_p95']:10.3f} {s['send_lag_p95']:10.4f}")
 print('\nClientIP/skew/run1 actual Pod distribution:',stats['b_sticky_skew_1']['pod_distribution'])
elif mode=='histograms':
 print('cohort                       client_n prom_n client_p95 server_exact bucket_p95')
 for s in read('histogram-comparison.json'):print(f"{s['phase']:28} {s['client_n']:6} {s['prometheus_n']:6.0f} {s['client_ttfc_p95']:10.3f} {s['server_exact_ttfc_p95']:10.3f} {s['prometheus_bucket_ttfc_p95']:10.3f}")
elif mode=='C':
 for x in read('c-hpa-analysis.json'):
  print(x['scenario'])
  for p in x['new_pods']:
   print(' new Pod:',p['pod'],'created UTC:',p['creation_timestamp'])
   print(' Ready delay from creation (s):',round(p['first_ready_wall']-__import__('datetime').datetime.fromisoformat(p['creation_timestamp'].replace('Z','+00:00')).timestamp(),2))
  print(' desired2 after load stop (s):',round(x['desired_two_after_stop_seconds'],2))
  print(' Ready2 after load stop (s):',round(x['two_ready_after_stop_seconds'],2))
  print(' configured down stabilization (s):',x['configured_stabilization_seconds'])
  print(' request distribution:',x['total_pod_distribution'])
  print(' new Pod requests:',x['new_pod_requests'])
 states=collections.defaultdict(set)
 for line in (R/'c-alert-states.jsonl').read_text().splitlines():
  for a in json.loads(line)['data']['data']['alerts']:states[a['labels']['alertname']].add(a['state'])
 print('Observed alert states:',dict((k,sorted(v)) for k,v in states.items()))
elif mode=='audit':
 data=read('audit.json');print('Audit:',data['status'],'checks:',len(data['checks']))
 phases=[c for c in data['checks'] if c['name'].endswith('_120s_complete_accounting')]
 print('120s policy/traffic repetitions:',len(phases),'all PASS:',all(c['passed'] for c in phases))
 for c in data['checks']:
  if c not in phases:print(('PASS' if c['passed'] else 'FAIL'),c['name'])
