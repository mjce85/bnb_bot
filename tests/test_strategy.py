"""Tests for the two baseline strategies and their param validation."""

from __future__ import annotations

import pytest

from bnb_bot.backtest import SignalSource, run_backtest
from bnb_bot.strategy import (
    MeanReversion,
    MeanReversionParams,
    Momentum,
    MomentumParams,
)
from bnb_bot.types import Candle

HOUR = 60 * 60 * 1000


def _candles(closes: list[float]) -> list[Candle]:
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(ts=i * HOUR, open=c, high=c, low=c, close=c, volume=1.0))
    return out


# --- param validation --------------------------------------------------


def test_momentum_params_reject_fast_ge_slow():
    with pytest.raises(ValueError, match="must be <"):
        MomentumParams(fast_period=26, slow_period=12)


def test_mean_reversion_params_reject_exit_ge_entry():
    with pytest.raises(ValueError, match="must be <"):
        MeanReversionParams(entry_z=1.0, exit_z=1.5)


def test_mean_reversion_params_reject_nonpositive_entry():
    with pytest.raises(ValueError, match="entry_z"):
        MeanReversionParams(entry_z=0.0)


# --- momentum behaviour ------------------------------------------------


def test_momentum_flat_during_warmup():
    strat = Momentum(MomentumParams(fast_period=3, slow_period=10))
    # Only 5 bars < slow_period 10 -> flat.
    assert strat.signal(_candles([1, 2, 3, 4, 5])) == 0.0


def test_momentum_long_on_uptrend():
    strat = Momentum(MomentumParams(fast_period=3, slow_period=10))
    closes = list(range(1, 31))  # steady rise
    assert strat.signal(_candles(closes)) == 1.0


def test_momentum_flat_on_downtrend():
    strat = Momentum(MomentumParams(fast_period=3, slow_period=10))
    closes = list(range(30, 0, -1))  # steady fall
    assert strat.signal(_candles(closes)) == 0.0


# --- mean reversion behaviour ------------------------------------------


def test_mean_reversion_flat_during_warmup():
    strat = MeanReversion(MeanReversionParams(lookback=5))
    assert strat.signal(_candles([100, 100, 100])) == 0.0


def test_mean_reversion_enters_long_when_oversold():
    strat = MeanReversion(MeanReversionParams(lookback=5, entry_z=1.0, exit_z=0.0))
    # window [100,100,100,100,80]: mean 96, sd 8, z = -2 <= -1 -> long.
    assert strat.signal(_candles([100, 100, 100, 100, 80])) == 1.0


def test_mean_reversion_holds_then_exits_on_reversion():
    strat = MeanReversion(MeanReversionParams(lookback=5, entry_z=1.0, exit_z=0.0))
    closes = [100, 100, 100, 100, 80]  # oversold -> enter
    # Feed prefixes in order so the stance state evolves causally.
    for i in range(5, len(closes) + 1):
        strat.signal(_candles(closes[:i]))
    assert strat._long is True

    # Now a spike well above the mean pushes z >= 0 -> exit to flat.
    closes2 = closes + [200]
    assert strat.signal(_candles(closes2)) == 0.0


def test_mean_reversion_flat_window_gives_no_signal():
    strat = MeanReversion(MeanReversionParams(lookback=5))
    # Perfectly flat window: sd == 0, z forced to 0 -> no entry, stays flat.
    assert strat.signal(_candles([100, 100, 100, 100, 100])) == 0.0


# --- integration -------------------------------------------------------


def test_both_strategies_are_signal_sources_and_run():
    closes = [10 + (i % 7) for i in range(60)]  # noisy-ish series
    candles = _candles(closes)
    for strat in (Momentum(), MeanReversion()):
        assert isinstance(strat, SignalSource)
        res = run_backtest(candles, strat, symbol="X/USDT", strategy_name=strat.name)
        assert res.strategy == strat.name
        # Engine ran end to end and produced one equity point per bar.
        assert len(res.equity_curve) == len(candles)
