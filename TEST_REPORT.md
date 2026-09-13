# Test Report — NOVA MEME HUNTER — MANUS V1.0.0

## Executed result

Command:

```bash
pytest -q && python3 -m compileall -q app tests && node --check dashboard/app.js
```

Result: **7 passed**, Python compilation successful, and JavaScript syntax check successful. FastAPI emitted only deprecation warnings for `on_event`; this does not affect behavior or test outcomes.

## Covered checks

| Area | Result |
|---|---|
| Health/version response | PASS |
| Hardcoded live execution lock | PASS |
| Major and stablecoin rejection | PASS |
| High-quality early entry | PASS |
| Anti-chase rejection | PASS |
| Weak liquidity rejection | PASS |
| Creator dump rejection | PASS |
| Launch qualification and immature-launch rejection | PASS |
| Risk sizing and dollar-risk bound | PASS |
| Maximum positions and daily loss guard | PASS |
| Loss-streak risk reduction | PASS |
| Paper spread/slippage/fee and exit P&L | PASS |
| Edge Governor rolling statistics | PASS |
| Admin authentication and candidate API schema | PASS |
| Python compilation | PASS |
| JavaScript syntax | PASS |

## Self-audit notes

The paper executor applies modeled entry spread/slippage and exit cost before net P&L. Risk sizing uses equity multiplied by a bounded risk fraction divided by stop distance; loss streaks reduce risk and never increase it. Candidate ingestion is separated from scoring, and the PumpPortal adapter uses timeout-based heartbeat handling, exponential reconnect backoff, cancellation propagation, and async I/O. No wallet, signing, withdrawal, or real execution path exists. The dashboard reads the documented response keys and never contains a provider credential.
