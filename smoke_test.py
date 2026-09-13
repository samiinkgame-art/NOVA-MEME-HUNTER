import os, importlib.util, sys
os.environ['NOVA_ADMIN_KEY']='test-key'
spec=importlib.util.spec_from_file_location('nova_app','app.py')
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)
from fastapi.testclient import TestClient
client=TestClient(mod.app)
r=client.get('/health')
assert r.status_code == 200
body=r.json()
assert body['live_execution_locked'] is True
assert body['mode'] == 'PAPER / SHADOW'
assert 'NOVA MEME HUNTER' in body['version']
html=open('../repo-dashboard/index.html',encoding='utf-8').read()
for text in ('LIVE EXECUTION','LOCKED','PAPER / SHADOW','Best signals','/api/dashboard'):
    assert text in html
print('backend smoke: PASS')
print('dashboard contract: PASS')
