"""Readiness, real response, invalid request and unchanged backend calls."""
import json
from pathlib import Path
import sys
import time
from benchmark import request
from urllib.error import HTTPError
url = sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8091'
records=[]
for _ in range(180):
    try:
        status, ready=request(url+'/ready')
        if status==200: break
    except (OSError,HTTPError): time.sleep(1)
else: raise RuntimeError('Real backend not ready')
for path in ['/health','/ready','/debug']:
    status,payload=request(url+path);records.append({'path':path,'status':status,'body':payload})
before=request(url+'/debug')[1]['calls']
try: request(url+'/generate',{'prompt':'hello','max_new_tokens':100000})
except HTTPError as exc: records.append({'path':'/generate invalid','status':exc.code,'body':json.loads(exc.read())})
after=request(url+'/debug')[1]['calls']
assert before==after
status,answer=request(url+'/generate',{'prompt':'Что выведет print(2 + 3)? choices: A: 5; B: 6.','max_new_tokens':32})
assert status==200 and 'STUB ONLY' not in answer['answer']
records.append({'path':'/generate real','status':status,'body':answer})
print(json.dumps(records,ensure_ascii=False,indent=2))
Path('docs/real/smoke.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
