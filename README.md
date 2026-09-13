# NOVA MEME HUNTER — MANUS V1.0.0

A production-oriented **paper/shadow-only** event-driven meme-coin research and simulation service. It is not financial advice and makes no profitability promise.

## Architecture

FastAPI exposes a small JSON API and serves health data. Candidate events are normalized into a bounded deterministic scoring pipeline: pre-move intelligence, anti-chase, launch intelligence, flow, liquidity, market, security, execution, concentration, and creator-risk components combine into APEX. Entry is blocked by hard safety gates. Paper execution models spread, slippage, fees, delayed execution effects, staged risk sizing, and explicit exits. Provider adapters isolate PumpPortal WebSocket, DexScreener, and Binance read-only data. A background task is cancellation-safe and never performs blocking I/O in the async loop.

## Safety

`LIVE_EXECUTION_LOCKED = True` is hardcoded. There are no wallets, private keys, signing, withdrawals, or real order endpoints. All controls affect only paper/shadow state.

## Defaults

Starting equity is `$5,000`, normal risk is `0.30%` of equity, launch risk is `0.15%`, maximum simultaneous positions is `2`, and daily loss guard is `2.5%`. Risk is reduced after losses; there is no martingale or averaging down.

## Providers

PumpPortal realtime WebSocket is represented by a reconnecting, heartbeat-aware adapter. DexScreener and Binance public REST adapters use short async HTTP timeouts. Provider credentials remain backend-only.

## Environment variables

`NOVA_ADMIN_KEY` (required for admin POST endpoints), `CORS_ORIGINS` (comma-separated origins, default `*`), `PUMPPORTAL_API_KEY` (backend only, optional), `PUMPPORTAL_TRADE_STREAM_ENABLED` (backend-only deployment setting), `DATABASE_URL` (reserved for PostgreSQL integration), and `SOLANA_RPC_URL` (optional).

## Run locally

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export NOVA_ADMIN_KEY=change-me
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest -q
```

Open `dashboard/index.html` directly or publish the `dashboard/` directory to GitHub Pages. Configure the backend HTTPS URL and admin key in the Connection panel; the key is stored only in browser local storage and no provider key is ever sent to the browser.

## API

GET `/`, `/health`, `/api/dashboard`, `/api/signals`, `/api/positions`, `/api/trades`, `/api/realtime-diagnostics`, `/api/performance`, `/api/strategy-performance`; admin-authenticated POST `/api/candidates`, `/api/start`, `/api/stop`, `/api/kill`, `/api/reset-paper` using `X-NOVA-Key`.
