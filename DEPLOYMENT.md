# Deployment

## Northflank backend

1. Push this repository to GitHub.
2. In Northflank create a service from the repository and select Dockerfile build.
3. Set the exposed service port to `8000`; use one replica and one worker because paper state is in-process.
4. Add `NOVA_ADMIN_KEY` with a long random value, `CORS_ORIGINS` set to the GitHub Pages origin, and optional backend-only provider variables: `PUMPPORTAL_API_KEY`, `PUMPPORTAL_TRADE_STREAM_ENABLED=true`, `DATABASE_URL`, `SOLANA_RPC_URL`.
5. Deploy and verify `https://<service>/health` returns version `NOVA MEME HUNTER — MANUS V1.0.0`, `live_execution_locked: true`, and `mode: PAPER / SHADOW`.

## GitHub Pages dashboard

1. Put the `dashboard/` directory in a repository (or use this repository with Pages source `/dashboard` if supported; otherwise copy its three files to a Pages branch root).
2. Enable GitHub Pages from the chosen branch.
3. Open the HTTPS Pages URL, enter the Northflank HTTPS backend URL and the same `NOVA_ADMIN_KEY` in Connection, and click Save & Connect.
4. Confirm the diagnostics and live lock banner. Never put PumpPortal or other provider keys in dashboard files.
