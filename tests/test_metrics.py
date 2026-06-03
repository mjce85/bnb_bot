"""Tests for metrics — hand-computed against small, exact equity curves.

Where annualization would drag in ``sqrt(8766)`` and obscure the arithmetic,
the tests pass ``periods_per_year=1.0`` to isolate the ratio itself. One test
pins the inferred annualization factor separately.
"""

from __future__ import annotations

import math

import pytest

from bnb_bot.backtest import run_backtest
from bnb_bot.metrics import compute_metrics
from bnb_bot.types import BacktestResult, Candle, Fill, Side

HOUR = 60 * 60 * 1000


def _result(equity_pairs, fills=None) -> BacktestResult:
    return BacktestResult(
        strategy="t",
        symbol="X/USDT",
        window=(equity_pairs[0][0], equity_pairs[-1][0]),
        params={},
        equity_curve=list(equity_pairs),
        fills=list(fills or []),
    )


def test_total_return_and_drawdown_exact():
    curve = [(0, 100.0), (HOUR, 120.0), (2 * HOUR, 108.0)]
    m = compute_metrics(_result(curve), periods_per_year=1.0)
    assert m.total_return == pytest.approx(0.08)
    # peak 120 then 108 -> (120-108)/120 = 0.10
    assert m.max_drawdown == pytest.approx(0.10)


def test_sharpe_sortino_calmar_exact():
    # returns = [+0.20, -0.10]; ppy=1 so annualization factor is 1.
    curve = [(0, 100.0), (HOUR, 120.0), (2 * HOUR, 108.0)]
    m = compute_metrics(_result(curve), periods_per_year=1.0)

    # mean excess = 0.05; sample std of [0.2,-0.1] = sqrt(0.045) = 0.21213203
    assert m.sharpe == pytest.approx(0.05 / math.sqrt(0.045))
    # downside dev = sqrt((0^2 + 0.1^2)/2) = sqrt(0.005)
    assert m.sortino == pytest.approx(0.05 / math.sqrt(0.005))
    # cagr over 2 intervals at ppy=1 -> 1.08^(1/2)-1; calmar = cagr / 0.10
    cagr = 1.08**0.5 - 1.0
    assert m.cagr == pytest.approx(cagr)
    assert m.calmar == pytest.approx(cagr / 0.10)


def test_flat_returns_give_zero_sharpe_and_inf_calmar():
    # Two identical +10% bars: zero volatility, no drawdown.
    curve = [(0, 100.0), (HOUR, 110.0), (2 * HOUR, 121.0)]
    m = compute_metrics(_result(curve), periods_per_year=1.0)
    assert m.total_return == pytest.approx(0.21)
    assert m.max_drawdown == 0.0
    assert m.sharpe == 0.0  # std == 0 -> no risk signal, not a crash/NaN
    assert m.sortino == 0.0  # no downside periods
    assert m.calmar == math.inf  # positive return, zero drawdown


def test_win_rate_average_cost():
    # Two zero-fee round trips: +10 (win) then -10 (loss) -> 50% win rate.
    fills = [
        Fill(
            ts=HOUR,
            symbol="X/USDT",
            side=Side.BUY,
            base_qty=1.0,
            price=100.0,
            fee_usd=0.0,
        ),
        Fill(
            ts=2 * HOUR,
            symbol="X/USDT",
            side=Side.SELL,
            base_qty=1.0,
            price=110.0,
            fee_usd=0.0,
        ),
        Fill(
            ts=3 * HOUR,
            symbol="X/USDT",
            side=Side.BUY,
            base_qty=1.0,
            price=100.0,
            fee_usd=0.0,
        ),
        Fill(
            ts=4 * HOUR,
            symbol="X/USDT",
            side=Side.SELL,
            base_qty=1.0,
            price=90.0,
            fee_usd=0.0,
        ),
    ]
    curve = [(0, 100.0), (5 * HOUR, 100.0)]
    m = compute_metrics(_result(curve, fills), periods_per_year=1.0)
    assert m.win_rate == pytest.approx(0.5)
    assert m.n_trades == 4


def test_exposure_is_time_in_market():
    # Buy at bar 1, sell at bar 3, over 4 bars -> held bars 1 and 2 -> 0.5.
    fills = [
        Fill(
            ts=HOUR,
            symbol="X/USDT",
            side=Side.BUY,
            base_qty=1.0,
            price=100.0,
            fee_usd=0.0,
        ),
        Fill(
            ts=3 * HOUR,
            symbol="X/USDT",
            side=Side.SELL,
            base_qty=1.0,
            price=100.0,
            fee_usd=0.0,
        ),
    ]
    curve = [(0, 100.0), (HOUR, 100.0), (2 * HOUR, 100.0), (3 * HOUR, 100.0)]
    m = compute_metrics(_result(curve, fills), periods_per_year=1.0)
    assert m.exposure == pytest.approx(0.5)


def test_periods_per_year_inferred_from_hourly_spacing():
    curve = [(i * HOUR, 100.0 + i) for i in range(5)]
    m = compute_metrics(_result(curve))
    # 365.25 * 24 hours in a year
    assert m.periods_per_year == pytest.approx(365.25 * 24)


def test_realized_winrate_ties_to_a_real_backtest_flip():
    # Buy then full sell through the real engine; the single closing sell is a
    # winner and total_return matches the hand-computed flip P&L.
    def _candle(i, o, c):
        return Candle(
            ts=i * HOUR, open=o, high=max(o, c), low=min(o, c), close=c, volume=1.0
        )

    class _Flip:
        def signal(self, history):
            return 1.0 if len(history) == 1 else 0.0

    candles = [_candle(0, 100, 100), _candle(1, 100, 100), _candle(2, 200, 200)]
    res = run_backtest(candles, _Flip(), symbol="BNB/USDT", starting_equity=10_000.0)
    m = compute_metrics(res)
    assert m.win_rate == pytest.approx(1.0)  # the one closing sell was profitable
    assert m.total_return == pytest.approx(19894.425 / 10_000.0 - 1.0)


def test_too_few_points_fails_loud():
    with pytest.raises(ValueError, match="at least 2 equity points"):
        compute_metrics(_result([(0, 100.0)]))
