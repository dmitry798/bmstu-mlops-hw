"""Control only the separate demonstration Chromium profile via local CDP."""
import json,urllib.request,itertools
from websockets.sync.client import connect
class Browser:
 def __init__(self):
  tabs=json.load(urllib.request.urlopen('http://127.0.0.1:9227/json'));tab=next(t for t in tabs if t['type']=='page');self.ws=connect(tab['webSocketDebuggerUrl'],proxy=None);self.ids=itertools.count(1)
 def call(self,method,**params):
  i=next(self.ids);self.ws.send(json.dumps({'id':i,'method':method,'params':params}))
  while True:
   data=json.loads(self.ws.recv())
   if data.get('id')==i:
    if 'error' in data:raise RuntimeError(data['error'])
    return data.get('result',{})
 def navigate(self,url):return self.call('Page.navigate',url=url)
 def js(self,expression):return self.call('Runtime.evaluate',expression=expression,returnByValue=True)
if __name__=='__main__':
 import sys
 b=Browser();print(b.navigate(sys.argv[1]) if len(sys.argv)>1 else b.js('document.title'))
