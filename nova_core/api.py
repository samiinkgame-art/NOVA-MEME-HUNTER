"""Mobile API uses the same account and actual engine thresholds."""
import time, json, math
from datetime import datetime, timezone
from sqlalchemy import select, text
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from .schema import ExactPosition, TokenObservation
from .data import number
from .research import evaluate
from .backtest import Bar, run, walk_forward, monte_carlo

class BacktestInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    bars: list[dict[str,float]]=Field(min_length=30,max_length=2000)
    lookback:int=Field(default=20,ge=2,le=100)
    strategy:str='breakout'
    fee_bps:float=Field(default=30,ge=0,le=1000,allow_inf_nan=False)
    slippage_bps:float=Field(default=50,ge=0,le=1000,allow_inf_nan=False)
    walk_forward:bool=False

def safe(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    return value

class MobileAPI:
    def __init__(self,core):self.c=core
    def candidate(self,c):
        core=self.c;o=c.get('observation') or {}
        decision=evaluate(c,time.time(),core.f('min_liquidity'),core.f('max_data_age_sec'))
        with core.SessionLocal() as session:
            stored=session.get(TokenObservation,c['mint']);first=stored.first_seen if stored else c.get('first_seen')
        return {'mint':c['mint'],'symbol':c.get('symbol','?'),'pair':o.get('pool',c.get('pair_address')),
            'source':c.get('data_source','UNKNOWN'),'venue':o.get('venue',c.get('dex')),
            'price':number(c.get('price'),minimum=0),'market_cap':o.get('market_cap'),'fdv':o.get('fdv'),
            'liquidity':o.get('liquidity',number(c.get('liquidity'),minimum=0)),
            'volume5m':o.get('volume5m'),'volume1h':o.get('volume1h'),'change5m':o.get('change5m'),'change1h':o.get('change1h'),
            'received_at':c.get('received_at'),'first_seen':first,'pair_created_at':o.get('pair_created_at'),
            'token_created_at':None,'source_event_time':o.get('source_event_time'),'discovery_latency_ms':None,
            'stale':not core.valid_market_mark(c),'decision':decision,
            'v7_scores':{k:c.get(k) for k in ('pump_score','scalp_score','sniper_score','apex_score')},
            'security':c.get('security') or {'status':'UNKNOWN','score':None},
            'holders':None,'smart_money':None,'developer_score':None,'rug_score':None}
    def threshold_price(self,p,c,target):
        if p.remaining_cost<=0:return None
        low,high=1e-15,p.entry_price*100
        if self.c.expected_exit_total_pct(p,{**c,'price':high})<target:return None
        for _ in range(48):
            mid=(low+high)/2
            if self.c.expected_exit_total_pct(p,{**c,'price':mid})<target:low=mid
            else:high=mid
        return high
    def state(self):
        c=self.c;marks={x['mint']:x for x in c.runtime['candidates']};rows=[]
        with c.SessionLocal() as s:
            for p in s.scalars(select(c.Position).order_by(c.Position.id)).all():
                mark=marks.get(p.mint,{});fresh=c.valid_market_mark(mark);exact=s.get(ExactPosition,p.id);plan=c.strategy_tp_plan(p.strategy)
                rows.append({'id':str(p.id),'mint':p.mint,'symbol':p.symbol,'strategy':p.strategy,'mode':'paper','direction':'LONG','entry':p.entry_price,
                    'mark':mark.get('price',p.last_price),'mark_at':mark.get('received_at') if fresh else (exact.mark_at if exact else None),'stale':not fresh,
                    'quantity':float(exact.quantity) if exact else p.remaining_cost/p.entry_price,
                    'remaining_cost':exact.cost if exact else str(p.remaining_cost),'realized_pnl':float(exact.realized) if exact else p.locked_pnl,
                    'entry_fee':exact.entry_fee if exact and exact.origin!='LEGACY_FLOAT_IMPORT' else None,
                    'accounting_origin':exact.origin if exact else 'UNRECONCILED',
                    'stop_net_pct':-c.strategy_max_loss_pct(p.strategy),'tp_net_pct':[x[0] for x in plan],'tp_fractions':[x[1] for x in plan],
                    'stop':self.threshold_price(p,mark,-c.strategy_max_loss_pct(p.strategy)) if fresh else None,
                    'targets':[self.threshold_price(p,mark,x[0]) for x in plan] if fresh else [None]*3,
                    'tp_done':[p.tp1,p.tp2,p.tp3],'reason':'V7 rules + Decimal settlement',
                    'threshold_note':'Indicative reference price from current cost model; actual exits use total net PnL.'})
            trades=s.scalars(select(c.Trade).order_by(c.Trade.id.desc()).limit(100)).all()
            closed=[{'id':str(t.id),'mint':t.mint,'symbol':t.symbol,'strategy':t.strategy,'realized_pnl':t.pnl,'closed_at':c._compat_time(t.closed_at),'exit_reason':t.reason} for t in trades]
        m=c.metrics();h=c.source_health();periods=json.loads(c.getv('equity_periods','{}'))
        with c.SessionLocal() as s:s.execute(text('SELECT 1'))
        health={**h,'fresh':h['last_loop_age_sec']<=c.f('max_data_age_sec'),'last_success':self.timestamp(c.runtime.get('last_successful_loop')),
            'database':'OK','database_engine':c.engine.dialect.name,'last_error':str(c.runtime.get('last_error') or '')[:180],
            'pumpportal':{**c.public_discovery.health,'queue_depth':c.public_discovery.queue.qsize()},'fallback':'No guaranteed fallback','recovery_ok':c.getv('recovery_ok')=='true'}
        events=[{'kind':e.get('code','EVENT'),'created_at':self.timestamp(e.get('created_at')),'data':{'level':e.get('level'),'message':e.get('message'),'detail':e.get('detail')}} for e in c.system_events(30)]
        return safe({'api_version':'2','version':c.APP_VERSION,'mode':c.operating_mode().lower(),'engine_enabled':c.b('bot_enabled'),
            'auth_required':c.ADMIN_KEY_CONFIGURED,'controls_available':c.ADMIN_KEY_CONFIGURED,'kill':c.b('killed'),'health':health,
            'account':{'initial_cash':c.f('start_balance'),'cash':c.f('cash'),'cash_exact':c.getv('cash'),'equity':m['equity'],'pnl':m['pnl'],
                'exposure':sum(p['quantity']*p['mark'] for p in rows),'peak':number(periods.get('peak')),'equity_stale':any(p['stale'] for p in rows)},
            'positions':rows,'closed':closed,'tokens':[self.candidate(x) for x in c.runtime['candidates'][:200]],'events':events,
            'equity':[{'value':p['equity'],'created_at':self.timestamp(p['ts'])} for p in c.equity_curve(250)],
            'metrics':m,'risk_periods':periods,'limits':{k:c.f(k) for k in ('risk_pct','max_position_pct','max_total_exposure_pct','daily_loss_limit_pct','weekly_loss_limit_pct','max_positions','min_liquidity')},
            'live':{'enabled':False,'adapter_implemented':False,'reason':'No audited signer or validated live execution adapter'},
            'execution_model':'Simulated fees/spread/latency/impact; liquidity proxy is not verified route depth.',
            'validation':{'live_approved':False,'out_of_sample_passed':False,'paper_validation_passed':False},
            'launches':c.public_discovery.recent(60),'research_report':json.loads(c.getv('ohlcv_last_report','null'))})
    @staticmethod
    def timestamp(value):
        if isinstance(value,(int,float)):return value
        if not value:return None
        try:
            dt=datetime.fromisoformat(value)
            return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
        except (ValueError,TypeError):return None
    def install(self):
        c=self.c
        @c.app.get('/livez')
        def livez():return {'alive':True,'version':c.APP_VERSION}
        @c.app.get('/readyz')
        def readyz():
            try:
                with c.SessionLocal() as s:s.execute(text('SELECT 1'))
                okay=c.getv('recovery_ok')=='true'
                return JSONResponse({'ready':okay,'trading_ready':okay and c.b('bot_enabled') and c.operating_mode() in ('PAPER','SHADOW') and c.source_health()['status']=='OK' and not c.b('killed')},status_code=200 if okay else 503)
            except Exception:return JSONResponse({'ready':False,'trading_ready':False},status_code=503)
        @c.app.get('/api/reconciliation')
        def reconciliation():return c.integrity.reconcile()
        @c.app.get('/api/strategies')
        def strategies():
            return {'v7':[{'name':n,'version':'7.0.0-integrity-1','approved_live':False,'enabled':c.strategy_manual_enabled(n),'stop_net_pct':-c.strategy_max_loss_pct(n),'take_profits':c.strategy_tp_plan(n)} for n in ('PUMP_LONG','SCALP_LONG','SNIPER_LONG')],
                'research':[{'name':n,'version':'research-v1','approved_live':False} for n in ('momentum','continuation','breakout','trend')],
                'not_implemented':['Smart Money Follow','Whale Follow','Mean Reversion','Post-Graduation','Reversal','Model training registry']}
        @c.app.post('/api/backtest')
        def backtest(data:BacktestInput):
            try:
                bars=[Bar(**x) for x in data.bars]
                result=run(bars,lookback=data.lookback,strategy=data.strategy,fee_bps=data.fee_bps,slippage_bps=data.slippage_bps)
                result['monte_carlo']=monte_carlo([t['pnl'] for t in result['trades']],iterations=500)
                if data.walk_forward:result['walk_forward']=walk_forward(bars,fee_bps=data.fee_bps,slippage_bps=data.slippage_bps)
                result['provenance']='Historical NOVA research source integrated into V7 API';result['approved_live']=False
                c.setv('ohlcv_last_report',json.dumps(safe({k:v for k,v in result.items() if k not in ('equity','trades')}),allow_nan=False))
                return safe(result)
            except (ValueError,TypeError,OverflowError) as e:raise HTTPException(422,str(e))
