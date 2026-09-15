from dataclasses import dataclass
from pathlib import Path
import os


def load_env(path: str = ".env") -> None:
    if Path(path).is_file():
        for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Config:
    db: str = "data/nova.db"
    host: str = "127.0.0.1"
    port: int = 8765
    mode: str = "scanner"
    scan_seconds: int = 60
    stale_seconds: int = 180
    initial_cash: float = 10000
    risk_per_trade: float = 0.005
    max_position: float = 0.05
    max_exposure: float = 0.20
    daily_loss: float = 0.03
    weekly_loss: float = 0.06
    max_drawdown: float = 0.10
    min_liquidity: float = 100000
    max_participation: float = 0.001
    slippage_bps: float = 50
    fee_bps: float = 30
    max_slippage_bps: float = 100
    loss_streak: int = 3
    cooldown_seconds: int = 3600
    watchlist: tuple[str, ...] = ()
    auto_paper_research: bool = False

    def __post_init__(self):
        import math
        if self.mode not in ("scanner", "paper"):
            raise ValueError("LIVE is unavailable: no validated signing/execution adapter exists.")
        if self.host != "127.0.0.1":
            raise ValueError("This local research server must bind to 127.0.0.1.")
        for key in ("risk_per_trade", "max_position", "max_exposure", "daily_loss",
                    "weekly_loss", "max_drawdown", "max_participation"):
            val = getattr(self, key)
            if not math.isfinite(val) or not 0 < val <= 1:
                raise ValueError(f"Invalid {key}")
        for key in ("initial_cash", "min_liquidity", "scan_seconds", "stale_seconds",
                    "loss_streak", "cooldown_seconds", "max_slippage_bps"):
            val = getattr(self, key)
            if not math.isfinite(val) or val <= 0:
                raise ValueError(f"Invalid {key}")
        for key in ("fee_bps", "slippage_bps"):
            if not 0 <= getattr(self, key) <= 1000:
                raise ValueError(f"Invalid {key}")
        if not 1 <= self.port <= 65535 or self.scan_seconds < 30:
            raise ValueError("Invalid port or scan interval (minimum 30 seconds)")

    @classmethod
    def from_env(cls):
        load_env()
        base = cls()
        values = {}
        for key in cls.__dataclass_fields__:
            raw = os.getenv("NOVA_" + key.upper())
            if raw is not None:
                default = getattr(base, key)
                if isinstance(default, bool):
                    if raw.lower() not in ("true", "false"): raise ValueError(f"Invalid boolean {key}")
                    values[key] = raw.lower() == "true"
                else:
                    values[key] = tuple(x.strip() for x in raw.split(",") if x.strip()) if key == "watchlist" else type(default)(raw)
        return cls(**values)
