"""Full fresh-run workflow. Use a separate checkout; refuse retained evidence."""
import argparse,json,subprocess,sys,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent;R=ROOT/'results'
STAGES=['experiment_a.py','recheck_a.py','kubernetes_checks.py','experiments.py B','experiment_c.py','fetch_metrics.py','network_analysis.py','hot_analysis.py','warmup_analysis.py','hpa_analysis.py','analyze.py','check_monitoring.py','audit.py','resources.sh','report.py']
def require_empty_results(path):
 if path.exists() and any(path.iterdir()):raise RuntimeError('Results directory is not empty: '+str(path)+'; preserve it and use a fresh checkout as documented.')
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',action='store_true');args=parser.parse_args()
 if args.plan:print('\n'.join(['preflight + setup.sh','collect_logs.py (background)','capture stable two-Pod B baseline',*STAGES]));return
 require_empty_results(R)
 # Both cluster and tmpfs holder must be fresh. Cleanup is an explicit manual step.
 for name in ['hw11-control-plane','hw11-storage-holder']:
  if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:raise RuntimeError('Existing own stand '+name+'; use the documented own-stand cleanup before a full rerun.')
 R.mkdir(exist_ok=True);pre=R/'preflight';pre.mkdir();usage=shutil.disk_usage(REPO)
 (pre/'host-before.json').write_text(json.dumps({'wall_time':time.time(),'disk':usage._asdict(),'meminfo':Path('/proc/meminfo').read_text()}))
 def run(command,log):
  with (R/log).open('w') as f:subprocess.run(command,cwd=REPO,check=True,stdout=f,stderr=subprocess.STDOUT)
 run(['bash',str(ROOT/'scripts/setup.sh')],'setup.log')
 from cluster import kub,helm,wait_ready
 # Save actual limits and source versions before issuing experimental load.
 with (pre/'node-limits.json').open('w') as f:subprocess.run(['docker','inspect','hw11-control-plane','--format','{{json .HostConfig}}'],check=True,stdout=f)
 run([str(ROOT/'.tools/helm'),'lint',str(ROOT/'charts/hw11')],'helm-lint.log')
 helm(brokenProbes=True);collector_log=(R/'collector.log').open('w');collector=subprocess.Popen([sys.executable,str(ROOT/'scripts/collect_logs.py')],cwd=REPO,stdout=collector_log,stderr=subprocess.STDOUT)
 try:
  for stage in STAGES:
   if stage=='experiments.py B':
    wait_ready(2,'A');snapshot=kub('get','pods','-o','json');(pre/'pods-stable-b.json').write_text(json.dumps(snapshot));(pre/'pods-before-b.json').write_text(json.dumps(snapshot));(pre/'network.txt').write_text(kub('get','services,endpointslices,pods','-o','wide',raw=True));(pre/'network-stable-b.txt').write_text((pre/'network.txt').read_text())
    images=[{'pod':p['metadata']['name'],'containers':p['status'].get('containerStatuses',[])} for p in snapshot['items']];(pre/'images.json').write_text(json.dumps(images,indent=2))
    with (pre/'own-image-sizes.txt').open('w') as f:subprocess.run(['docker','image','inspect','kindest/node:v1.34.0@sha256:7416a61b42b1662ca6ca89f02028ac133a309a2a30ba309614e8ec94d976dc5a','hw11-api:1.1','--format','{{.RepoTags}} size_bytes={{.Size}} id={{.Id}}'],check=True,stdout=f)
   command=['bash',str(ROOT/'scripts'/stage)] if stage.endswith('.sh') else [sys.executable,str(ROOT/'scripts'/stage.split()[0]),*stage.split()[1:]]
   run(command,stage.replace(' ','-').replace('.py','').replace('.sh','')+'.log')
 finally:
  collector.terminate();collector.wait(timeout=10);collector_log.close()
 print('Full fresh run complete:',R)
if __name__=='__main__':main()
