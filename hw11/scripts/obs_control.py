"""OBS websocket control; credentials live only in /tmp, never the repository."""
import base64,hashlib,json,uuid
from pathlib import Path
from websockets.sync.client import connect
class OBS:
 def __init__(self):
  self.ws=connect('ws://127.0.0.1:4457',proxy=None);hello=json.loads(self.ws.recv())['d'];identify={'rpcVersion':1,'eventSubscriptions':0}
  if 'authentication' in hello:
   a=hello['authentication'];pw=Path('/tmp/hw11-obs-password').read_text();secret=base64.b64encode(hashlib.sha256((pw+a['salt']).encode()).digest()).decode();identify['authentication']=base64.b64encode(hashlib.sha256((secret+a['challenge']).encode()).digest()).decode()
  self.ws.send(json.dumps({'op':1,'d':identify}));assert json.loads(self.ws.recv())['op']==2
 def call(self,name,**data):
  rid=str(uuid.uuid4());self.ws.send(json.dumps({'op':6,'d':{'requestType':name,'requestId':rid,'requestData':data}}))
  while True:
   result=json.loads(self.ws.recv())
   if result['op']==7 and result['d']['requestId']==rid:
    result=result['d']
    if not result['requestStatus']['result']:raise RuntimeError(name+': '+str(result['requestStatus']))
    return result.get('responseData',{})
if __name__=='__main__':
 import sys
 obs=OBS();print(json.dumps(obs.call(sys.argv[1],**json.loads(sys.argv[2] if len(sys.argv)>2 else '{}')),indent=2))
