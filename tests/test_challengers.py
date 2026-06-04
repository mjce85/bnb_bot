"""Tests for the challenger strategies: Donchian breakout + time-series momentum."""

from __future__ import annotations

import pytest

from bnb_bot.strategy import (
    DonchianBreakout,
    DonchianParams,
    StickyExit,
    Strategy,
    TimeSeriesMomentum,
    TimeSeriesMomentumParams,
)
from bnb_bot.types import Candle


class _Flip(Strategy):
    """Base stub whose signal can be flipped between calls, to test StickyExit."""

    def __init__(self, w=1.0):
        self.w = w

    @property
    def name(self):
        return "flip"

    @property
    def params(self):
        return {}

    def signal(self, history):
        return self.w


_DAY = 24 * 60 * 60 * 1000


def _c(close, high=None, low=None, i=0):
    return Candle(
        ts=i * _DAY,
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=1.0,
    )


def _flat(prices):
    return [_c(p, i=i) for i, p in enumerate(prices)]


# --- Donchian breakout -------------------------------------------------


def test_donchian_warmup_is_flat():
    s = DonchianBreakout(DonchianParams(entry_period=20, exit_period=10))
    assert s.signal(_flat([100] * 5)) == 0.0


def test_donchian_enters_on_new_high():
    s = DonchianBreakout(DonchianParams(entry_period=5, exit_period=3))
    # 6 bars flat at 100, then a close at 105 breaks the prior-5 high (100)
    hist = _flat([100, 100, 100, 100, 100, 100]) + [_c(105, i=6)]
    assert s.signal(hist) == 1.0


def test_donchian_holds_then_exits_on_new_low():
    s = DonchianBreakout(DonchianParams(entry_period=3, exit_period=3))
    base = _flat([100, 100, 100])
    # break out at 120 -> long
    h1 = base + [_c(120, i=3)]
    assert s.signal(h1) == 1.0
    # next bar 118: above the prior-3 low (100), so still long (hysteresis)
    h2 = h1 + [_c(118, i=4)]
    assert s.signal(h2) == 1.0
    # now a close below the prior-3 low -> exit to cash
    h3 = h2 + [_c(95, i=5)]
    assert s.signal(h3) == 0.0


def test_donchian_channel_excludes_current_bar_no_lookahead():
    # If the current bar's own high counted, price could never "break" its own
    # high. Entry must compare to the channel of PRIOR bars only.
    s = DonchianBreakout(DonchianParams(entry_period=3, exit_period=3))
    hist = _flat([10, 11, 12, 13]) + [_c(20, high=20, i=4)]
    assert s.signal(hist) == 1.0  # 20 > prior-3 high (13) -> long


def test_donchian_validates_params():
    with pytest.raises(ValueError):
        DonchianParams(entry_period=1)


# --- time-series momentum ----------------------------------------------


def test_tsmom_warmup_is_flat():
    s = TimeSeriesMomentum(TimeSeriesMomentumParams(lookback=10))
    assert s.signal(_flat([100] * 5)) == 0.0


def test_tsmom_long_when_trailing_return_positive():
    s = TimeSeriesMomentum(TimeSeriesMomentumParams(lookback=3))
    # close[-1]=130 vs close[-4]=100 -> +30% -> long
    assert s.signal(_flat([100, 110, 120, 130])) == 1.0


def test_tsmom_flat_when_trailing_return_negative():
    s = TimeSeriesMomentum(TimeSeriesMomentumParams(lookback=3))
    assert s.signal(_flat([100, 95, 90, 85])) == 0.0


def test_tsmom_validates_params():
    with pytest.raises(ValueError):
        TimeSeriesMomentumParams(lookback=1)


# --- StickyExit (let-winners-run) --------------------------------------

_UP = _flat([10, 10, 10, 20])  # last 20 > SMA(10,10,20)=13.3 -> regime up
_DOWN = _flat([20, 20, 20, 5])  # last 5 < SMA(20,20,5)=15 -> regime down


def test_sticky_warmup_is_flat():
    s = StickyExit(_Flip(1.0), trend_period=3)
    assert s.signal(_flat([10, 10])) == 0.0


def test_sticky_enters_on_base_plus_uptrend():
    s = StickyExit(_Flip(1.0), trend_period=3)
    assert s.signal(_UP) == 1.0


def test_sticky_does_not_enter_when_base_flat():
    s = StickyExit(_Flip(0.0), trend_period=3)
    assert s.signal(_UP) == 0.0  # uptrend but base says no


def test_sticky_holds_through_base_flip_while_trend_holds():
    base = _Flip(1.0)
    s = StickyExit(base, trend_period=3)
    assert s.signal(_UP) == 1.0  # entered
    base.w = 0.0  # base flips flat (a shallow-pullback EMA cross would exit here)
    assert s.signal(_UP) == 1.0  # but StickyExit holds — trend still up


def test_sticky_exits_only_when_trend_breaks():
    base = _Flip(1.0)
    s = StickyExit(base, trend_period=3)
    assert s.signal(_UP) == 1.0  # long
    assert s.signal(_DOWN) == 0.0  # trend broke -> exit


def test_sticky_validates_params():
    with pytest.raises(ValueError):
        StickyExit(_Flip(), trend_period=1)
