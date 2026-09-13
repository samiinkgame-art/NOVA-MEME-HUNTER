from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

VERSION = "NOVA MEME HUNTER — MANUS V1.0.0"
LIVE_EXECUTION_LOCKED = True
MAJORS = {"BTC", "ETH", "SOL", "BNB"}
STABLES = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "PYUSD"}

@dataclass
class Candidate:
    symbol: str
    source: str = "synthetic"
    chain: str = "Solana"
    price: float = 1.0
    price_1m: float = 0.0
    price_5m: float = 0.0
    price_15m: float = 0.0
    buy_pressure: float = 0.5
    unique_buyers: int = 0
    buyer_growth: float = 0.0
    trade_acceleration: float = 0.0
    volume_acceleration: float = 0.0
    liquidity_acceleration: float = 0.0
    transaction_velocity: float = 0.0
    volatility: float = 0.0
    momentum_consistency: float = 0.0
    range_compression: float = 0.0
    liquidity_usd: float = 0.0
    market_cap: float = 0.0
    token_age_minutes: float = 1000.0
    pair_age_minutes: float = 1000.0
    buyer_concentration: float = 0.0
    creator_selling: bool = False
    security_quality: float = 70.0
    spread_bps: float = 80.0
    estimated_slippage_bps: float = 80.0
    events: int = 0

    def normalized(self) -> dict[str, Any]:
        return self.__dict__.copy()


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def is_rejected_asset(symbol: str) -> bool:
    s = symbol.upper().replace("W", "", 1) if symbol.upper().startswith("W") else symbol.upper()
    return s in MAJORS or s in STABLES or any(x in s for x in ("USD", "USDT", "USDC", "WBTC", "WETH", "WSOL"))


def pre_move_score(c: Candidate) -> float:
    momentum = clamp((c.price_1m * 2 + c.price_5m + c.price_15m * 0.5) * 180)
    flow = clamp(c.buy_pressure * 45 + min(c.unique_buyers, 50) * 0.6 + c.buyer_growth * 20)
    acceleration = clamp((c.trade_acceleration + c.volume_acceleration + c.liquidity_acceleration) * 10)
    structure = clamp(c.momentum_consistency * 35 + c.range_compression * 25 + min(c.transaction_velocity, 10) * 4)
    return round(clamp(momentum * .25 + flow * .35 + acceleration * .2 + structure * .2), 2)


def chase_score(c: Candidate) -> float:
    extension = clamp(max(c.price_1m * 8, c.price_5m * 3, c.price_15m * 1.5) * 100)
    climax = clamp(c.volatility * 60 + max(0, c.volume_acceleration - 3) * 12)
    weakening = clamp((1 - c.buy_pressure) * 100 + max(0, c.buyer_growth * -20))
    return round(clamp(extension * .5 + climax * .25 + weakening * .25), 2)


def launch_score(c: Candidate) -> float:
    if c.token_age_minutes > 180 or c.events < 5 or c.unique_buyers < 4:
        return round(clamp(c.events * 3 + c.unique_buyers * 2), 2)
    return round(clamp(c.buy_pressure * 45 + min(c.unique_buyers, 40) * 1.1 + min(c.events, 100) * .2 + c.transaction_velocity * 2 - c.buyer_concentration * 25 - (35 if c.creator_selling else 0)), 2)


