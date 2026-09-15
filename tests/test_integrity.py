"""Deterministic fixtures only. No real trades, wallets, or provider claims."""
import asyncio,json,time,os,subprocess,sys
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import pytest,httpx
from sqlalchemy import select,func
from test_release import nova,candidate,clean_account,setup_accounting,position,client,headers
from nova_core.money import dec,settle,size
from nova_core.data import normalize_pair
from nova_core.risk import update_periods,assess_periods
from nova_core.auth import validate_key,RateLimiter
from nova_core.schema import Ledger,ExactPosition,Intent,TokenObservation
from nova_core.backtest import Bar,run,walk_forward,monte_carlo
from nova_core.discovery import LaunchEvent

def healthy():
    c=candidate();nova.runtime['candidates']=[c]
    nova.runtime['loop_alive']=True
    nova.runtime['last_successful_loop']=datetime.now(timezone.utc).isoformat()
    nova.runtime['engine_error_streak']=0
    nova.setv('bot_enabled','true');nova.setv('max_execution_cost_bps','120')
    return c

def raw_pair():
    return {'chainId':'solana','pairAddress':'fixture-pool','dexId':'raydium','baseToken':{'address':candidate()['mint'],'symbol':'TEST','name':'Fixture'},'priceUsd':'1.5','liquidity':{'usd':1000000},'volume':{'m5':25000,'h1':80000},'txns':{'m5':{'buys':150,'sells':30}},'priceChange':{'m5':2,'h1':6},'marketCap':2000000,'fdv':2500000,'pairCreatedAt':(time.time()-3600)*1000}

@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'bad'])
def test_money_rejects_invalid(value):
    with pytest.raises(ValueError):dec(value)

def test_fee_is_based_on_executed_sale_value():
    r=settle('2.5','10','20','30')
    assert r.gross==Decimal('50');assert r.fee==Decimal('.15');assert r.pnl==Decimal('24.85')

def test_sizing_counts_costs_and_remaining_exposure():
    a=size(1000,1000,190,.01,.05,.01,.1,.2,10000)
    assert a==10
    assert size(1000,1000,200,.01,.05,.01,.1,.2,10000)==0
    assert size(1000,1000,0,.01,.05,.01,.9,.9,10000)<size(1000,1000,0,.01,.05,0,.9,.9,10000)

@pytest.mark.parametrize('field,value',[('priceUsd','NaN'),('priceUsd','0'),('priceUsd','-1'),('pairCreatedAt',9999999999999)])
def test_bad_pair_rejected(field,value):
    p=raw_pair();p[field]=value
    with pytest.raises(ValueError):normalize_pair(p,time.time())

def test_timeframe_and_marketcap_not_fabricated():
    p=raw_pair();del p['volume']['h1'];del p['marketCap']
    o=normalize_pair(p,time.time())
    assert o.volume1h is None and o.volume5m==25000 and o.market_cap is None and o.fdv==2500000
    assert not o.complete

def test_first_seen_persistent_and_older_observation_ignored():
    p=raw_pair();now=time.time();first=nova.integrity.observation(normalize_pair(p,now))
    assert nova.integrity.observation(normalize_pair(p,now+1))==first
    nova.integrity.observation(normalize_pair(p,now-.5))
    with nova.SessionLocal() as s:
        row=s.get(TokenObservation,p['baseToken']['address']);assert row.first_seen==now and row.received_at==now+1
    nova.integrity.recover()
    with nova.SessionLocal() as s:assert s.get(TokenObservation,p['baseToken']['address']).first_seen==first

def test_research_baseline_is_integrated_with_real_timeframes():
    c=healthy();o=normalize_pair(raw_pair(),time.time());nova.integrity.observation(o);c['observation']=o.dict()
    token=nova.mobile.candidate(c)
    assert token['volume1h']==80000 and token['volume5m']==25000
    assert token['decision']['model_version']=='research-market-v1'
    assert token['decision']['nova_score'] is None
    assert token['decision']['components']['liquidity'] is not None

def test_full_strategy_risk_entry_partial_exit_final_exit():
    # Real V7 gate + sizing + execution + database. No gate or strategy mocks.
    c=healthy();ok,why=nova.gate(c,'PUMP_LONG');assert ok,why
    start=dec(nova.getv('cash'));assert nova.open_position(c,'PUMP_LONG')[0]
    p=position();c['price']=1.03
    nova.partial_sell(p,c,.2,request_id='test-full-tp1')
    assert nova.integrity.reconcile()['ok']
    c['price']=1.06;nova.close_position(p,c,'TEST_FINAL')
    assert nova.integrity.reconcile()['ok']
    with nova.SessionLocal() as s:
        trade=s.scalar(select(nova.Trade));assert float(dec(nova.getv('cash'))-start)==pytest.approx(trade.pnl)
        assert s.scalar(select(func.count(Ledger.id)))==3
        assert s.scalar(select(ExactPosition)).closed==1

