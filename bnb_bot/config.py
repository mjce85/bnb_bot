"""Central configuration for bnb_bot backtests.

All tunables live here — no magic numbers in strategy/engine code.
Grouped into frozen dataclasses so a single backtest can override one knob
without mutating global state. Constructors validate ranges and fail loud.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Exchange / data ---------------------------------------------------
EXCHANGE_ID = "binance"  # ccxt id; Binance has spot history for BSC-listed tokens
DEFAULT_TIMEFRAME = "1h"
DATA_DIR = "data"  # parquet cache (gitignored)

# Liquid token set (Binance spot symbols). Long-only spot — TWAK has no perps.
TOKEN_SET = (
    "BNB/USDT",
    "CAKE/USDT",
    "ETH/USDT",
    "BTC/USDT",
)

STARTING_EQUITY_USD = 10_000.0


@dataclass(frozen=True)
class CostModel:
    """Costs charged on every simulated fill. A fee-free backtest lies."""

    swap_fee: float = 0.0025  # PancakeSwap v2 swap fee, 0.25%
    slippage_bps: float = 10.0  # assumed slippage per fill, basis points
    gas_usd: float = 0.30  # flat BSC gas estimate per swap, USD

    def __post_init__(self):
        if self.swap_fee < 0 or self.slippage_bps < 0 or self.gas_usd < 0:
            raise ValueError("cost model components must be non-negative")


@dataclass(frozen=True)
class RiskLimits:
    """Rule-adherence is a judged axis — these are hard caps, enforced loud."""

    max_position_frac: float = 0.25  # max fraction of equity in one position
    max_total_exposure: float = 1.0  # max fraction of equity deployed at once
    max_drawdown_halt: float = 0.20  # halt new entries past 20% drawdown
    stop_loss_frac: float = 0.10  # per-trade stop, 10% adverse move

    def __post_init__(self):
        for name, v in (
            ("max_position_frac", self.max_position_frac),
            ("max_total_exposure", self.max_total_exposure),
            ("max_drawdown_halt", self.max_drawdown_halt),
            ("stop_loss_frac", self.stop_loss_frac),
        ):
            if not 0 < v <= 1:
                raise ValueError(f"{name} must be in (0, 1], got {v}")


# Default instances consumed when a backtest doesn't override.
DEFAULT_COSTS = CostModel()
DEFAULT_RISK = RiskLimits()