def scores(c: Candidate) -> dict[str, float]:
    pre = pre_move_score(c); chase = chase_score(c)
    flow = clamp(c.buy_pressure * 55 + c.buyer_growth * 15 + c.transaction_velocity * 3)
    liquidity = clamp(c.liquidity_usd / 1500 + c.liquidity_acceleration * 8)
    market = clamp(c.market_cap / 10000 + c.volume_acceleration * 8 + c.momentum_consistency * 15)
    security = clamp(c.security_quality)
    execution = clamp(100 - (c.spread_bps + c.estimated_slippage_bps) / 8)
    creator = 100.0 if c.creator_selling else 0.0
    concentration = clamp(c.buyer_concentration * 100)
    launch = launch_score(c) if c.token_age_minutes <= 180 else 0.0
    apex = clamp(pre*.25 + flow*.20 + liquidity*.15 + market*.12 + security*.12 + execution*.16 - chase*.22 - creator*.18 - concentration*.10)
    state = "WATCH"
    if is_rejected_asset(c.symbol): state = "BLOCKED"
    elif c.creator_selling: state = "BLOCKED"
    elif c.liquidity_usd < 500: state = "BLOCKED"
    elif chase >= 70: state = "BLOCKED"
    elif apex >= 72 and (c.token_age_minutes > 15 or launch >= 45): state = "ENTRY"
    elif pre >= 55: state = "ACCUMULATING"
    return {"pre_move": pre, "chase": chase, "flow": round(flow,2), "liquidity": round(liquidity,2), "market": round(market,2), "security": security, "execution": round(execution,2), "creator_risk": creator, "concentration_risk": round(concentration,2), "launch": launch, "apex": round(apex,2), "state": state, "block_reason": block_reason(c, chase, execution)}


def block_reason(c: Candidate, chase: float | None = None, execution: float | None = None) -> str | None:
    if is_rejected_asset(c.symbol): return "Major asset or stablecoin filter"
    if c.creator_selling: return "Creator selling detected"
    if c.liquidity_usd < 500: return "Liquidity insufficient"
    chase = chase if chase is not None else chase_score(c)
    if chase >= 70: return "Chase risk too high"
    execution = execution if execution is not None else clamp(100 - (c.spread_bps + c.estimated_slippage_bps)/8)
    if execution < 45: return "Execution cost too high"
    if c.security_quality < 45: return "Security quality too low"
    return None

@dataclass
class RiskConfig:
    starting_balance: float = 5000.0
    risk_fraction: float = .003
    launch_risk_fraction: float = .0015
    max_positions: int = 2
    daily_loss_fraction: float = .025

class RiskEngine:
    def __init__(self, cfg: RiskConfig | None = None):
        self.cfg = cfg or RiskConfig()
        self.daily_pnl = 0.0
        self.loss_streak = 0
    def risk_fraction(self, launch=False) -> float:
        base = self.cfg.launch_risk_fraction if launch else self.cfg.risk_fraction
        return base * (0.75 ** min(self.loss_streak, 3))
    def position_size(self, equity: float, entry: float, stop: float, launch=False) -> float:
        if entry <= 0 or stop <= 0 or entry <= stop: return 0.0
        risk_dollars = equity * self.risk_fraction(launch)
        return round(risk_dollars / (entry - stop), 8)
    def can_trade(self, open_positions: int) -> bool:
        return open_positions < self.cfg.max_positions and self.daily_pnl > -(self.cfg.starting_balance * self.cfg.daily_loss_fraction)

@dataclass
class Trade:
    token: str; strategy: str; entry_price: float; size: float; entry_score: float; opened_at: float = field(default_factory=time.time)
    exit_price: float | None = None; net_pnl: float | None = None; fees: float = 0.0; slippage: float = 0.0; exit_reason: str | None = None

class PaperExecutor:
    def __init__(self): self.positions: list[Trade] = []; self.closed: list[Trade] = []
    def enter(self, c: Candidate, strategy: str, score: float, risk: RiskEngine, equity: float, stop_pct=.04) -> Trade:
        cost = (c.spread_bps + c.estimated_slippage_bps) / 10000
        price = c.price * (1 + cost)
        size = risk.position_size(equity, price, price*(1-stop_pct), strategy == "LAUNCH_SNIPER")
        t = Trade(c.symbol, strategy, price, size, score, fees=price*size*.003, slippage=price*size*cost)
        self.positions.append(t); return t
    def exit(self, t: Trade, price: float, reason: str) -> Trade:
        if t not in self.positions: raise ValueError("position is not open")
        exit_cost = t.entry_price * .002
        t.exit_price = price * (1 - .002); t.exit_reason = reason
        t.net_pnl = (t.exit_price - t.entry_price) * t.size - t.fees - t.slippage - exit_cost*t.size
        self.positions.remove(t); self.closed.append(t); return t