def test_duplicate_partial_and_final_no_double_credit(monkeypatch):
    c=setup_accounting(monkeypatch);nova.open_position(c,'PUMP_LONG');p=position();c['price']=1.1
    nova.partial_sell(p,c,.25,request_id='stable-exit-key');cash=nova.getv('cash')
    nova.partial_sell(p,c,.25,request_id='stable-exit-key');assert nova.getv('cash')==cash
    nova.close_position(p,c,'END');cash=nova.getv('cash')
    nova.partial_sell(p,c,.25,request_id='another-exit-key');nova.close_position(p,c,'RETRY')
    assert nova.getv('cash')==cash and nova.integrity.reconcile()['ok']

def test_position_ids_not_reused_after_last_position_closed(monkeypatch):
    c=setup_accounting(monkeypatch);nova.open_position(c,'PUMP_LONG');p=position();old=p.id;nova.close_position(p,c,'END')
    nova.open_position(c,'PUMP_LONG');assert position().id>old
    assert nova.integrity.reconcile()['ok']

def test_idempotent_http_open_and_conflicting_key():
    c=healthy();auth={'Authorization':'Bearer '+os.environ['NOVA_ADMIN_KEY']}
    csrf=client.get('/api/session',headers=auth).json()['csrf'];h={**auth,'X-Nova-CSRF':csrf}
    body={'mint':c['mint'],'request_id':'request-stable-0001','acknowledgement':'RESEARCH_ONLY_UNKNOWN_SECURITY'}
    one=client.post('/api/paper/open',headers=h,json=body);assert one.status_code==200,one.text
    cash=nova.getv('cash');two=client.post('/api/paper/open',headers=h,json=body)
    assert one.json()==two.json() and cash==nova.getv('cash')
    body['mint']='different';assert client.post('/api/paper/open',headers=h,json=body).status_code==409
    close={'position_id':one.json()['id']}
    assert client.post('/api/paper/close',headers=h,json=close).status_code==200
    cash=nova.getv('cash');assert client.post('/api/paper/close',headers=h,json=close).status_code==200
    assert cash==nova.getv('cash')

def test_concurrent_same_intent_executes_once():
    calls=[]
    def action():calls.append(1);return {'value':1}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda _:nova.integrity.request('concurrent-request',{'mint':'fixture'},action),range(6)))
    assert len(calls)==1 and all(x=={'value':1} for x in results)

def test_kill_survives_recovery_start_does_not_clear_it():
    healthy();nova.setv('killed','true');nova.integrity.recover()
    assert nova.b('killed') and not nova.b('bot_enabled')
    assert client.post('/api/control/start',headers=headers).status_code==409

def test_reconciliation_catches_cash_corruption_and_stops_restart():
    nova.setv('cash',nova.f('cash')+1)
    assert not nova.integrity.reconcile()['ok']
    nova.integrity.recover();assert nova.b('killed') and nova.getv('recovery_ok')=='false'

def test_exact_exit_fee_audit_and_database_atomicity(monkeypatch):
    c=setup_accounting(monkeypatch);nova.open_position(c,'PUMP_LONG');p=position();c['price']=2
    start=nova.getv('cash')
    def fail(*a,**kw):raise RuntimeError('fixture failure before transaction commit')
    monkeypatch.setattr(nova,'record_execution_event',fail)
    with pytest.raises(RuntimeError):nova.close_position(p,c,'END')
    assert nova.getv('cash')==start and position() is not None and nova.integrity.reconcile()['ok']

@pytest.mark.parametrize('daily,weekly,dd,expected',[(.01,.5,.5,'daily'),(.5,.01,.5,'weekly'),(.5,.5,.01,'drawdown')])
def test_period_losses(daily,weekly,dd,expected):
    state=update_periods({},1000,1700000000)
    assert any(expected in s for s in assess_periods(state,980,daily,weekly,dd))

def test_week_boundary_and_peak_persistence():
    a=update_periods({},1000,datetime(2026,9,13,23,59,tzinfo=timezone.utc).timestamp())
    b=update_periods(a,900,datetime(2026,9,14,0,1,tzinfo=timezone.utc).timestamp())
    assert b['week_start']=='900' and b['day_start']=='900' and b['peak']=='1000'

def test_weekly_limit_really_blocks_gate():
    c=healthy();s=update_periods({},nova.f('cash'),time.time());s['week_start']=str(nova.f('cash')*1.5)
    nova.setv('equity_periods',json.dumps(s))
    assert 'weekly' in nova.gate(c,'PUMP_LONG')[1]

def test_stale_existing_position_blocks_second_entry():
    c=healthy();nova.open_position(c,'PUMP_LONG');c['received_at']=time.time()-200
    second={**candidate(),'mint':'another-test-mint'}
    assert 'stale' in nova.gate(second,'PUMP_LONG')[1]

