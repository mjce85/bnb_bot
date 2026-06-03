"""Tests for the buy-and-hold benchmark and walk-forward folds."""

from __future__ import annotations

import pytest

from bnb_bot.strategy import TrendFollowing, TrendFollowingParams
from bnb_bot.types import Candle
from bnb_bot.walkforward import buy_and_hold, walk_forward

HOUR = 60 * 60 * 1000


def _candles(closes: list[float]) -> list[Candle]:
    return [
        Candle(ts=i * HOUR, open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def test_buy_and_hold_enters_once_and_holds():
    # Price doubles from the entry bar; benchmark should buy once and ride it.
    candles = _candles([100.0, 100.0, 200.0, 200.0])
    res = buy_and_hold(candles, symbol="X/USDT", starting_equity=10_000.0)
    buys = [f for f in res.fills if f.side.value == "buy"]
    assert len(res.fills) == 1
    assert len(buys) == 1
    # Final equity is roughly double minus the single entry's costs.
    _, final_eq = res.equity_curve[-1]
    assert final_eq == pytest.approx(20_000.0, rel=0.01)


def test_buy_and_hold_flat_market_only_loses_entry_cost():
    candles = _candles([100.0] * 5)
    res = buy_and_hold(candles, symbol="X/USDT", starting_equity=10_000.0)
    _, final_eq = res.equity_curve[-1]
    # Slightly below start: just the one entry's fee + slippage.
    assert final_eq < 10_000.0
    assert final_eq == pytest.approx(10_000.0, rel=0.01)


def test_walk_forward_splits_and_scores_each_fold():
    closes = [100.0 + i for i in range(200)]  # steady rise
    candles = _candles(closes)

    folds = walk_forward(
        candles,
        lambda: TrendFollowing(TrendFollowingParams(trend_period=10)),
        symbol="X/USDT",
        n_folds=4,
    )
    assert len(folds) == 4
    # Folds tile the series with no gaps/overlaps and cover every bar.
    assert sum(f.n_bars for f in folds) == len(candles)
    assert folds[0].window[0] == candles[0].ts
    assert folds[-1].window[1] == candles[-1].ts
    for f in folds:
        # excess_return is strategy minus benchmark, by construction.
        assert f.excess_return == pytest.approx(
            f.strategy_metrics.total_return - f.benchmark_metrics.total_return
        )


def test_walk_forward_uses_fresh_strategy_per_fold():
    calls = {"n": 0}

    def make():
        calls["n"] += 1
        return TrendFollowing(TrendFollowingParams(trend_period=5))

    candles = _candles([100.0 + i for i in range(60)])
    walk_forward(candles, make, symbol="X/USDT", n_folds=3)
    assert calls["n"] == 3  # one fresh instance per fold


def test_walk_forward_fails_loud_when_too_many_folds():
    candles = _candles([100.0] * 5)
    with pytest.raises(ValueError, match="cannot be split"):
        walk_forward(candles, lambda: TrendFollowing(), symbol="X/USDT", n_folds=4)
