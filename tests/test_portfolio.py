"""Tests for the multi-asset portfolio engine.

The anchor test proves a one-symbol portfolio reproduces the single-asset engine
exactly — same fills, same equity curve — so the shared fill math is trusted.
"""

from __future__ import annotations

import pytest

from bnb_bot.backtest import run_backtest
from bnb_bot.metrics import compute_metrics
from bnb_bot.portfolio import buy_and_hold_portfolio, run_portfolio_backtest
from bnb_bot.types import Candle, Side
from bnb_bot.walkforward import buy_and_hold

HOUR = 60 * 60 * 1000


def _series(closes, start_i=0):
    return [
        Candle(
            ts=(start_i + i) * HOUR,
            open=c,
            high=c + 1,
            low=c - 1,
            close=c,
            volume=1.0,
        )
        for i, c in enumerate(closes)
    ]


def test_single_symbol_portfolio_matches_single_engine():
    candles = _series([100, 102, 99, 105, 103, 108, 110])

    def strat(history):
        return 1.0  # always fully long

    single = run_backtest(candles, strat, symbol="X/USDT", starting_equity=10_000.0)
    port = run_portfolio_backtest(
        {"X/USDT": candles},
        lambda sym: strat,
        starting_equity=10_000.0,
        max_total_exposure=1.0,
    )

    # Identical equity curve and fills — shared fill economics, same sizing.
    assert [t for t, _ in port.equity_curve] == [t for t, _ in single.equity_curve]
    for (_, pe), (_, se) in zip(port.equity_curve, single.equity_curve):
        assert pe == pytest.approx(se)
    assert len(port.fills) == len(single.fills)
    for pf, sf in zip(port.fills, single.fills):
        assert pf == sf


def test_total_exposure_cap_splits_across_symbols():
    # Two always-long symbols, flat price 100, cap 1.0 -> 0.5 each (~50 units).
    a = _series([100.0] * 4)
    b = _series([100.0] * 4)
    port = run_portfolio_backtest(
        {"A/USDT": a, "B/USDT": b},
        lambda sym: (lambda h: 1.0),
        starting_equity=10_000.0,
        max_total_exposure=1.0,
    )
    first_buys = {f.symbol: f for f in port.fills if f.side is Side.BUY}
    assert set(first_buys) == {"A/USDT", "B/USDT"}
    # Each gets ~0.5 * 10_000 / 100 = ~50 units (minus slippage on sizing).
    for f in first_buys.values():
        assert f.base_qty == pytest.approx(50.0, rel=2e-3)


def test_timeline_is_intersection_of_symbols():
    # B starts two bars later; the portfolio runs on the overlap only.
    a = _series([100, 101, 102, 103, 104], start_i=0)
    b = _series([100, 101, 102], start_i=2)  # ts 2,3,4
    port = run_portfolio_backtest(
        {"A/USDT": a, "B/USDT": b}, lambda sym: (lambda h: 0.0)
    )
    assert port.window == (2 * HOUR, 4 * HOUR)
    assert len(port.equity_curve) == 3


def test_buy_and_hold_portfolio_buys_once_per_symbol():
    a = _series([100, 100, 100, 100])
    b = _series([100, 100, 100, 100])
    port = buy_and_hold_portfolio({"A/USDT": a, "B/USDT": b}, starting_equity=10_000.0)
    buys = [f for f in port.fills if f.side is Side.BUY]
    sells = [f for f in port.fills if f.side is Side.SELL]
    assert {f.symbol for f in buys} == {"A/USDT", "B/USDT"}
    assert len(buys) == 2  # one entry each
    assert sells == []  # held, never re-trimmed


def test_diversification_reduces_drawdown():
    # One asset rises, one falls. An equal-weight hold of both should draw down
    # less than holding the falling asset alone.
    up = _series([100 + 5 * i for i in range(20)])
    down = _series([100 - 4 * i for i in range(20)])

    combined = compute_metrics(
        buy_and_hold_portfolio({"UP/USDT": up, "DOWN/USDT": down})
    ).max_drawdown
    down_only = compute_metrics(buy_and_hold(down, symbol="DOWN/USDT")).max_drawdown

    assert combined < down_only  # the riser cushions the faller


def test_fewer_than_two_common_timestamps_fails_loud():
    a = _series([100, 101], start_i=0)
    b = _series([100, 101], start_i=5)  # no overlap
    with pytest.raises(ValueError, match="common timestamps"):
        run_portfolio_backtest({"A/USDT": a, "B/USDT": b}, lambda sym: (lambda h: 1.0))
