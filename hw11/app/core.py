"""Small, independently tested scheduling/accounting primitives."""
import asyncio
from collections import OrderedDict
import hashlib
import math
import time
import uuid

class Rejected(Exception):pass

class Admission:
    def __init__(self,capacity,queue_limit):
        self.capacity=capacity;self.queue_limit=queue_limit
        self.running=0;self.waiting=0;self.condition=asyncio.Condition()
    async def acquire(self):
        async with self.condition:
            if self.running>=self.capacity:
                if self.waiting>=self.queue_limit:raise Rejected('queue_full')
                self.waiting+=1
                try:
                    while self.running>=self.capacity:await self.condition.wait()
                finally:self.waiting-=1
            self.running+=1
    async def release(self):
        async with self.condition:
            if self.running<=0:raise RuntimeError('unbalanced admission release')
            self.running-=1;self.condition.notify(1)

class PrefixCache:
    def __init__(self,capacity):self.capacity=capacity;self.entries=OrderedDict()
    def lookup(self,key):
        hit=key in self.entries
        self.entries[key]=None;self.entries.move_to_end(key)
        if len(self.entries)>self.capacity:self.entries.popitem(last=False)
        return hit
    def clear(self):self.entries.clear()

def classify(status,done,deadline):
    if deadline:return 'expired'
    if status in (429,503):return 'rejected'
    if status==200:return 'completed' if done else 'aborted'
    return 'error'

def bucket_quantile(buckets,q):
    buckets=sorted(buckets);total=buckets[-1][1]
    if total==0:return None
    target=q*total;before=0;lower=0.
    for upper,count in buckets:
        if count>=target:
            if math.isinf(upper):return lower
            return lower+(upper-lower)*(target-before)/(count-before) if count>before else upper
        lower=upper;before=count
    return lower

def validate_payload(value):
    if not isinstance(value,dict):raise ValueError('JSON object required')
    messages=value.get('messages')
    if messages is None and isinstance(value.get('prompt'),str):messages=[{'role':'user','content':value['prompt']}]
    if not isinstance(messages,list) or not messages:raise ValueError('nonempty messages required')
    for message in messages:
        if not isinstance(message,dict) or message.get('role') not in ['user','assistant','system'] or not isinstance(message.get('content'),str) or not message['content'].strip():raise ValueError('invalid message')
    if sum(len(m['content']) for m in messages)>8192:raise ValueError('input exceeds 8192 characters')
    result={**value,'messages':messages}
    limits={'chunks':(4,1,64),'chunk_delay':(.04,0.,.6),'work_multiplier':(1.,0.,8.)}
    for key,(default,lower,upper) in limits.items():
        item=value.get(key,default)
        if isinstance(item,bool) or not isinstance(item,(int,float)) or not math.isfinite(item) or not lower<=item<=upper:raise ValueError('invalid '+key)
        if key=='chunks' and type(item) is not int:raise ValueError('chunks must be integer')
        result[key]=item
    result['request_id']=str(value.get('request_id') or uuid.uuid4())
    if len(result['request_id'])>128:raise ValueError('request_id too long')
    result['session_id']=str(value.get('session_id','none'))[:128]
    result['phase']=str(value.get('phase','other'))
    return result

def cpu_burn(seconds):
    started=time.thread_time();payload=b'hw11-simulated-cpu'
    while time.thread_time()-started<seconds:payload=hashlib.pbkdf2_hmac('sha256',payload,b'hw11',512)
    return time.thread_time()-started