def test_liquidity_collapse_does_not_fill(monkeypatch):
    c=setup_accounting(monkeypatch);nova.open_position(c,'PUMP_LONG');p=position();c['liquidity']=0
    with pytest.raises(ValueError):nova.close_position(p,c,'LIQUIDITY')
    assert position() and nova.integrity.reconcile()['ok']

def test_public_stream_dedup_and_unknown_source_time():
    e={'mint':candidate()['mint'],'signature':'fixture-signature','txType':'create','symbol':'TEST'}
    assert nova.public_discovery.store_event(e,time.time())
    assert not nova.public_discovery.store_event(e,time.time())
    row=nova.public_discovery.recent()[0]
    assert row['source_event_time'] is None and row['slot'] is None
    assert nova.public_discovery.queue.maxsize==256

def test_http_post_submission_never_retried():
    calls=[]
    def handler(request):calls.append(1);raise httpx.ReadTimeout('after submission')
    async def execute():
        async with nova.ResilientClient(transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(httpx.ReadTimeout):await c.post('https://provider.invalid/send',json={'method':'sendTransaction'})
    asyncio.run(execute());assert len(calls)==1

def test_optional_key_strength():
    validate_key('');validate_key('test-only-key-123456789012345678901234567890')
    with pytest.raises(ValueError):validate_key('x'*40)

def test_liveness_readiness_separate_from_trading():
    assert client.get('/livez').status_code==200
    r=client.get('/readyz').json();assert r['ready'] and not r['trading_ready']

def test_missing_data_api_is_null_not_zero():
    nova.runtime['candidates']=[candidate()]
    response=client.get('/api/state',headers=headers).json();t=response['tokens'][0]
    assert t['volume1h'] is None and t['holders'] is None and t['first_seen'] is None
    assert response['account']['exposure']==0

def test_backend_targets_match_net_rules():
    c=healthy();nova.open_position(c,'PUMP_LONG');p=position()
    row=nova.mobile.state()['positions'][0]
    for target,price in zip(row['tp_net_pct'],row['targets']):
        assert nova.expected_exit_total_pct(p,{**c,'price':price})==pytest.approx(target,abs=1e-6)

def test_csv_backtest_input_validation_and_api():
    bars=[dict(timestamp=1700000000+i*60,open=1,high=1.1,low=.9,close=1,volume=100,liquidity=1e6) for i in range(40)]
    r=client.post('/api/backtest',headers=headers,json={'bars':bars});assert r.status_code==200,r.text
    assert not r.json()['approved_live'] and r.json()['metrics']['trades']==0
    bars[1]['timestamp']=bars[0]['timestamp'];assert client.post('/api/backtest',headers=headers,json={'bars':bars}).status_code==422

def test_stop_wins_ohlc_tie_next_bar_entry():
    bars=[Bar(i*60,100,101,99,100,100,1e6) for i in range(6)]
    bars+=[Bar(360,100,105,99,104,1000,1e6),Bar(420,104,150,50,110,200,1e6)]
    result=run(bars,lookback=3)
    assert result['trades'][0]['opened_at']==420
    assert result['trades'][0]['reason']=='STOP'
    assert result['trades'][0]['pnl']<0

def test_monte_carlo_reproducible_not_live_validation():
    assert monte_carlo([10,-20,5],iterations=50)==monte_carlo([10,-20,5],iterations=50)
    assert monte_carlo([])['available'] is False

def test_sqlite_account_lock_serializes_processes():
    # Separate OS processes share this fixture database; no provider or order calls.
    nova.setv('process_lock_test','0')
    code="""import app
@app.account_transaction
def increment():
    app.setv('process_lock_test',str(int(app.getv('process_lock_test','0'))+1))
for _ in range(15):increment()
"""
    workers=[subprocess.Popen([sys.executable,'-c',code],cwd=os.path.dirname(nova.__file__),env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(3)]
    for worker in workers:
        stdout,stderr=worker.communicate(timeout=25)
        assert worker.returncode==0,stderr.decode()
    assert nova.getv('process_lock_test')=='45'

def test_walkforward_uses_requested_costs(monkeypatch):
    import nova_core.backtest as bt
    seen=[]
    original=bt.run
    def recorded(*args,**kwargs):
        seen.append((kwargs['fee_bps'],kwargs['slippage_bps']))
        return original(*args,**kwargs)
    monkeypatch.setattr(bt,'run',recorded)
    bars=[Bar(1700000000+i*60,1,1.1,.9,1,100,1e6) for i in range(240)]
    bt.walk_forward(bars,fee_bps=17,slippage_bps=29)
    assert seen and set(seen)=={(17,29)}

def test_metered_connection_cannot_be_enabled_accidentally():
    with pytest.raises(RuntimeError,match='not integrated'):
        asyncio.run(nova.pumpportal_realtime_loop())
