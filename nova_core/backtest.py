"""Single-asset chronological OHLCV research with next-bar entry and adverse fills."""
import csv
import math
import random
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    liquidity: float

    def __post_init__(self):
        if any(not math.isfinite(v) for v in vars(self).values()): raise ValueError("Non-finite candle")
        if min(self.open, self.high, self.low, self.close) <= 0 or min(self.volume, self.liquidity) < 0:
            raise ValueError("Invalid candle values")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.low > self.high:
            raise ValueError("Invalid OHLC geometry")


def read_bars(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        bars = [Bar(**{k:float(row[k]) for k in Bar.__dataclass_fields__}) for row in csv.DictReader(f)]
    if any(a.timestamp >= b.timestamp for a,b in zip(bars,bars[1:])):
        raise ValueError("Candles must be strictly chronological and deduplicated")
    if len(bars) < 30: raise ValueError("At least 30 bars required")
    return bars


def metrics(pnls, equity, initial):
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    peak, dd = initial, 0
    for value in equity:
        peak = max(peak, value)
        dd = max(dd, (peak-value)/peak)
    returns = [(b-a)/a for a,b in zip([initial]+equity, equity) if a > 0]
    mean = statistics.mean(returns) if returns else 0
    std = statistics.stdev(returns) if len(returns) > 1 else 0
    downside = math.sqrt(sum(min(r,0)**2 for r in returns)/len(returns)) if returns else 0
    return {"trades": len(pnls), "net_pnl": equity[-1]-initial if equity else 0,
        "win_rate": len(wins)/len(pnls) if pnls else None,
        "profit_factor": sum(wins)/abs(sum(losses)) if losses else None,
        "expectancy_usd": statistics.mean(pnls) if pnls else None,
        "average_win": statistics.mean(wins) if wins else None,
        "average_loss": statistics.mean(losses) if losses else None,
        "max_drawdown": dd, "sharpe_per_bar": mean/std if std else None,
        "sortino_per_bar": mean/downside if downside else None,
        "annualized": False}


def run(bars, lookback=20, initial=10000, fee_bps=30, slippage_bps=50, strategy="breakout"):
    if lookback < 2 or initial <= 0 or not math.isfinite(initial): raise ValueError("Invalid test configuration")
    if strategy not in ("breakout", "trend"): raise ValueError("Unknown strategy")
    if not 0 <= fee_bps <= 1000 or not 0 <= slippage_bps <= 1000: raise ValueError("Invalid costs")
    if any(a.timestamp >= b.timestamp for a,b in zip(bars,bars[1:])): raise ValueError("Unordered candles")
    fee, slip = fee_bps/10000, slippage_bps/10000
    cash, position, pending = initial, None, False
    trades, curve, pnls = [], [], []
    peak = initial
    day_key, week_key, day_base, week_base = None, None, initial, initial
    streak, cooldown_until = 0, 0
    from datetime import datetime, timezone
    for i, bar in enumerate(bars):
        opening_equity = cash+(position["qty"]*bar.open*(1-slip)*(1-fee) if position else 0)
        dt = datetime.fromtimestamp(bar.timestamp, timezone.utc)
        day, week = dt.strftime("%Y-%m-%d"), dt.strftime("%G-%V")
        if day != day_key: day_key, day_base = day, opening_equity
        if week != week_key: week_key, week_base = week, opening_equity
        if pending and position is None:
            # Only previous closed-bar liquidity is known at this open.
            previous = bars[i-1]
            eligible = (cash > peak*0.90 and cash > day_base*0.97 and cash > week_base*0.94
                        and bar.timestamp >= cooldown_until and previous.liquidity >= 100000)
            amount = min(cash*0.05, cash*0.005/(0.08+2*(fee+slip)), previous.liquidity*0.001)
            if eligible and amount >= 10:
                entry = bar.open*(1+slip)
                position = {"entry": entry, "qty": amount/entry, "cost": amount*(1+fee),
                            "stop": entry*0.92, "target": entry*1.16, "opened_at": bar.timestamp}
                cash -= position["cost"]
        pending = False
        if position:
            exit_price, reason = None, None
            if bar.low <= position["stop"]:
                exit_price, reason = min(bar.open, position["stop"]), "STOP"
            elif bar.high >= position["target"]:
                exit_price, reason = position["target"], "TP"
            elif i == len(bars)-1:
                exit_price, reason = bar.close, "END_OF_DATA"
            if exit_price is not None:
                proceeds = position["qty"]*exit_price*(1-slip)*(1-fee)
                pnl = proceeds-position["cost"]
                cash += proceeds
                pnls.append(pnl)
                trades.append({**position, "exit": exit_price*(1-slip), "closed_at": bar.timestamp,
                               "pnl": pnl, "reason": reason, "r_multiple": pnl/(position["cost"]*0.08)})
                streak = streak+1 if pnl < 0 else 0
                if streak >= 3: cooldown_until = bar.timestamp+3600
                position = None
        value = cash+(position["qty"]*bar.close*(1-slip)*(1-fee) if position else 0)
        peak = max(peak, value)
        curve.append(value)
        if i >= lookback and i < len(bars)-1 and position is None:
            history = bars[i-lookback:i]
            if strategy == "breakout":
                pending = bar.close > max(x.high for x in history) and bar.volume > statistics.mean(x.volume for x in history)
            else:
                slow = statistics.mean(x.close for x in history)
                fast = statistics.mean(x.close for x in history[-max(2,lookback//3):])
                pending = bar.close > fast > slow and bar.close > bars[i-1].close
    result = metrics(pnls, curve, initial)
    result["average_r"] = statistics.mean(t["r_multiple"] for t in trades) if trades else None
    return {"metrics": result, "trades": trades, "equity": curve,
            "parameters": {"lookback": lookback, "strategy": strategy, "fee_bps": fee_bps, "slippage_bps": slippage_bps},
            "limitations": ["Single asset; no token survivorship correction", "No route-level depth or MEV model",
              "Fixed slippage and previous-bar liquidity participation cap", "Intra-bar stop wins ties",
              "No inference of profitability or authorization for live trading"]}


def monte_carlo(pnls, initial=10000, iterations=1000, seed=42):
    if not pnls: return {"available": False, "reason": "No closed trades"}
    if not 1 <= iterations <= 10000 or initial <= 0: raise ValueError("Invalid simulation config")
    rng = random.Random(seed)
    draws, endings, ruins = [], [], 0
    for _ in range(iterations):
        balance, peak, dd = initial, initial, 0
        # Bootstrap with replacement varies both sequence and total PnL.
        for _ in pnls:
            balance += rng.choice(pnls)
            peak = max(peak, balance)
            dd = max(dd, (peak-balance)/peak)
            if balance <= initial*0.5:
                ruins += 1
                break
        draws.append(dd)
        endings.append(balance)
    draws.sort(); endings.sort()
    return {"available": True, "method": "iid dollar-PnL bootstrap; dependence ignored", "seed": seed,
            "iterations": iterations, "drawdown_p95": draws[int(0.95*(iterations-1))],
            "ending_equity_p05": endings[int(0.05*(iterations-1))],
            "risk_of_50pct_loss": ruins/iterations}


def walk_forward(bars, window=180, test_size=60, fee_bps=30, slippage_bps=50):
    if window < 90 or test_size < 30: raise ValueError("Train/validation window >=90 and test >=30 required")
    folds = []
    for end in range(window, len(bars)-test_size+1, test_size):
        history = bars[end-window:end]
        split = int(len(history)*0.65)
        train, validation = history[:split], history[split:]
        candidates = []
        for strategy in ("breakout", "trend"):
            for lookback in (5, 10, 20):
                tr = run(train, lookback=lookback, strategy=strategy, fee_bps=fee_bps, slippage_bps=slippage_bps)["metrics"]
                vr = run(validation, lookback=lookback, strategy=strategy, fee_bps=fee_bps, slippage_bps=slippage_bps)["metrics"]
                if tr["trades"] >= 3 and vr["trades"] >= 2:
                    candidates.append((vr["net_pnl"]-10000*vr["max_drawdown"], strategy, lookback))
        if not candidates:
            folds.append({"test_start": bars[end].timestamp, "status": "INSUFFICIENT_EVIDENCE"})
            continue
        _, strategy, lookback = max(candidates)
        test = run(bars[end:end+test_size], lookback=lookback, strategy=strategy, fee_bps=fee_bps, slippage_bps=slippage_bps)
        folds.append({"test_start": bars[end].timestamp, "status": "RESEARCH_ONLY",
                      "selected": test["parameters"], "out_of_sample": test["metrics"]})
    return {"folds": folds, "live_approved": False,
            "method": "Rolling chronological train/validation/test; flat account each fold; test warmup excluded"}