class EdgeGovernor:
    def __init__(self): self.stats = {s: {"samples":0,"wins":0,"gross_profit":0.0,"gross_loss":0.0,"loss_streak":0,"state":"LEARNING"} for s in ("SCALP_LONG","PUMP_LONG","SNIPER_LONG","LAUNCH_SNIPER")}
    def record(self, strategy: str, pnl: float):
        x=self.stats[strategy]; x["samples"]+=1
        if pnl >= 0: x["wins"]+=1; x["gross_profit"]+=pnl; x["loss_streak"]=0
        else: x["gross_loss"]+=abs(pnl); x["loss_streak"]+=1
        if x["samples"] >= 10 and x["gross_loss"] and x["gross_profit"]/x["gross_loss"] < .8: x["state"]="CAUTION"
        elif x["samples"] >= 5: x["state"]="ENABLED"
    def view(self):
        out={}
        for k,x in self.stats.items():
            out[k]={**x,"win_rate":round(x["wins"]/x["samples"]*100,2) if x["samples"] else 0,"profit_factor":round(x["gross_profit"]/x["gross_loss"],3) if x["gross_loss"] else None,"expectancy":round((x["gross_profit"]-x["gross_loss"])/x["samples"],4) if x["samples"] else 0}
        return out

class Diagnostics:
    def __init__(self): self.started=False; self.events=0; self.trade_events=0; self.buy=0; self.sell=0; self.create=0; self.last_event_at=None; self.attempts=0; self.subscription_errors=0; self.mode="DISCONNECTED"
    def view(self):
        age = None if self.last_event_at is None else round(time.time()-self.last_event_at,1)
        mode = "FULL REALTIME" if self.started and age is not None and age < 30 else self.mode
        return {"provider":"PumpPortal","http_status":None,"feed_mode":mode,"attempts":self.attempts,"last_event_age_seconds":age,"events_received":self.events,"trade_events":self.trade_events,"buy_count":self.buy,"sell_count":self.sell,"create_count":self.create,"subscriptions":[],"subscription_errors":self.subscription_errors,"retry_timer_seconds":0}

