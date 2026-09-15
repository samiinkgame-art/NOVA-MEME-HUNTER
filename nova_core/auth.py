import hashlib, math, time, threading
from collections import Counter, OrderedDict

def validate_key(key:str):
    if not key: return
    if len(key)<32 or len(key)>256 or not key.isascii() or any(x.isspace() for x in key):
        raise ValueError('NOVA_ADMIN_KEY: 32-256 ASCII characters without whitespace required')
    counts=Counter(key)
    entropy=-sum(n/len(key)*math.log2(n/len(key)) for n in counts.values())*len(key)
    if len(counts)<10 or entropy<100:
        raise ValueError('NOVA_ADMIN_KEY is too repetitive; choose a stronger key')

class RateLimiter:
    """Per-process admission limiter; bounded memory; one API worker deployment."""
    def __init__(self,limit=120,window=60,capacity=4096):
        self.limit,self.window,self.capacity=limit,window,capacity
        self.items=OrderedDict();self.lock=threading.Lock()
    def allow(self,identity):
        now=time.monotonic();key=hashlib.sha256(identity.encode()).digest()
        with self.lock:
            count,start=self.items.get(key,(0,now))
            if now-start>=self.window: count,start=0,now
            self.items[key]=(count+1,start);self.items.move_to_end(key)
            while len(self.items)>self.capacity:self.items.popitem(last=False)
            return count<self.limit
