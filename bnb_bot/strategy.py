"""Strategies — the things that turn a causal candle history into a target weight.

Reconciliation note: the original PLAN sketch named this ``generate_signals(
candles) -> Signal``. The T3 engine that actually *consumes* strategies settled
on a different, tested contract — :class:`bnb_bot.backtest.SignalSource`, i.e.
``signal(history: list[Candle]) -> float`` returning a target weight in
``[0, 1]``. We implement that real contract rather than a parallel API the
engine can't call. ``history`` is always ``candles[: t + 1]`` — every bar up to
and including the decision bar and *nothing after it*, so no-lookahead is
structural.

Two baselines, long-only spot (no shorting, no leverage):

* :class:`Momentum` — EMA crossover. Long while the fast EMA is above the slow
  EMA, flat otherwise. A pure function of history.
* :class:`MeanReversion` — z-score band with hysteresis. Go long when price is
  ``entry_z`` standard deviations below its rolling mean (oversold); exit when
  it reverts back to within ``exit_z``. Carries a tiny bit of causal state (the
  current long/flat stance), so a given instance backs exactly one run.

During warmup (fewer bars than the lookback needs) a strategy returns ``0.0`` —
flat. Not enough data to have a view is an honest flat, not a guess and not an
error.
"""

from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from bnb_bot.types import Candle


class Strategy(ABC):
    """A target-weight signal source. Satisfies ``backtest.SignalSource``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for reports/results."""

    @property
    @abstractmethod
    def params(self) -> dict:
        """Flat dict of tunables, recorded on the BacktestResult."""

    @abstractmethod
    def signal(self, history: list[Candle]) -> float:
        """Target weight in [0, 1] given the causal slice ``candles[: t+1]``."""


def _ema(values: list[float], period: int) -> float:
    """Final EMA of ``values`` with the given period, seeded on the first value."""
    alpha = 2.0 / (period + 1.0)
    e = values[0]
    for v in values[1:]:
        e = alpha * v + (1.0 - alpha) * e
    return e


# --- Momentum ----------------------------------------------------------


@dataclass(frozen=True)
class MomentumParams:
    fast_period: int = 12
    slow_period: int = 26

    def __post_init__(self):
        if self.fast_period < 1 or self.slow_period < 1:
            raise ValueError("EMA periods must be >= 1")
        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be < slow_period "
                f"({self.slow_period}) for a crossover to mean anything"
            )


class Momentum(Strategy):
    """Long while fast EMA > slow EMA (trend up), flat otherwise."""

    def __init__(self, params: MomentumParams = MomentumParams()):
        self._params = params

    @property
    def name(self) -> str:
        return "momentum_ema_cross"

    @property
    def params(self) -> dict:
        return asdict(self._params)

    def signal(self, history: list[Candle]) -> float:
        closes = [c.close for c in history]
        if len(closes) < self._params.slow_period:
            return 0.0  # warmup — not enough history for the slow EMA
        fast = _ema(closes, self._params.fast_period)
        slow = _ema(closes, self._params.slow_period)
        return 1.0 if fast > slow else 0.0


# --- Mean reversion ----------------------------------------------------


@dataclass(frozen=True)
class MeanReversionParams:
    lookback: int = 24
    entry_z: float = 1.0  # go long when z <= -entry_z (oversold)
    exit_z: float = 0.0  # exit when z >= -exit_z (reverted toward mean)

    def __post_init__(self):
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2 to have a dispersion")
        if self.entry_z <= 0:
            raise ValueError("entry_z must be > 0 (entries are below the mean)")
        if self.exit_z >= self.entry_z:
            raise ValueError(
                f"exit_z ({self.exit_z}) must be < entry_z ({self.entry_z}); the "
                "exit threshold sits closer to the mean than the entry"
            )


class MeanReversion(Strategy):
    """Buy oversold, sell on reversion. Hysteresis via causal stance state."""

    def __init__(self, params: MeanReversionParams = MeanReversionParams()):
        self._params = params
        self._long = False  # current stance; updated only from past bars

    @property
    def name(self) -> str:
        return "mean_reversion_zscore"

    @property
    def params(self) -> dict:
        return asdict(self._params)

    def signal(self, history: list[Candle]) -> float:
        closes = [c.close for c in history]
        if len(closes) < self._params.lookback:
            return 0.0  # warmup — no rolling window yet
        window = closes[-self._params.lookback :]
        mean = statistics.mean(window)
        sd = statistics.pstdev(window)
        z = 0.0 if sd == 0 else (closes[-1] - mean) / sd

        if z <= -self._params.entry_z:
            self._long = True
        elif z >= -self._params.exit_z:
            self._long = False
        # between thresholds: hold the current stance (hysteresis)
        return 1.0 if self._long else 0.0


# --- Trend following ---------------------------------------------------


@dataclass(frozen=True)
class TrendFollowingParams:
    trend_period: int = 100  # SMA lookback (bars; designed for daily)

    def __post_init__(self):
        if self.trend_period < 2:
            raise ValueError("trend_period must be >= 2")


class TrendFollowing(Strategy):
    """Long while price is above its long SMA, flat otherwise.

    The robust low-turnover baseline: it sits in **cash** whenever the trend is
    down, so it never fights a sustained downturn. Turnover is low because the
    price crosses a long SMA far less often than two fast EMAs cross each other.
    """

    def __init__(self, params: TrendFollowingParams = TrendFollowingParams()):
        self._params = params

    @property
    def name(self) -> str:
        return "trend_following_sma"

    @property
    def params(self) -> dict:
        return asdict(self._params)

    def signal(self, history: list[Candle]) -> float:
        closes = [c.close for c in history]
        if len(closes) < self._params.trend_period:
            return 0.0  # warmup
        sma = statistics.mean(closes[-self._params.trend_period :])
        return 1.0 if closes[-1] > sma else 0.0


# --- Regime gate (composable) ------------------------------------------


class RegimeGated(Strategy):
    """Force a base strategy flat unless the long-term trend is up.

    Wraps any :class:`Strategy`. When the latest close is at or below its
    ``trend_period`` SMA (a downtrend regime) the gate returns ``0.0`` — cash —
    no matter what the base wants. In an uptrend the base strategy's own signal
    passes through unchanged. The base always receives the full causal history,
    so no-lookahead is preserved.

    This is the fix for both probe killers at once: momentum stops whipsawing
    long in downtrends, and mean-reversion stops catching falling knives.
    """

    def __init__(self, base: Strategy, trend_period: int = 100):
        if trend_period < 2:
            raise ValueError("trend_period must be >= 2")
        self._base = base
        self._trend_period = trend_period

    @property
    def name(self) -> str:
        return f"{self._base.name}_regime{self._trend_period}"

    @property
    def params(self) -> dict:
        return {**self._base.params, "regime_trend_period": self._trend_period}

    def signal(self, history: list[Candle]) -> float:
        closes = [c.close for c in history]
        if len(closes) < self._trend_period:
            return 0.0  # warmup — no trend reference yet
        sma = statistics.mean(closes[-self._trend_period :])
        if closes[-1] <= sma:
            return 0.0  # downtrend regime -> cash, base is overruled
        return self._base.signal(history)
