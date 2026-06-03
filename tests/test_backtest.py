"""Tests for the backtest engine — this is where the engine's credibility lives.

Two things are pinned hard here:
  * **Exact cost math** on a hand-computed flip (buy then full sell).
  * **No lookahead** — both via fill timing (decision at t fills at t+1 open) and
    via *future invariance* (changing only future bars cannot change past fills
    or the past equity curve).
"""

from __future__ import annotations

import pytest

from bnb_bot import config
from bnb_bot.backtest import run_backtest
from bnb_bot.types import Candle, Side

HOUR = 60 * 60 * 1000


def _candle(i: int, open_: float, close: float) -> Candle:
    hi = max(open_, close)
    lo = min(open_, close)
    return Candle(ts=i * HOUR, open=open_, high=hi, low=lo, close=close, volume=1.0)


class _Flip:
    """Target 1.0 at the first bar, 0.0 thereafter (buy then exit)."""

    def signal(self, history: list[Candle]) -> float:
        return 1.0 if len(history) == 1 else 0.0


def test_flip_fee_math_is_exact():
    # bar0 open/close 100; bar1 open 100 (BUY fills here); bar2 open 200 (SELL).
    candles = [_candle(0, 100, 100), _candle(1, 100, 100), _candle(2, 200, 200)]
    res = run_backtest(candles, _Flip(), symbol="BNB/USDT", starting_equity=10_000.0)

    assert len(res.fills) == 2

    buy = res.fills[0]
    assert buy.side is Side.BUY
    assert buy.ts == 1 * HOUR  # filled at bar 1 open, NOT bar 0
    assert buy.base_qty == pytest.approx(100.0)
    assert buy.price == pytest.approx(100.1)  # 100 * (1 + 10bps)
    # fee = 0.25% * (100 * 100.1) + 0.30 gas = 25.025 + 0.30
    assert buy.fee_usd == pytest.approx(25.325)

    sell = res.fills[1]
    assert sell.side is Side.SELL
    assert sell.ts == 2 * HOUR
    assert sell.base_qty == pytest.approx(100.0)
    assert sell.price == pytest.approx(199.8)  # 200 * (1 - 10bps)
    # fee = 0.25% * (100 * 199.8) + 0.30 = 49.95 + 0.30
    assert sell.fee_usd == pytest.approx(50.25)

    # Final equity: 10000 - 10010 - 25.325 (buy) + 19980 - 50.25 (sell) = 19894.425
    final_ts, final_eq = res.equity_curve[-1]
    assert final_ts == 2 * HOUR
    assert final_eq == pytest.approx(19894.425)

    # Equity curve has one point per bar.
    assert [ts for ts, _ in res.equity_curve] == [0, HOUR, 2 * HOUR]


def test_fill_happens_at_next_open_not_this_close():
    # Decision to go long is made at bar 0; it must fill at bar 1's OPEN price,
    # never bar 0's close. Make those two prices differ so a lookahead bug shows.
    candles = [_candle(0, 50, 999), _candle(1, 100, 100), _candle(2, 100, 100)]

    def always_long(history):
        return 1.0

    res = run_backtest(candles, always_long, symbol="X/USDT", starting_equity=1_000.0)
    assert res.fills[0].ts == 1 * HOUR
    # Fill price is bar1 open (100) with buy slippage, not bar0 close (999).
    assert res.fills[0].price == pytest.approx(
        100.0 * (1 + config.DEFAULT_COSTS.slippage_bps / 10_000)
    )


def test_no_lookahead_future_invariance():
    # Two series share bars 0..3 and differ only at bar 4. A causal engine must
    # produce identical fills and equity for bars 0..3 regardless of the future.
    shared = [
        _candle(0, 100, 100),
        _candle(1, 100, 105),
        _candle(2, 105, 110),
        _candle(3, 110, 115),
    ]
    series_a = shared + [_candle(4, 115, 130)]
    series_b = shared + [_candle(4, 115, 70)]

    def trend(history):
        # Purely causal: long iff the latest close is above the first close.
        return 1.0 if history[-1].close > history[0].close else 0.0

    res_a = run_backtest(series_a, trend, symbol="X/USDT")
    res_b = run_backtest(series_b, trend, symbol="X/USDT")

    # Equity for bars 0..3 (the shared prefix) must be identical.
    assert res_a.equity_curve[:4] == res_b.equity_curve[:4]

    # Fills executed at or before bar 3 must be identical.
    cutoff = 3 * HOUR
    fills_a = [f for f in res_a.fills if f.ts <= cutoff]
    fills_b = [f for f in res_b.fills if f.ts <= cutoff]
    assert fills_a == fills_b


def test_weight_is_clamped_into_range():
    candles = [_candle(0, 100, 100), _candle(1, 100, 100), _candle(2, 100, 100)]

    # Over-1 weight clamps to fully invested: first action is a BUY that deploys
    # ~all equity (10 units at ~100). It does not error or over-leverage.
    res_hi = run_backtest(
        candles, lambda h: 5.0, symbol="X/USDT", starting_equity=1_000.0
    )
    assert res_hi.fills[0].side is Side.BUY
    assert res_hi.fills[0].base_qty == pytest.approx(10.0)

    # Negative weight clamps to flat (no trade at all).
    res_lo = run_backtest(
        candles, lambda h: -3.0, symbol="X/USDT", starting_equity=1_000.0
    )
    assert res_lo.fills == []


def test_rebalance_band_stops_hold_churn():
    # A held full-weight position drifts a few dollars off target each bar after
    # fees. With no band it re-trims every bar; a 2% band leaves it alone after
    # the initial entry.
    candles = [_candle(i, 100, 100) for i in range(6)]

    churny = run_backtest(
        candles, lambda h: 1.0, symbol="X/USDT", starting_equity=10_000.0
    )
    banded = run_backtest(
        candles,
        lambda h: 1.0,
        symbol="X/USDT",
        starting_equity=10_000.0,
        rebalance_band=0.02,
    )
    assert len(banded.fills) == 1  # just the entry
    assert len(churny.fills) > 1  # re-trims on drift without a band


def test_min_trade_usd_skips_dust():
    candles = [_candle(0, 100, 100), _candle(1, 100, 100), _candle(2, 100, 100)]
    # target weight 1e-5 of 1000 = $0.01 notional, below the $1 floor -> no fill.
    res = run_backtest(
        candles, lambda h: 1e-5, symbol="X/USDT", starting_equity=1_000.0
    )
    assert res.fills == []


def test_nan_weight_fails_loud():
    candles = [_candle(0, 100, 100), _candle(1, 100, 100)]
    with pytest.raises(ValueError, match="NaN"):
        run_backtest(candles, lambda h: float("nan"), symbol="X/USDT")


def test_too_few_candles_fails_loud():
    with pytest.raises(ValueError, match="at least 2 candles"):
        run_backtest([_candle(0, 100, 100)], lambda h: 1.0, symbol="X/USDT")


def test_nonpositive_equity_fails_loud():
    candles = [_candle(0, 100, 100), _candle(1, 100, 100)]
    with pytest.raises(ValueError, match="starting_equity"):
        run_backtest(candles, lambda h: 1.0, symbol="X/USDT", starting_equity=0.0)
