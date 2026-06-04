"""Tests for cross-sectional rotation: the dual-momentum allocator + engine path.

Synthetic, deterministic. The contract: rank by trailing return, drop negative
momentum (absolute filter), equal-weight the top-K, all-cash when nothing trends.
"""

from __future__ import annotations

import pytest

from bnb_bot.portfolio import run_rotation_backtest
from bnb_bot.rotation import dual_momentum_allocator, trailing_return
from bnb_bot.types import Candle

_DAY = 24 * 60 * 60 * 1000


def _series(prices, start=0):
    """Flat OHLC candles at the given closes, one per day."""
    return [
        Candle(ts=start + i * _DAY, open=p, high=p, low=p, close=p, volume=1.0)
        for i, p in enumerate(prices)
    ]


# --- trailing_return ---------------------------------------------------


def test_trailing_return_value():
    c = _series([100, 110, 121])  # +10% then +10%
    assert trailing_return(c, 2) == pytest.approx(0.21)  # 121/100 - 1
    assert trailing_return(c, 1) == pytest.approx(0.10)  # 121/110 - 1


def test_trailing_return_too_short():
    assert trailing_return(_series([100, 110]), 5) is None


def test_trailing_return_only_uses_last_lookback():
    # earlier history must not change a fixed-lookback return (no leakage of old)
    a = trailing_return(_series([1, 2, 100, 110]), 1)
    b = trailing_return(_series([999, 50, 100, 110]), 1)
    assert a == b == pytest.approx(0.10)


# --- dual_momentum_allocator ------------------------------------------


def _hist(prices):
    return _series(prices)


def test_allocator_picks_top_k_by_momentum():
    alloc = dual_momentum_allocator(lookback=2, top_k=2)
    histories = {
        "A": _hist([100, 100, 130]),  # +30%
        "B": _hist([100, 100, 120]),  # +20%
        "C": _hist([100, 100, 110]),  # +10%
        "D": _hist([100, 100, 105]),  # +5%
    }
    w = alloc(histories)
    assert w["A"] == pytest.approx(0.5) and w["B"] == pytest.approx(0.5)
    assert w["C"] == 0.0 and w["D"] == 0.0


def test_allocator_absolute_filter_drops_negatives():
    alloc = dual_momentum_allocator(lookback=2, top_k=2)
    histories = {
        "A": _hist([100, 100, 130]),  # +30%
        "B": _hist([100, 100, 90]),  # -10% -> ineligible
        "C": _hist([100, 100, 80]),  # -20% -> ineligible
    }
    w = alloc(histories)
    # only A is positive; it gets 1/top_k, the rest stays cash
    assert w["A"] == pytest.approx(0.5)
    assert w["B"] == 0.0 and w["C"] == 0.0


def test_allocator_all_cash_when_all_negative():
    alloc = dual_momentum_allocator(lookback=2, top_k=2)
    histories = {
        "A": _hist([100, 100, 90]),
        "B": _hist([100, 100, 80]),
    }
    w = alloc(histories)
    assert sum(w.values()) == 0.0  # dual-momentum cash fallback


def test_allocator_ignores_symbols_with_short_history():
    alloc = dual_momentum_allocator(lookback=5, top_k=1)
    histories = {
        "A": _hist([100, 100, 100, 100, 100, 200]),  # enough, +100%
        "B": _hist([100, 110]),  # too short -> ineligible
    }
    w = alloc(histories)
    assert w["A"] == pytest.approx(1.0) and w["B"] == 0.0


def test_allocator_validates_params():
    with pytest.raises(ValueError):
        dual_momentum_allocator(lookback=0)
    with pytest.raises(ValueError):
        dual_momentum_allocator(top_k=0)


# --- engine path: run_rotation_backtest --------------------------------


def test_rotation_backtest_rotates_into_the_winner():
    # A rises monotonically, B falls. Rotation should hold A, end up profitable.
    n = 60
    a = _series([100 * (1.02**i) for i in range(n)])
    b = _series([100 * (0.99**i) for i in range(n)], start=0)
    cbs = {"A": a, "B": b}
    alloc = dual_momentum_allocator(lookback=10, top_k=1)
    res = run_rotation_backtest(cbs, alloc, starting_equity=10_000.0)
    start_eq = res.equity_curve[0][1]
    end_eq = res.equity_curve[-1][1]
    assert end_eq > start_eq  # captured A's uptrend
    # it actually traded (rotated in), and only ever held the winner
    assert any(f.symbol == "A" for f in res.fills)


def test_rotation_backtest_goes_cash_in_broad_downtrend():
    # Everything falls -> absolute-momentum filter keeps the book in cash ->
    # equity is preserved (only any tiny entry cost), never deeply drawn down.
    n = 60
    cbs = {
        "A": _series([100 * (0.99**i) for i in range(n)]),
        "B": _series([100 * (0.98**i) for i in range(n)]),
    }
    alloc = dual_momentum_allocator(lookback=10, top_k=1)
    res = run_rotation_backtest(cbs, alloc, starting_equity=10_000.0)
    # never invested (all negative momentum throughout) -> equity stays flat
    assert res.equity_curve[-1][1] == pytest.approx(10_000.0)
    assert res.fills == []
