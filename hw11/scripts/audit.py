"""Fail on missing mandatory evidence. Never infer PASS from a screenshot."""
import json,collections,hashlib,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';checks=[]
def load(n):return json.loads((R/n).read_text())
def rows(n):return [json.loads(x) for x in (R/n).read_text().splitlines() if x.strip()]
def check(name,value,evidence):checks.append({'name':name,'passed':bool(value),'evidence':evidence})
try:
 unit=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],env={**__import__('os').environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True);(R/'unit-final.log').write_text(unit.stdout+unit.stderr)
 check('unit_suite',unit.returncode==0,'unit-final.log')
 lint=subprocess.run([str(ROOT/'.tools/helm'),'lint',str(ROOT/'charts/hw11')],capture_output=True,text=True);(R/'helm-lint.log').write_text(lint.stdout+lint.stderr);check('helm_lint',lint.returncode==0,'helm-lint.log')
 check('five_real_kubernetes_checks',len(load('kubernetes-checks.json'))>=5 and all(c['passed'] for c in load('kubernetes-checks.json')),'kubernetes-checks.json')
 warm=load('warmup-correlations.json');check('Ready_EndpointSlice_backend_warmup_correlation',warm[0]['cold_backend_received']>0 and warm[0]['endpoint_before_warmup']>0 and warm[1]['cold_backend_received']==0 and warm[1]['ready_before_warmup']==0 and warm[1]['endpoint_before_warmup']==0,'warmup-correlations.json')
 check('readiness_red_green_healthy_rollout',all(c['passed'] for c in load('checks-a-repeat.json')),'checks-a-repeat.json')
 initial=load('checks-a.json');check('unready_B_exclusion_actual_rollback',all(next(c for c in initial if c['name']==n)['passed'] for n in ['unready_B_excluded','rollback_actual_version_A']),'a-bad-b-requests.jsonl; a-rollback-requests.jsonl')
 phases=[];schedules={};allb=[]
 for policy in ['none','sticky','fixed']:
  for traffic in ['uniform','skew']:
   for rep in range(1,4):
    name=f'b_{policy}_{traffic}_{rep}';rs=rows(name+'-requests.jsonl');summary=load(name+'-summary.json');spec=load(name+'-schedule.json');allb+=rs;phases.append(name)
    digest=hashlib.sha256(json.dumps(spec['items'],sort_keys=True).encode()).hexdigest();schedules.setdefault(traffic,set()).add(digest)
    check(name+'_120s_complete_accounting',summary['measured_schedule_seconds']>=120 and summary['sent']==summary['planned']==len(rs)==720 and sum(summary['outcomes'].values())==720,{'summary':name+'-summary.json','schedule_sha256':digest})
 check('identical_schedules_for_comparisons',all(len(v)==1 for v in schedules.values()),{k:list(v) for k,v in schedules.items()})
 baseline=load('preflight/pods-stable-b.json')['items'];expected={p['metadata']['name'] for p in baseline if p['metadata']['labels'].get('app')=='hw11-api'}
 start=load('b_none_uniform_1-summary.json')['start_wall'];end=load('b_fixed_skew_3-summary.json')['last_finish_wall'];stable=True;snap_count=0
 for snap in rows('kubernetes-timeline.jsonl'):
  if start<=snap['wall_time']<=end:
   active=[p for p in snap['pods']['items'] if p['metadata']['labels'].get('app')=='hw11-api' and not p['metadata'].get('deletionTimestamp')];snap_count+=1
   stable=stable and {p['metadata']['name'] for p in active}==expected and all(c['restartCount']==0 for p in active for c in p['status'].get('containerStatuses',[]))
 check('same_two_Pods_without_restart_all_B',len(expected)==2 and stable and snap_count>500,{'pods':sorted(expected),'snapshots':snap_count})
 ips={r['client_ip'] for r in allb};check('four_distinct_client_pod_IPs',len(ips)>=4,sorted(ips))
 check('all_B_responses_have_real_pod_version',all(r['pod'] and r['model_id']=='A' and r['backend_mode']=='simulated' for r in allb),'b_*-requests.jsonl')
 network=load('network-analysis.json');check('non_skew_control_retained',next(x for x in network if x['phase']=='b_none_skew_1')['max_pod_share']<.65,'network-analysis.json')
 sticky=rows('b_sticky_skew_1-requests.jsonl');distribution=collections.Counter(r['pod'] for r in sticky);check('hot_replica_reproduced',max(distribution.values())/len(sticky)>=.79,dict(distribution))
 compare=load('histogram-comparison.json');check('hot_queue_and_other_idle_observed',all(x['observed_queue_while_other_idle_samples']>0 for x in load('b-hot-spare-capacity.json')),'b-hot-spare-capacity.json')
 check('matching_histogram_completed_cohorts',len(compare)==18 and all(x['client_n']==x['prometheus_n'] for x in compare),'histogram-comparison.json')
 events=load('c-events.json');names={x['kind'] for x in events};check('hpa_two_to_three_to_two_twice',all(n in names for n in ['c-compute_three_ready','c-compute_two_restored','c-hot_three_ready','c-hot_two_restored']),'c-events.json; kubernetes-timeline.jsonl')
 alerts=rows('c-alert-states.jsonl');states=collections.defaultdict(set)
 for snap in alerts:
  for a in snap['data']['data']['alerts']:states[a['labels']['alertname']].add(a['state'])
 final={a['labels']['alertname'] for snap in alerts[-5:] for a in snap['data']['data']['alerts']}
 check('both_alerts_pending_firing_recovered',all({'pending','firing'}<=states[n] and n not in final for n in ['HW11HighTTFC','HW11RejectionFraction']),{'states':{k:sorted(v) for k,v in states.items()},'last_5_active_names':sorted(final)})
 check('four_plots',all((R/'plots'/n).is_file() for n in ['1-ready-rollout.png','2-per-pod.png','3-policies.png','4-hpa.png']),'plots/')
 check('backend_logs_link_requests',any('cold_backend_received' in p.read_text() for p in (R/'pod-logs').glob('*.log')),'pod-logs/')
 monitor=load('monitoring-live-check.json');check('live_Grafana_all_required_panels_and_both_gauges',len(monitor['dashboard_panels'])>=8 and {'hw11_running','hw11_waiting'}<=set(monitor['observed_series_names']) and all(t['health']=='up' for t in monitor['targets']),'monitoring-live-check.json; monitoring/dashboard-export.json')
 check('primary_case_review',(ROOT/'docs/review.md').exists() and 'philly-atc19.pdf' in (ROOT/'docs/review.md').read_text(),'docs/review.md; lecture 24:40 slide141')
except Exception as exc:
 check('audit_has_all_inputs',False,type(exc).__name__+': '+str(exc))
result={'status':'PASS' if checks and all(x['passed'] for x in checks) else 'FAIL','checks':checks}
(R/'audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,indent=2,ensure_ascii=False));sys.exit(0 if result['status']=='PASS' else 1)
