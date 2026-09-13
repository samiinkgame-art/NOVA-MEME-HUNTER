from __future__ import annotations
import asyncio, json, time
from typing import Any
import httpx

class ProviderHealth:
    def __init__(self, name: str):
        self.name=name; self.attempts=0; self.events=0; self.errors=0; self.last_event_at=None; self.subscriptions=[]
    def view(self):
        age=None if self.last_event_at is None else time.time()-self.last_event_at
        return {"provider":self.name,"attempts":self.attempts,"events":self.events,"errors":self.errors,"last_event_age_seconds":age,"subscriptions":self.subscriptions}

class DexScreenerClient:
    base="https://api.dexscreener.com"
    async def search(self, query: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            r=await client.get(f"{self.base}/latest/dex/search",params={"q":query}); r.raise_for_status(); return r.json()

class BinanceClient:
    base="https://api.binance.com"
    async def ticker(self, symbol: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            r=await client.get(f"{self.base}/api/v3/ticker/24hr",params={"symbol":symbol}); r.raise_for_status(); return r.json()

class PumpPortalStream:
    url="wss://pumpportal.fun/api/data"
    def __init__(self, api_key: str|None=None): self.api_key=api_key; self.health=ProviderHealth("PumpPortal")
    async def run(self, on_event, stop: asyncio.Event):
        try:
            import websockets
        except ImportError: return
        backoff=1
        while not stop.is_set():
            self.health.attempts += 1
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=10, close_timeout=5) as ws:
                    await ws.send(json.dumps({"method":"subscribeNewToken"})); self.health.subscriptions=["subscribeNewToken"]; backoff=1
                    while not stop.is_set():
                        try: raw=await asyncio.wait_for(ws.recv(), timeout=35)
                        except asyncio.TimeoutError: await ws.ping(); continue
                        event=json.loads(raw); self.health.events+=1; self.health.last_event_at=time.time(); await on_event(event)
            except asyncio.CancelledError: raise
            except Exception:
                self.health.errors += 1
                await asyncio.sleep(backoff); backoff=min(backoff*2,60)
            
