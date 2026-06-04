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

from bnb_bot.sentiment import FearGreedSeries
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


# --- Volatility targeting (composable) ---------------------------------


class VolatilityTargeted(Strategy):
    """Scale a base strategy's weight inversely to recent realized volatility.

    The core of the risk-adjusted thesis: hold a roughly *constant amount of
    risk* instead of a constant amount of capital. When recent volatility is
    calm, deploy up to ``max_weight`` of the base signal; when it's wild, shrink
    exposure so a turbulent regime can't inflict a large drawdown.

    ``target_vol`` is a per-bar target (e.g. 0.02 = 2% daily). The scale factor
    is ``target_vol / realized_vol``, capped at ``max_weight`` (long-only spot,
    so no leverage above the cap). Realized vol is the population stdev of the
    last ``lookback`` simple returns. Wraps any base; preserves no-lookahead
    (vol is computed only from past closes).
    """

    def __init__(
        self,
        base: Strategy,
        *,
        target_vol: float = 0.02,
        lookback: int = 20,
        max_weight: float = 1.0,
    ):
        if target_vol <= 0:
            raise ValueError("target_vol must be > 0")
        if lookback < 2:
            raise ValueError("lookback must be >= 2 to have a dispersion")
        if not 0 < max_weight <= 1:
            raise ValueError("max_weight must be in (0, 1] (long-only spot)")
        self._base = base
        self._target_vol = target_vol
        self._lookback = lookback
        self._max_weight = max_weight

    @property
    def name(self) -> str:
        return f"{self._base.name}_voltgt"

    @property
    def params(self) -> dict:
        return {
            **self._base.params,
            "target_vol": self._target_vol,
            "vol_lookback": self._lookback,
            "max_weight": self._max_weight,
        }

    def signal(self, history: list[Candle]) -> float:
        base_w = self._base.signal(history)
        if base_w <= 0.0:
            return 0.0  # base is flat — nothing to size

        closes = [c.close for c in history]
        if len(closes) < self._lookback + 1:
            return 0.0  # warmup — not enough returns to estimate vol

        window = closes[-(self._lookback + 1) :]
        rets = [window[i] / window[i - 1] - 1.0 for i in range(1, len(window))]
        vol = statistics.pstdev(rets)
        scale = (
            self._max_weight
            if vol <= 0
            else min(self._max_weight, self._target_vol / vol)
        )
        return max(0.0, min(1.0, base_w * scale))


# --- Fear & Greed gate (composable) ------------------------------------


class FearGreedGated(Strategy):
    """Cut a base strategy's exposure at sentiment extremes (greed and/or fear).

    A top-level *risk overlay* powered by a Fear & Greed index. Each side is
    optional and a-priori, not fitted:

    * **greed side** — when the index sits at or above ``greed_threshold``, scale
      the base weight to ``greed_weight`` (0.0 = step to cash). The hypothesis:
      extreme greed marks froth / elevated top-risk. Default **75** is the
      standard "Extreme Greed" classification boundary, chosen by convention.
    * **fear side** — when the index sits at or below ``fear_threshold``, scale to
      ``fear_weight``. The inverse hypothesis: extreme fear marks capitulation /
      falling-knife risk. Off by default; **25** is the standard "Extreme Fear"
      boundary.

    Pass ``None`` to disable a side. With both active the overlay only holds in the
    calm middle band. Thresholds are convention boundaries, not search winners —
    keeping with the repo's anti-overfitting discipline.

    No-lookahead is preserved by :meth:`FearGreedSeries.value_asof`, which only
    returns sentiment stamped *strictly before* the decision bar. Before the
    series begins (or a reading is missing) the overlay is inert and the base
    passes through — an honest "no view", not a guess. The overlay only ever
    *reduces* exposure; it cannot lift a flat base.

    Complements :class:`RegimeGated` (which handles sustained *downtrends*).
    """

    def __init__(
        self,
        base: Strategy,
        fng: FearGreedSeries,
        *,
        greed_threshold: int | None = 75,
        greed_weight: float = 0.0,
        fear_threshold: int | None = None,
        fear_weight: float = 0.0,
    ):
        for name, t in (
            ("greed_threshold", greed_threshold),
            ("fear_threshold", fear_threshold),
        ):
            if t is not None and not 0 <= t <= 100:
                raise ValueError(f"{name} must be in [0, 100] or None")
        for name, w in (("greed_weight", greed_weight), ("fear_weight", fear_weight)):
            if not 0.0 <= w <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if greed_threshold is None and fear_threshold is None:
            raise ValueError("at least one of greed_threshold / fear_threshold")
        self._base = base
        self._fng = fng
        self._greed_threshold = greed_threshold
        self._greed_weight = greed_weight
        self._fear_threshold = fear_threshold
        self._fear_weight = fear_weight

    @property
    def name(self) -> str:
        tag = ""
        if self._greed_threshold is not None:
            tag += f"g{self._greed_threshold}"
        if self._fear_threshold is not None:
            tag += f"f{self._fear_threshold}"
        return f"{self._base.name}_fng{tag}"

    @property
    def params(self) -> dict:
        return {
            **self._base.params,
            "fng_source": self._fng.source,
            "greed_threshold": self._greed_threshold,
            "greed_weight": self._greed_weight,
            "fear_threshold": self._fear_threshold,
            "fear_weight": self._fear_weight,
        }

    def signal(self, history: list[Candle]) -> float:
        base_w = self._base.signal(history)
        if base_w <= 0.0 or not history:
            return base_w
        value = self._fng.value_asof(history[-1].ts)
        if value is None:
            return base_w  # no sentiment reading yet — overlay inert
        if self._greed_threshold is not None and value >= self._greed_threshold:
            return max(0.0, min(1.0, base_w * self._greed_weight))
        if self._fear_threshold is not None and value <= self._fear_threshold:
            return max(0.0, min(1.0, base_w * self._fear_weight))
        return base_w


