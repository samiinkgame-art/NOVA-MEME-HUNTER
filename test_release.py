"""Deterministic regression tests, not strategy profitability validation."""
import os
import tempfile
import asyncio
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

_temp = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + _temp.name + '/test.db'
os.environ['NOVA_ADMIN_KEY'] = 'test-only-key-123456789012345678901234567890'
os.environ['PUMPPORTAL_TRADE_STREAM_ENABLED'] = 'false'
os.environ['PUMPPORTAL_API_KEY'] = ''
import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select, func
import app as nova

client = TestClient(nova.app)
headers = {'X-NOVA-Key': os.environ['NOVA_ADMIN_KEY']}

@pytest.fixture(autouse=True)
def clean_account():
    with nova._SessionFactory.begin() as session:
        for table in reversed(nova.Base.metadata.sorted_tables):
            session.execute(table.delete())
    nova.init_defaults()
    nova.runtime['pause_until'] = None
    for key in ('cooldowns','strategy_pauses','token_security','realtime_exit_refs',
                'governor_pauses','governor_last_reason','governor_recovery','apex_feedback_cache'):
        nova.runtime[key].clear()
    nova.runtime['candidates'] = []
    nova.ResilientClient.failures.clear()
    nova.ResilientClient.opened_until.clear()

def candidate():
    return dict(mint='TestMint123456789012345678901234567890',symbol='TEST',name='Test',
                price=1.,liquidity=1_000_000.,market_cap=2_000_000.,market_risk=95,
                buy_pressure=75,m5=2.,h1=4.,h6=5.,h24=8.,volume_accel=90,
                pump_score=95,scalp_score=94,sniper_score=95,long_score=95,
                short_score=5,direction_edge=90,age_minutes=120,
                volume_m5=100_000,buys_m5=300,sells_m5=100,
                data_source='DEXSCREENER',received_at=time.time(),perp_eligible=False,
                volatility_regime='SPOT',security={'status':'PASS','score':85,'hard_block':False})

def setup_accounting(monkeypatch):
    # Isolate ledger invariants from heuristic strategy selection.
    monkeypatch.setattr(nova,'gate',lambda c,s:(True,'test ledger'))
    monkeypatch.setattr(nova,'planned_collateral',lambda c,s:100.)
    monkeypatch.setattr(nova,'arm_realtime_exit_ref',lambda *a:None)
    monkeypatch.setattr(nova,'maybe_pause_strategy',lambda *a:None)
    nova.setv('execution_simulator_enabled','true')
    nova.setv('max_execution_cost_bps','120')
    return candidate()

def position():
    with nova.SessionLocal() as session:
        return session.scalar(select(nova.Position))

def test_health_and_authenticated_dashboard():
    assert client.get('/health').json()['version'] == '1.3.0'
    assert client.get('/api/dashboard').status_code == 401
    data=client.get('/api/dashboard',headers=headers)
    assert data.status_code == 200, data.text
    for key in ('settings','metrics','universe','edge_governor','realtime_pulse','launch_sniper'):
        assert key in data.json()

@pytest.mark.parametrize('path',['/api/readiness','/api/system','/api/diagnostics/pumpportal',
    '/api/security','/api/portfolio','/api/research/status','/api/optimizer','/api/full-status'])
def test_account_endpoints_require_auth(path):
    assert client.get(path).status_code == 401

def test_unicode_auth_is_rejected_without_server_error():
    assert client.get('/api/dashboard',headers={'X-NOVA-Key':'wrong'}).status_code == 401
    with pytest.raises(nova.HTTPException) as error:
        nova.auth('کلید')
    assert error.value.status_code == 401

def test_exact_cors_origin():
    request_headers={'Origin':'https://samiinkgame-art.github.io',
                     'Access-Control-Request-Method':'POST',
                     'Access-Control-Request-Headers':'X-NOVA-Key,Content-Type'}
    result=client.options('/api/control/start',headers=request_headers)
    assert result.status_code == 200
    assert result.headers['access-control-allow-origin']==request_headers['Origin']
    request_headers['Origin']='https://attacker.invalid'
    assert client.options('/api/control/start',headers=request_headers).status_code == 400

