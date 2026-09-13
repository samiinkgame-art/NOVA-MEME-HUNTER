# NOVA MEME HUNTER V1.1.0 — APEX EDGE

PAPER/SHADOW meme/altcoin hunter derived from the NOVA V7.0.0 reference core.

## What changed
- APEX local decision ensemble: pre-move, flow, liquidity, market quality, security and recent PAPER feedback.
- Anti-chase veto for already-extended moves.
- Stablecoin / wrapped-major exclusion from meme hunting.
- Strict mode: rejected premium setups cannot be re-opened through the old soft-entry router.
- Launch APEX: stronger event, independent-buyer, flow, concentration and acceleration gates.
- Smaller launch exposure and faster invalidation.
- Lower account risk and fewer simultaneous positions.
- Edge Governor recovery probes: a paused strategy can recover with tiny controlled PAPER probes instead of being permanently re-paused by old losses.
- APEX feedback cache to keep dashboard and engine latency low.
- Historical PAPER trades remain visible, while the V1.1 APEX learning baseline starts from the deployment boundary.

## Safety
- LIVE execution remains hard locked.
- No martingale.
- Risk/security/liquidity guards remain authoritative.
- Profit is not guaranteed; evaluate with expectancy, profit factor and drawdown after a meaningful PAPER sample.

## Required Northflank variables
- `NOVA_ADMIN_KEY`
- `PUMPPORTAL_API_KEY`
- `PUMPPORTAL_TRADE_STREAM_ENABLED=true`

Optional database persistence:
- `DATABASE_URL` (PostgreSQL recommended for durable PAPER history)

## Health
After deployment, `/health` should include:
- `version: 1.1.0`
- `bot_profile: NOVA_MEME_HUNTER`
- `apex_edge_enabled: true`
- `apex_strict_mode: true`
- `apex_edition: APEX_EDGE`
- `base_core_version: 7.0.0`
- `major_perp_trading: false`
- `live_execution_locked: true`
