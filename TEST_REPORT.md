# NOVA MEME HUNTER V1.1.0 — APEX EDGE Test Report

## Static / syntax
- Python compile: PASS
- Dashboard JavaScript syntax (`node --check`): PASS

## Decision smoke tests
- App version / APEX identity: PASS
- LIVE hard-lock retained: PASS
- High-quality early DEX setup passes APEX gate: PASS
- Extended/chasing setup rejected: PASS
- USDC stablecoin excluded from meme target universe: PASS
- Strict APEX mode prevents rejected setup from becoming a soft-entry: PASS
- Launch APEX high-quality synthetic flow score >= entry floor: PASS
- Edge Governor expired pause enters controlled RECOVERY state at 0.20x risk: PASS
- APEX status endpoint data generation: PASS

Observed synthetic scores in smoke test:
- Early quality DEX setup: 80.9
- Chasing setup: 52.2
- Strong launch setup: 100.0

## Important
These are engineering smoke tests, not evidence of future profitability. PAPER performance must be evaluated on real market samples with fees/slippage assumptions.

## V7 APEX Fusion regression run

Executed after restoring the original V7 implementation and adding the V7 APEX Fusion release layer:

```bash
python3 -m py_compile app.py test_v7_fusion.py
pytest -q test_v7_fusion.py
```

Result: **6 passed**. The suite verified V7 version continuity, the hard live lock, capability contract, authenticated dashboard schema, rejection of LIVE mode with HTTP 403, unsafe-risk-setting rejection, and preservation of the full dashboard panel set. Only FastAPI startup-event deprecation warnings were emitted.
