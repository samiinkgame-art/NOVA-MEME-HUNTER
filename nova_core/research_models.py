from dataclasses import dataclass, asdict
from typing import Protocol
import math


@dataclass(frozen=True)
class Snapshot:
    mint: str
    symbol: str
    pair: str
    price: float
    liquidity: float
    volume5m: float
    volume1h: float
    buys5m: int
    sells5m: int
    change5m: float
    change1h: float
    received_at: float
    market_cap: float | None = None
    pair_created_at: float | None = None
    source: str = "dexscreener"

    def __post_init__(self):
        for key in ("price", "liquidity", "volume5m", "volume1h", "buys5m", "sells5m", "received_at"):
            v = getattr(self, key)
            if not math.isfinite(v) or v < 0:
                raise ValueError(f"Invalid {key}")
        if self.price <= 0 or not self.mint or not self.pair:
            raise ValueError("Missing valid price, mint or pair")
        for key in ("change5m", "change1h"):
            if not math.isfinite(getattr(self, key)):
                raise ValueError(f"Invalid {key}")
        for key in ("market_cap", "pair_created_at"):
            value = getattr(self, key)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"Invalid {key}")

    def dict(self):
        return asdict(self)


class MarketProvider(Protocol):
    def discover(self) -> list[str]: ...
    def snapshots(self, mints: list[str]) -> list[Snapshot]: ...


@dataclass(frozen=True)
class Decision:
    state: str
    market_score: float
    nova_score: None
    coverage: float
    components: dict
    reasons: list[str]
    strategy: str | None
    research_candidate: bool

    def dict(self):
        return asdict(self)
