import os
os.environ.setdefault('NOVA_ADMIN_KEY','test-key')
os.environ['DATABASE_URL']='sqlite:///./nova_v7_test.db'
from fastapi.testclient import TestClient
from app import app, LIVE_EXECUTION_LOCKED

client = TestClient(app)


def test_health_preserves_v7_and_lock():
    r = client.get('/health')
    assert r.status_code == 200
    data = r.json()
    assert data['base_core_version'] == '7.0.0'
    assert data['release_label'] == 'V7 APEX FUSION'
    assert data['live_execution_locked'] is True
    assert data['major_perp_trading'] is False
    assert LIVE_EXECUTION_LOCKED is True


def test_capability_contract():
    data = client.get('/api/capabilities').json()
    assert data['paper_shadow_modes'] == ['PAPER', 'SHADOW']
    for feature in ('APEX_SCORE', 'PRE_MOVE', 'ANTI_CHASE', 'EDGE_GOVERNOR'):
        assert feature in data['intelligence']
    for feature in ('DAILY_LOSS_GUARD', 'OPEN_RISK_CAP', 'TAIL_RISK', 'NO_MARTINGALE'):
        assert feature in data['risk']
    assert data['major_perpetual_trading'] is False


def test_admin_boundary_and_dashboard_schema():
    assert client.get('/api/dashboard').status_code == 401
    r = client.get('/api/dashboard', headers={'X-NOVA-Key':'test-key'})
    assert r.status_code == 200
    body = r.json()
    for key in ('version','settings','metrics','universe','risk_status','edge_governor','realtime_pulse','launch_sniper'):
        assert key in body


def test_live_mode_is_unavailable():
    r = client.post('/api/mode/LIVE', headers={'X-NOVA-Key':'test-key'})
    assert r.status_code == 403


def test_unsafe_risk_setting_rejected():
    r = client.post('/api/settings', headers={'X-NOVA-Key':'test-key'}, json={'risk_pct':99})
    assert r.status_code == 400


def test_dashboard_keeps_full_v7_panels():
    html = open('/home/ubuntu/repo-dashboard/index.html', encoding='utf-8').read()
    for label in ('Meme Hunter Universe','Realtime Core','Micro Profit Cycle','NOVA Decision','Daily Guard + Target','Launch Sniper','APEX Edge Intelligence','Edge Governor','Recent Results'):
        assert label in html
    assert 'LIVE LOCKED' in html
    assert 'PAPER / SHADOW' in html
