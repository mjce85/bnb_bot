"""Core dataclasses shared across the backtest engine.

Pure data — no engine logic. Float64 throughout: backtest precision is fine
with floats (we are not settling on-chain here). Timestamps are epoch
milliseconds, matching the ccxt OHLCV convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class Candle:
    """One OHLCV bar. `ts` is epoch milliseconds."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        if self.high < self.low:
            raise ValueError(f"candle high {self.high} < low {self.low} @ ts={self.ts}")


@dataclass(frozen=True)
class Signal:
    """Target allocation for a symbol at a point in time.

    `target_weight` in [0, 1] — fraction of equity to hold long. Long-only
    (spot venue: no perps). 0 == flat, 1 == fully allocated.
    """

    ts: int
    symbol: str
    target_weight: float

    def __post_init__(self):
        if not 0.0 <= self.target_weight <= 1.0:
            raise ValueError(
                f"target_weight must be in [0,1], got {self.target_weight}"
            )


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Order:
    """An intent to trade `base_qty` (>0) of `symbol` at the next bar open."""

    ts: int
    symbol: str
    side: Side
    base_qty: float


@dataclass(frozen=True)
class Fill:
    """A realized trade. `price` is effective (incl. slippage); `fee_usd`
    bundles swap fee + gas."""

    ts: int
    symbol: str
    side: Side
    base_qty: float
    price: float
    fee_usd: float


@dataclass
class Position:
    """Open long position in `symbol` (base units) with weighted avg entry."""

    symbol: str
    base_qty: float = 0.0
    avg_entry: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.base_qty > 0


@dataclass
class BacktestResult:
    """Everything a report needs from one strategy/symbol/window run."""

    strategy: str
    symbol: str
    window: tuple  # (start_iso, end_iso)
    params: dict
    equity_curve: list  # list[tuple[int ts, float equity]]
    fills: list  # list[Fill]
    metrics: dict = field(default_factory=dict)
