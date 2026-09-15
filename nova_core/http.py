"""Bounded READ retries only; transaction submission is deliberately never retried."""
import asyncio, math, random, time
from email.utils import parsedate_to_datetime
import httpx

READ_RPC={'getAccountInfo','getTokenLargestAccounts','getMultipleAccounts','getBalance','getTokenSupply','getSignaturesForAddress','getTransaction','getSignatureStatuses','getLatestBlockhash','getSlot','getHealth'}
class ResilientClient(httpx.AsyncClient):
    failures={}
    opened_until={}
    async def request(self,method,url,**kwargs):
        host=httpx.URL(url).host
        safe=method.upper() in ('GET','HEAD') or (method.upper()=='POST' and isinstance(kwargs.get('json'),dict) and kwargs['json'].get('method') in READ_RPC)
        if safe and self.opened_until.get(host,0)>time.monotonic(): raise RuntimeError('Provider circuit open: '+host)
        for attempt in range(3 if safe else 1):
            try:
                response=await super().request(method,url,**kwargs)
                if response.status_code==429 and safe:
                    raw=response.headers.get('Retry-After','30')
                    try: delay=float(raw)
                    except ValueError:
                        try: delay=parsedate_to_datetime(raw).timestamp()-time.time()
                        except (ValueError,TypeError): delay=30
                    delay=max(1,delay if math.isfinite(delay) else 30)
                    self.opened_until[host]=time.monotonic()+delay
                    response.raise_for_status()
                if response.status_code<500:
                    self.failures[host]=0
                    return response
                response.raise_for_status()
            except (httpx.TransportError,httpx.HTTPStatusError) as error:
                if not safe: raise
                self.failures[host]=self.failures.get(host,0)+1
                if self.failures[host]>=5: self.opened_until[host]=max(self.opened_until.get(host,0),time.monotonic()+30)
                if attempt==2 or self.opened_until.get(host,0)>time.monotonic():
                    raise RuntimeError('Provider unavailable: '+host+' ('+type(error).__name__+')') from None
                await asyncio.sleep(.25*2**attempt+random.random()*.1)