# --- Donchian breakout (challenger) ------------------------------------


@dataclass(frozen=True)
class DonchianParams:
    entry_period: int = 20  # Turtle System-1 entry channel (~one month)
    exit_period: int = 10  # Turtle System-1 exit channel

    def __post_init__(self):
        if self.entry_period < 2 or self.exit_period < 2:
            raise ValueError("channel periods must be >= 2")


class DonchianBreakout(Strategy):
    """Turtle-style breakout: enter on a new high, exit on a trailing low.

    Long when the latest close breaks **above the highest high of the prior
    ``entry_period`` bars**; exit when it breaks **below the lowest low of the
    prior ``exit_period`` bars**; hold the stance in between (hysteresis via a
    tiny bit of causal state, like :class:`MeanReversion`). The point of the A/B:
    unlike the entry's EMA-cross + SMA gate — which exits early and re-enters late
    — a breakout channel *stays long for the whole duration a trend holds*, so it
    captures the bull-market upside the entry leaves on the table.

    Channels exclude the current bar (we compare today's close to the channel
    formed by the bars *before* it), so the rule is causal. Parameters are the
    classic Turtle System-1 values (20 / 10), frozen by convention not search.
    """

    def __init__(self, params: DonchianParams = DonchianParams()):
        self._params = params
        self._long = False  # stance; updated only from past bars

    @property
    def name(self) -> str:
        return f"donchian_{self._params.entry_period}_{self._params.exit_period}"

    @property
    def params(self) -> dict:
        return asdict(self._params)

    def signal(self, history: list[Candle]) -> float:
        need = max(self._params.entry_period, self._params.exit_period) + 1
        if len(history) < need:
            return 0.0  # warmup
        last = history[-1].close
        prior_high = max(c.high for c in history[-(self._params.entry_period + 1) : -1])
        prior_low = min(c.low for c in history[-(self._params.exit_period + 1) : -1])
        if not self._long and last > prior_high:
            self._long = True
        elif self._long and last < prior_low:
            self._long = False
        return 1.0 if self._long else 0.0


# --- Time-series momentum (challenger) ---------------------------------


@dataclass(frozen=True)
class TimeSeriesMomentumParams:
    lookback: int = 365  # ~12 months; the canonical trend-following horizon

    def __post_init__(self):
        if self.lookback < 2:
            raise ValueError("lookback must be >= 2")


class TimeSeriesMomentum(Strategy):
    """Long while the asset's own trailing ``lookback``-day return is positive.

    The Moskowitz/Ooi/Pedersen "time-series momentum" rule: an asset's own past
    return predicts its near future. Long-only here (weight 1 if the trailing
    12-month return is positive, else cash). The 12-month lookback is the single
    least data-mined parameter in trend-following — validated across dozens of
    instruments and decades — so it's the honest apples-to-apples test of "does
    simply staying long through the whole trend win back return?" vs the entry's
    faster, cash-prone signal. Pure function of past closes.
    """

    def __init__(self, params: TimeSeriesMomentumParams = TimeSeriesMomentumParams()):
        self._params = params

    @property
    def name(self) -> str:
        return f"tsmom_{self._params.lookback}"

    @property
    def params(self) -> dict:
        return asdict(self._params)

    def signal(self, history: list[Candle]) -> float:
        lb = self._params.lookback
        if len(history) < lb + 1:
            return 0.0  # warmup
        past = history[-(lb + 1)].close
        if past <= 0:
            return 0.0
        return 1.0 if (history[-1].close / past - 1.0) > 0.0 else 0.0


# --- Sticky (let-winners-run) exit (composable) ------------------------


class StickyExit(Strategy):
    """Enter on base + uptrend, then HOLD until the trend itself breaks.

    The asymmetric counterpart to :class:`RegimeGated`. The ``trend_period`` SMA
    gates the *entry* (go long only when the base signals long AND price is above
    its trend SMA), but once long the position is held until price falls back
    *below* the SMA — it does **not** exit merely because the faster base signal
    flips. The point: let a winner run for the whole duration of a trend instead of
    bailing on a shallow pullback (the A/B tournament showed the entry leaves
    bull-market upside on the table by exiting early).

    Stateful (one long/flat stance updated only from past bars, like
    :class:`MeanReversion`), so an instance backs exactly one run. No-lookahead:
    the stance at bar ``t`` uses only ``history``.
    """

    def __init__(self, base: Strategy, trend_period: int = 50):
        if trend_period < 2:
            raise ValueError("trend_period must be >= 2")
        self._base = base
        self._trend_period = trend_period
        self._long = False

    @property
    def name(self) -> str:
        return f"{self._base.name}_sticky{self._trend_period}"

    @property
    def params(self) -> dict:
        return {**self._base.params, "sticky_trend_period": self._trend_period}

    def signal(self, history: list[Candle]) -> float:
        closes = [c.close for c in history]
        if len(closes) < self._trend_period:
            return 0.0  # warmup — no trend reference
        sma = statistics.mean(closes[-self._trend_period :])
        regime_up = closes[-1] > sma
        if self._long:
            if not regime_up:  # exit only when the trend breaks
                self._long = False
        else:
            if regime_up and self._base.signal(history) > 0:  # asymmetric entry
                self._long = True
        return 1.0 if self._long else 0.0