@pytest.mark.parametrize('settings',[{'risk_pct':99},{'max_position_pct':90},
    {'max_total_exposure_pct':99},{'spot_fee_bps':-1},
    {'execution_simulator_enabled':False},{'no_martingale':False},
    {'launch_sniper_enabled':True},{'invented_setting':1}])
def test_unsafe_settings_rejected(settings):
    assert client.post('/api/settings',headers=headers,json=settings).status_code in (400,409,422)

def test_nonfinite_settings_rejected():
    assert client.post('/api/settings',headers=headers,
        content='{"risk_pct":1e999}').status_code == 422

def test_live_and_launch_locked():
    assert client.post('/api/mode/LIVE',headers=headers).status_code == 403
    assert nova.launch_gate({})[0] is False
    assert nova.LIVE_EXECUTION_LOCKED is True

@pytest.mark.parametrize('price',[0,-1,float('nan'),float('inf')])
def test_invalid_price_blocks_entry(price):
    c=candidate();c['price']=price
    assert nova.gate(c,'PUMP_LONG')[0] is False

def test_stale_price_and_security_hard_block():
    c=candidate();c['received_at']=time.time()-200
    assert 'stale' in nova.gate(c,'PUMP_LONG')[1]
    c=candidate();c['security']['hard_block']=True
    assert nova.gate(c,'PUMP_LONG')==(False,'token security hard block')

def test_kill_blocks_new_entries():
    assert client.post('/api/control/start',headers=headers).status_code == 200
    assert nova.b('bot_enabled')
    assert client.post('/api/control/kill',headers=headers).status_code == 200
    assert nova.gate(candidate(),'PUMP_LONG')==(False,'kill switch')

def test_roundtrip_ledger_and_duplicate_close(monkeypatch):
    c=setup_accounting(monkeypatch)
    start=nova.f('cash')
    assert nova.open_position(c,'PUMP_LONG')[0]
    p=position()
    assert nova.f('cash') < start-100
    c['price']=1.05
    nova.close_position(p,c,'TEST_EXIT')
    end=nova.f('cash')
    nova.close_position(p,c,'DUPLICATE_EXIT')
    assert nova.f('cash')==end
    with nova.SessionLocal() as session:
        trades=session.scalars(select(nova.Trade)).all()
        assert len(trades)==1
        assert end-start==pytest.approx(trades[0].pnl)
        assert session.scalar(select(func.count(nova.Position.id)))==0
        assert session.scalar(select(func.count(nova.ExecutionEvent.id)))==2

def test_entry_failure_rolls_back_cash_and_position(monkeypatch):
    c=setup_accounting(monkeypatch);start=nova.f('cash')
    def fail(*args,**kwargs): raise RuntimeError('injected audit-write failure')
    monkeypatch.setattr(nova,'record_execution_event',fail)
    with pytest.raises(RuntimeError): nova.open_position(c,'PUMP_LONG')
    assert nova.f('cash')==start
    assert position() is None

def test_partial_then_final_exit_reconciles(monkeypatch):
    c=setup_accounting(monkeypatch);start=nova.f('cash')
    assert nova.open_position(c,'PUMP_LONG')[0]
    p=position();c['price']=1.10
    nova.partial_sell(p,c,.25)
    assert position().remaining_cost==pytest.approx(75)
    c['price']=.98
    nova.close_position(p,c,'FINAL')
    with nova.SessionLocal() as session:
        trade=session.scalar(select(nova.Trade))
        assert nova.f('cash')-start==pytest.approx(trade.pnl)

