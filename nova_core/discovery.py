"""Public PumpPortal launch discovery; no metered trades and no keys in URLs."""
import asyncio, json, random, time, hashlib
from sqlalchemy import select
from .schema import IntegrityBase
from sqlalchemy import String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
import websockets

class LaunchEvent(IntegrityBase):
    __tablename__='nova_launch_events'
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    mint:Mapped[str]=mapped_column(String(120),index=True)
    received_at:Mapped[float]=mapped_column(Float,index=True)
    payload:Mapped[str]=mapped_column(Text)

class PublicDiscovery:
    def __init__(self,core):
        self.c=core;self.queue=asyncio.Queue(maxsize=256)
        self.health={'status':'STOPPED','last_received':None,'events':0,'duplicates':0,'gaps':0,'overflows':0}
    def store_event(self,event,received):
        c=self.c
        if not isinstance(event,dict) or not event.get('mint') or not event.get('signature'):return False
        if event.get('txType') not in ('create',):return False
        key=hashlib.sha256(('pumpportal:'+str(event['signature'])+':'+str(event['mint'])).encode()).hexdigest()
        safe={k:event.get(k) for k in ('mint','signature','name','symbol','traderPublicKey','txType','uri')}
        safe.update(provider='PumpPortal',chain='solana',source_event_time=None,slot=None,commitment=None,stage='NEW_LAUNCH')
        @c.account_transaction
        def write():
            with c.SessionLocal() as s:
                if s.get(LaunchEvent,key):return False
                s.add(LaunchEvent(key=key,mint=str(event['mint']),received_at=received,payload=json.dumps(safe,allow_nan=False)))
                s.query(LaunchEvent).filter(LaunchEvent.received_at<received-86400).delete(synchronize_session=False)
                return True
        fresh=write()
        self.health['events' if fresh else 'duplicates']+=1
        return fresh
    def recent(self,limit=80):
        with self.c.SessionLocal() as s:
            rows=s.scalars(select(LaunchEvent).order_by(LaunchEvent.received_at.desc()).limit(limit)).all()
        return [{**json.loads(x.payload),'received_at':x.received_at} for x in rows]
    async def consume(self):
        while True:
            event,received=await self.queue.get()
            try:self.store_event(event,received)
            except Exception:self.health.update(status='DATABASE_ERROR')
            finally:self.queue.task_done()
    async def run(self):
        worker=asyncio.create_task(self.consume());backoff=1
        try:
            while True:
                try:
                    self.health['status']='CONNECTING'
                    async with websockets.connect('wss://pumpportal.fun/api/data',ping_interval=20,ping_timeout=20,close_timeout=5,max_size=65536,max_queue=32) as ws:
                        await ws.send(json.dumps({'method':'subscribeNewToken'}))
                        self.health['status']='CONNECTED';backoff=1
                        async for raw in ws:
                            try:event=json.loads(raw)
                            except (ValueError,TypeError):continue
                            now=time.time();self.health['last_received']=now
                            if self.queue.full():self.health['overflows']+=1
                            await self.queue.put((event,now))
                except asyncio.CancelledError:raise
                except Exception as e:
                    self.health.update(status='DISCONNECTED',last_error=type(e).__name__)
                    self.health['gaps']+=1
                    await asyncio.sleep(backoff+random.random());backoff=min(30,backoff*2)
        finally:
            worker.cancel();await asyncio.gather(worker,return_exceptions=True)
            self.health['status']='STOPPED'
