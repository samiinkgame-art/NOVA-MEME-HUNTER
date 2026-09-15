"""Transparent, uncalibrated market heuristics. Never a probability of profit."""
from .research_models import Snapshot, Decision
from .research_config import Config


def clamp(x):
    return round(max(0, min(100, x)), 2)


def analyze(s: Snapshot, now: float, cfg: Config) -> Decision:
    activity = s.buys5m + s.sells5m
    imbalance = s.buys5m / activity if activity else 0.5
    acceleration = s.volume5m * 12 / s.volume1h if s.volume1h else 0
    liquidity = clamp(s.liquidity / 500000 * 100)
    momentum = clamp(45 + s.change5m * 2 + s.change1h * 0.3)
    flow = clamp(imbalance * 100)
    activity_score = clamp(min(activity / 200, 1) * 60 + min(acceleration / 3, 1) * 40)
    components = {"liquidity": liquidity, "momentum": momentum, "buy_count_pressure": flow,
                  "activity": activity_score, "developer": None, "security": None,
                  "rug": None, "smart_money": None, "holder_quality": None, "volume_quality": None}
    score = round(0.30*liquidity + 0.30*momentum + 0.20*flow + 0.20*activity_score, 2)
    reasons = ["Security, developer history, holder clusters and rug risk are UNKNOWN.",
               "Market score is an unvalidated heuristic; NOVA score is unavailable."]
    fresh = 0 <= now - s.received_at <= cfg.stale_seconds
    if not fresh:
        reasons.append("Stale or future-dated observation.")
    if s.liquidity < cfg.min_liquidity:
        reasons.append("Liquidity below minimum.")
    strategy = None
    if score >= 65 and 1 <= s.change5m <= 15 and s.change1h > 0 and imbalance >= 0.6 and activity >= 30:
        strategy = "momentum_v1"
    elif score >= 60 and -3 <= s.change5m <= 3 and s.change1h >= 8 and imbalance >= 0.65 and acceleration >= 1.5:
        strategy = "continuation_v1"
    candidate = bool(strategy and fresh and s.liquidity >= cfg.min_liquidity)
    if candidate:
        reasons.append(f"Market-only research candidate: {strategy}; not cleared for trading.")
    return Decision("NO TRADE", score, None, 0.4, components, reasons, strategy, candidate)
