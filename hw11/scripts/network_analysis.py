import json,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'results';result=[]
for p in sorted(R.glob('b_*-requests.jsonl')):
 rows=[json.loads(x) for x in p.read_text().splitlines()];mapping={ip:dict(collections.Counter(r['pod'] for r in rows if r['client_ip']==ip)) for ip in sorted({r['client_ip'] for r in rows})};counts=collections.Counter(r['pod'] for r in rows)
 result.append({'phase':rows[0]['phase'],'total':len(rows),'client_IP_to_actual_pod_counts':mapping,'pod_counts':dict(counts),'max_pod_share':max(counts.values())/len(rows),'tcp_keep_alive':False})
(R/'network-analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps([x for x in result if x['phase'] in ['b_none_skew_1','b_sticky_uniform_1','b_sticky_skew_1']],indent=2))