def test_concurrent_duplicate_close_only_credits_once(monkeypatch):
    c=setup_accounting(monkeypatch);start=nova.f('cash')
    assert nova.open_position(c,'PUMP_LONG')[0]
    p=position();c['price']=1.03
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _:nova.close_position(p,c,'RETRY'),range(4)))
    with nova.SessionLocal() as session:
        trades=session.scalars(select(nova.Trade)).all()
        assert len(trades)==1
        assert nova.f('cash')-start==pytest.approx(trades[0].pnl)

def test_current_mobile_contract_round_trip(monkeypatch):
    c=setup_accounting(monkeypatch)
    nova.runtime['candidates']=[c]
    nova.runtime['loop_alive']=True
    nova.runtime['last_successful_loop']=datetime.now(timezone.utc).isoformat()
    nova.setv('bot_enabled','false');nova.setv('killed','false')
    with TestClient(nova.app) as mobile:
        auth={'Authorization':'Bearer '+os.environ['NOVA_ADMIN_KEY']}
        csrf=mobile.get('/api/session',headers=auth).json()['csrf']
        protected={**auth,'X-Nova-CSRF':csrf}
        state=mobile.get('/api/state',headers=auth)
        assert state.status_code==200 and state.json()['mode']=='paper'
        opened=mobile.post('/api/paper/open',headers=protected,json={
            'mint':c['mint'],'request_id':'mobile-contract-12345678',
            'acknowledgement':'RESEARCH_ONLY_UNKNOWN_SECURITY'})
        assert opened.status_code==200, opened.text
        closed=mobile.post('/api/paper/close',headers=protected,
                           json={'position_id':opened.json()['id']})
        assert closed.status_code==200, closed.text

def test_stale_marks_do_not_generate_fictitious_exits(monkeypatch):
    c=setup_accounting(monkeypatch)
    assert nova.open_position(c,'PUMP_LONG')[0]
    c.update(price=.01,received_at=time.time()-200)
    nova.runtime['candidates']=[c]
    nova.manage_positions()
    assert position() is not None

def test_rpc_missing_mint_data_is_unknown(monkeypatch):
    async def bad(*args): return {'value':{'owner':'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','data':{}}}
    monkeypatch.setattr(nova,'solana_rpc',bad)
    security=asyncio.run(nova.scan_token_security(None,candidate()))
    assert security['status']=='UNKNOWN'
    assert security['score'] is None

def test_token2022_is_not_claimed_safe(monkeypatch):
    async def rpc(client,method,params):
        if method=='getAccountInfo':
            return {'value':{'owner':'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb',
                'data':{'parsed':{'type':'mint','info':{'supply':'1000000',
                    'mintAuthority':None,'freezeAuthority':None}}}}}
        return {'value':[{'amount':'100'}]}
    monkeypatch.setattr(nova,'solana_rpc',rpc)
    security=asyncio.run(nova.scan_token_security(None,candidate()))
    assert security['hard_block'] is True
    assert security['coverage']=='PARTIAL'

def test_retry_then_success():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls)<2 else 200,json={'ok':True})
    async def run():
        async with nova.ResilientClient(transport=httpx.MockTransport(handler)) as c:
            assert (await c.get('https://provider.invalid/data')).status_code==200
    asyncio.run(run());assert len(calls)==2

def test_rate_limit_opens_circuit_without_repeated_requests():
    calls=[]
    def handler(request):
        calls.append(request);return httpx.Response(429,headers={'Retry-After':'30'})
    async def run():
        async with nova.ResilientClient(transport=httpx.MockTransport(handler)) as c:
            for _ in range(2):
                with pytest.raises(RuntimeError): await c.get('https://provider.invalid/data')
    asyncio.run(run());assert len(calls)==1

def test_dashboard_escapes_external_fields_and_labels_paper():
    html=(Path(__file__).resolve().parent.parent/'dashboard'/'index.html').read_text()
    assert 'generate-key' not in html
    assert "rawUrl='https://'+rawUrl" in html
    assert 'type=\"text\"' in html
    for panel in ('Command center','Live scanner','Paper portfolio','Strategy lab','System health','Trade better.','Protect capital.'):
        assert panel in html
