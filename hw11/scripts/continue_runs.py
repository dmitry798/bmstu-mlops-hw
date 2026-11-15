"""Sequential experiments never overlap; no workload duration is shortened."""
import os,time,subprocess,sys
from cluster import ROOT
while True:
 try:os.kill(30118,0)
 except ProcessLookupError:break
 time.sleep(3)
for script,args,log in [('recheck_a.py',[],'a-repeat.log'),('kubernetes_checks.py',[],'kubernetes-checks.log'),('experiments.py',['pilot'],'pilot.log')]:
 with (ROOT/'results'/log).open('w') as f:
  result=subprocess.run([sys.executable,str(ROOT/'scripts'/script),*args],stdout=f,stderr=subprocess.STDOUT)
 if result.returncode:raise SystemExit(script+' failed; inspect '+log)
print('PILOT READY FOR REVIEW',flush=True)
