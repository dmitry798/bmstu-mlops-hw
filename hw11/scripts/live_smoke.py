"""Short real in-cluster streaming check for the final screen recording."""
import time,json
from experiments import *
processes=launch_clients()
try:
 name='video-smoke-'+str(int(time.time()));rows=collect(begin(name,'test',schedule(4,1)))
 for r in rows:print(json.dumps({k:r[k] for k in ['request_id','client_ip','status','pod','model_id','backend_mode','chunks','done','outcome','ttfc_seconds']},ensure_ascii=False))
 assert all(r['done'] and r['model_id']=='A' and r['backend_mode']=='simulated' for r in rows)
finally:
 for p in processes:p.terminate()
