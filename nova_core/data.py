"""DEX observation normalization. Receipt time is not source time or mint creation."""
import math
from dataclasses import dataclass, asdict
from typing import Any

def number(value, *, minimum=None):
    if value is None or isinstance(value,bool): return None
    try: result=float(value)
    except (ValueError,TypeError): return None
    if not math.isfinite(result) or (minimum is not None and result<minimum): return None
    return result

@dataclass(frozen=True)
class Observation:
    chain: str
    mint: str
    pool: str
    venue: str
    provider: str
    received_at: float
    source_event_time: float|None
    pair_created_at: float|None
    price: float
    liquidity: float|None
    market_cap: float|None
    fdv: float|None
    volume5m: float|None
    volume1h: float|None
    change5m: float|None
    change1h: float|None
    buys5m: float|None
    sells5m: float|None
    coverage: float
    complete: bool
    def dict(self): return asdict(self)

def normalize_pair(p: dict[str,Any], now: float) -> Observation:
    if not isinstance(p,dict) or p.get('chainId')!='solana': raise ValueError('Solana pair required')
    mint=(p.get('baseToken') or {}).get('address');pool=p.get('pairAddress')
    price=number(p.get('priceUsd'),minimum=0)
    if not mint or not pool or not price: raise ValueError('Mint, pool and positive price required')
    if not math.isfinite(now) or now<=0: raise ValueError('Invalid receipt timestamp')
    created=number(p.get('pairCreatedAt'),minimum=0)
    created=created/1000 if created is not None else None
    if created is not None and created>now: raise ValueError('Future pair creation timestamp')
    vol=p.get('volume') or {};pc=p.get('priceChange') or {};tx=(p.get('txns') or {}).get('m5') or {}
    liq=number((p.get('liquidity') or {}).get('usd'),minimum=0)
    vals=[liq,number(vol.get('m5'),minimum=0),number(vol.get('h1'),minimum=0),number(pc.get('m5')),number(pc.get('h1')),number(tx.get('buys'),minimum=0),number(tx.get('sells'),minimum=0)]
    if any(v is not None and v!=int(v) for v in vals[-2:]): raise ValueError('Fractional trade count')
    return Observation('solana',str(mint),str(pool),str(p.get('dexId') or 'UNKNOWN'),'DEXSCREENER',now,None,created,price,liq,
        number(p.get('marketCap'),minimum=0),number(p.get('fdv'),minimum=0),*vals[1:],sum(v is not None for v in vals)/len(vals),all(v is not None for v in vals))
