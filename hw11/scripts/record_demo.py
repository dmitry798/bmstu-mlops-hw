"""Actual terminal/browser screen demo: commands/output only, no captions/audio."""
import os,time,subprocess,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
os.chdir(REPO);os.environ['KUBECONFIG']=str(ROOT/'.local/kubeconfig');os.environ['PATH']=str(ROOT/'.tools')+':'+os.environ['PATH'];os.environ['PYTHONPATH']=str(ROOT)
go=Path(sys.argv[1])
while not go.exists():time.sleep(.1)
def show(command,hold=8):
 print('\033[2J\033[H',end='',flush=True);print('$ '+command,flush=True);subprocess.run(command,shell=True,cwd=REPO,check=True);time.sleep(hold)
show('kubectl get nodes -o wide; kubectl -n hw11 get pods -o wide',12)
show('helm get values hw11 -n hw11 --all; kubectl -n hw11 get service',12)
show('kubectl -n hw11 get deployment hw11-api -o jsonpath=\'{.spec.template.spec.containers[0].startupProbe}{"\\n"}{.spec.template.spec.containers[0].readinessProbe}{"\\n"}{.spec.template.spec.containers[0].livenessProbe}{"\\n"}{.spec.template.spec.containers[0].resources}{"\\n"}\'',12)
show('hw11/.venv/bin/python hw11/scripts/live_smoke.py',10)
show('PYTHONPATH=hw11 hw11/.venv/bin/python -m unittest discover -s hw11/tests -v',10)
show('hw11/.venv/bin/python hw11/scripts/demo_evidence.py checks',15)
show('hw11/.venv/bin/python hw11/scripts/demo_evidence.py A',20)
show('hw11/.venv/bin/python hw11/scripts/demo_evidence.py B',22)
show('hw11/.venv/bin/python hw11/scripts/demo_evidence.py histograms',15)
show('kubectl -n hw11 get hpa; kubectl -n hw11 top pods',12)
show('cat hw11/monitoring/alerts.yaml',15)
show('hw11/.venv/bin/python hw11/scripts/demo_evidence.py C',25)
from browser_control import Browser
browser=Browser();browser.navigate((ROOT/'report.html').as_uri());time.sleep(3);browser.js('document.body.style.fontSize="22px"')
subprocess.run(['wmctrl','-a','ДЗ11 — Kubernetes под нагрузкой']);time.sleep(15)
for filename,hold in [('1-ready-rollout.png',15),('2-per-pod.png',15),('3-policies.png',18),('4-hpa.png',18)]:
 browser.navigate((ROOT/'results/plots'/filename).as_uri());time.sleep(hold)
browser.navigate((ROOT/'report.html').as_uri());time.sleep(2);browser.js('document.body.style.fontSize="22px"')
browser.js('Array.from(document.querySelectorAll("h2")).find(x=>x.textContent.includes("Ревью PR")).scrollIntoView()');time.sleep(60)
browser.navigate('http://127.0.0.1:13000/d/hw11/hw11-simulated-cpu-backend?orgId=1&from=now-1h&to=now&kiosk');time.sleep(20);browser.js('window.scrollTo(0,650)');time.sleep(15)
subprocess.run(['wmctrl','-a','HW11 demonstration'])
show('hw11/.venv/bin/python hw11/scripts/demo_evidence.py audit; git log -1 --format="%h %an <%ae> %s"',20)
(ROOT/'results/demo-finished.json').write_text(json.dumps({'wall_time':time.time()}))
time.sleep(10)
