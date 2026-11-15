import time,json
from cluster import *
out=ROOT/'results/pod-logs';out.mkdir(exist_ok=True)
while True:
 for p in pods():
  name=p['metadata']['name']
  try:
   log=kub('logs',name,raw=True)
   if log:(out/(name+'.log')).write_text(log)
   if p['status'].get('containerStatuses',[{}])[0].get('restartCount',0):
    (out/(name+'-previous.log')).write_text(kub('logs',name,'--previous',raw=True))
  except Exception:pass
 time.sleep(3)