app=FastAPI(title=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS","*").split(","), allow_methods=["*"], allow_headers=["*"])
risk=RiskEngine(); executor=PaperExecutor(); governor=EdgeGovernor(); diagnostics=Diagnostics(); candidates: list[Candidate]=[]; running=False

class CandidateIn(BaseModel):
    symbol: str; price: float=1; source: str="manual"; chain: str="Solana"; price_1m: float=0; price_5m: float=0; price_15m: float=0; buy_pressure: float=.5; unique_buyers: int=0; buyer_growth: float=0; trade_acceleration: float=0; volume_acceleration: float=0; liquidity_acceleration: float=0; transaction_velocity: float=0; volatility: float=0; momentum_consistency: float=0; range_compression: float=0; liquidity_usd: float=0; market_cap: float=0; token_age_minutes: float=1000; pair_age_minutes: float=1000; buyer_concentration: float=0; creator_selling: bool=False; security_quality: float=70; spread_bps: float=80; estimated_slippage_bps: float=80; events: int=0

def auth(key: str | None):
    expected=os.getenv("NOVA_ADMIN_KEY")
    if not expected or key != expected: raise HTTPException(401,"admin authentication required")

def snapshot():
    ss=[{"symbol":c.symbol,"source":c.source,"chain":c.chain,"strategy":"LAUNCH_SNIPER" if c.token_age_minutes<=180 else "SNIPER_LONG",**scores(c),"age_minutes":c.token_age_minutes} for c in candidates]
    return sorted(ss,key=lambda x:x["apex"],reverse=True)

@app.get("/", response_class=HTMLResponse)
def root(): return "<h1>NOVA MEME HUNTER — MANUS V1.0.0</h1><p>PAPER / SHADOW ONLY — LIVE LOCKED</p>"
@app.get("/health")
def health(): return {"version":VERSION,"status":"ok","live_execution_locked":LIVE_EXECUTION_LOCKED,"mode":"PAPER / SHADOW"}
@app.get("/api/signals")
def signals(): return {"items":snapshot()}
@app.get("/api/positions")
def positions(): return {"items":[t.__dict__ for t in executor.positions]}
@app.get("/api/trades")
def trades(): return {"items":[t.__dict__ for t in executor.closed]}
@app.get("/api/realtime-diagnostics")
def realtime(): return diagnostics.view()
@app.get("/api/strategy-performance")
def strat_perf(): return governor.view()
@app.get("/api/performance")
def performance():
    pnls=[t.net_pnl or 0 for t in executor.closed]; wins=[p for p in pnls if p>=0]; losses=[abs(p) for p in pnls if p<0]; gp=sum(wins); gl=sum(losses)
    return {"equity":risk.cfg.starting_balance+sum(pnls),"total_net_pnl":sum(pnls),"today_pnl":risk.daily_pnl,"open_positions":len(executor.positions),"closed_trades":len(pnls),"win_rate":len(wins)/len(pnls)*100 if pnls else 0,"profit_factor":gp/gl if gl else None,"expectancy":sum(pnls)/len(pnls) if pnls else 0,"average_win":sum(wins)/len(wins) if wins else 0,"average_loss":sum(losses)/len(losses) if losses else 0,"max_drawdown":0,"loss_streak":risk.loss_streak}
@app.get("/api/dashboard")
def dashboard(): return {"version":VERSION,"live_locked":LIVE_EXECUTION_LOCKED,"mode":"PAPER / SHADOW","signals":snapshot()[:10],"positions":positions()["items"],"performance":performance(),"strategies":governor.view(),"diagnostics":diagnostics.view()}
@app.post("/api/candidates")
def add_candidate(item: CandidateIn, x_nova_key: str | None = Header(default=None)):
    auth(x_nova_key); c=Candidate(**item.model_dump()); candidates[:]=[x for x in candidates if x.symbol != c.symbol]; candidates.append(c); diagnostics.events += 1; diagnostics.last_event_at=time.time(); return {"candidate":c.normalized(),"scores":scores(c)}
@app.post("/api/start")
def start(x_nova_key: str | None = Header(default=None)):
    auth(x_nova_key); global running; running=True; diagnostics.started=True; diagnostics.mode="PAPER / SHADOW"; return {"running":running,"mode":"PAPER / SHADOW","live_locked":LIVE_EXECUTION_LOCKED}
@app.post("/api/stop")
def stop(x_nova_key: str | None = Header(default=None)):
    auth(x_nova_key); global running; running=False; diagnostics.started=False; diagnostics.mode="STOPPED"; return {"running":running}
@app.post("/api/kill")
def kill(x_nova_key: str | None = Header(default=None)):
    auth(x_nova_key); global running; running=False; diagnostics.started=False; diagnostics.mode="KILLED"; return {"running":False,"positions_closed":0,"live_locked":LIVE_EXECUTION_LOCKED}
@app.post("/api/reset-paper")
def reset(x_nova_key: str | None = Header(default=None)):
    auth(x_nova_key); executor.positions.clear(); executor.closed.clear(); candidates.clear(); risk.daily_pnl=0; risk.loss_streak=0; return {"reset":True}

async def provider_worker():
    while True:
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup():
    app.state.worker=asyncio.create_task(provider_worker())
@app.on_event("shutdown")
async def shutdown():
    task=getattr(app.state,"worker",None)
    if task: task.cancel()
