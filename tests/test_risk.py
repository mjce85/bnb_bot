"""Tests for risk rules — one scenario per rule, plus an engine integration.

Each test isolates a single rule by relaxing the others through a tailored
:class:`RiskLimits`, so a failure points at exactly one rule.
"""

from __future__ import annotations

import pytest

from bnb_bot import config
from bnb_bot.backtest import run_backtest
from bnb_bot.risk import RuleBasedRisk
from bnb_bot.types import Candle, Position, Side

HOUR = 60 * 60 * 1000


def _flat() -> Position:
    return Position(symbol="X/USDT")


def _open(qty: float, avg_entry: float) -> Position:
    return Position(symbol="X/USDT", base_qty=qty, avg_entry=avg_entry)


def test_position_size_cap():
    risk = RuleBasedRisk(config.RiskLimits(max_position_frac=0.25))
    out = risk.adjust(
        target_weight=1.0,
        equity=10_000.0,
        peak_equity=10_000.0,
        position=_flat(),
        price=100.0,
    )
    assert out == pytest.approx(0.25)


def test_total_exposure_cap_binds_when_below_position_cap():
    # Position cap wide open (1.0); exposure cap is the binding constraint.
    risk = RuleBasedRisk(
        config.RiskLimits(max_position_frac=1.0, max_total_exposure=0.5)
    )
    out = risk.adjust(
        target_weight=1.0,
        equity=10_000.0,
        peak_equity=10_000.0,
        position=_flat(),
        price=100.0,
    )
    assert out == pytest.approx(0.5)


def test_stop_loss_forces_exit():
    # avg entry 100, stop 10% -> trigger at/below 90. Price 85 -> exit (0.0).
    risk = RuleBasedRisk(config.RiskLimits(stop_loss_frac=0.10))
    out = risk.adjust(
        target_weight=1.0,
        equity=9_000.0,
        peak_equity=10_000.0,
        position=_open(qty=100.0, avg_entry=100.0),
        price=85.0,
    )
    assert out == 0.0


def test_stop_loss_not_triggered_above_threshold():
    risk = RuleBasedRisk(config.RiskLimits(stop_loss_frac=0.10, max_position_frac=1.0))
    # Price 95 is above the 90 stop -> position kept, normal sizing applies.
    out = risk.adjust(
        target_weight=1.0,
        equity=9_500.0,
        peak_equity=10_000.0,
        position=_open(qty=100.0, avg_entry=100.0),
        price=95.0,
    )
    assert out == pytest.approx(1.0)


def test_drawdown_breaker_halts_new_entries():
    # 25% drawdown vs 20% halt; already holding ~10% weight. Strategy wants more
    # (0.8) but the breaker caps the target at the current weight: no adding.
    risk = RuleBasedRisk(
        config.RiskLimits(max_drawdown_halt=0.20, max_position_frac=1.0)
    )
    equity = 7_500.0  # 25% below the 10_000 peak
    pos = _open(qty=10.0, avg_entry=75.0)  # 10 * 75 = 750 -> weight 0.10
    out = risk.adjust(
        target_weight=0.8,
        equity=equity,
        peak_equity=10_000.0,
        position=pos,
        price=75.0,
    )
    assert out == pytest.approx(0.10)  # held weight, not increased


def test_drawdown_breaker_still_allows_reducing():
    risk = RuleBasedRisk(
        config.RiskLimits(max_drawdown_halt=0.20, max_position_frac=1.0)
    )
    pos = _open(qty=10.0, avg_entry=75.0)  # weight 0.10 at price 75
    # Strategy wants to cut to 0.05 -> breaker permits reductions.
    out = risk.adjust(
        target_weight=0.05,
        equity=7_500.0,
        peak_equity=10_000.0,
        position=pos,
        price=75.0,
    )
    assert out == pytest.approx(0.05)


def test_below_threshold_drawdown_does_not_halt():
    risk = RuleBasedRisk(
        config.RiskLimits(max_drawdown_halt=0.20, max_position_frac=1.0)
    )
    # Only 10% drawdown -> breaker inactive, full target allowed.
    out = risk.adjust(
        target_weight=0.8,
        equity=9_000.0,
        peak_equity=10_000.0,
        position=_open(qty=10.0, avg_entry=90.0),
        price=90.0,
    )
    assert out == pytest.approx(0.8)


def test_nonpositive_equity_forces_flat():
    risk = RuleBasedRisk()
    out = risk.adjust(
        target_weight=1.0,
        equity=0.0,
        peak_equity=10_000.0,
        position=_open(qty=10.0, avg_entry=100.0),
        price=50.0,
    )
    assert out == 0.0


def test_integration_position_cap_limits_deployment():
    # Strategy always wants fully invested; a 25% position cap should leave the
    # book ~75% in cash. Flat prices so we can read the weight straight off.
    candles = [
        Candle(ts=i * HOUR, open=100.0, high=100.0, low=100.0, close=100.0, volume=1.0)
        for i in range(4)
    ]
    risk = RuleBasedRisk(config.RiskLimits(max_position_frac=0.25))
    res = run_backtest(
        candles,
        lambda h: 1.0,
        symbol="X/USDT",
        starting_equity=10_000.0,
        risk=risk,
    )
    buy = res.fills[0]
    assert buy.side is Side.BUY
    # ~0.25 of 10_000 / 100 = ~25 units (minus a hair of slippage on sizing).
    assert buy.base_qty == pytest.approx(25.0, rel=1e-3)


class _PhaseStrat:
    """Long, then flat through a crash, then long again on recovery."""

    def signal(self, history):
        i = len(history) - 1  # current decision bar
        if i <= 2:
            return 1.0  # phase A: long
        if i <= 5:
            return 0.0  # phase B: flat (exit during/after the crash)
        return 1.0  # phase C: long again


def test_drawdown_breaker_does_not_lock_out_after_going_flat():
    # Enter at 100, crash to 70 (>20% drawdown) while the strategy exits to cash,
    # then recover. With the campaign-peak fix the breaker must let the strategy
    # back in on the recovery; the old all-time-peak behaviour locked it out.
    prices = [100, 100, 100, 100, 70, 70, 75, 80, 80, 80]
    candles = [
        Candle(ts=i * HOUR, open=p, high=p, low=p, close=p, volume=1.0)
        for i, p in enumerate(prices)
    ]
    # Full allocation allowed; stop-loss effectively off so the EXIT is driven by
    # the strategy signal, isolating the breaker's re-entry behaviour.
    risk = RuleBasedRisk(
        config.RiskLimits(
            max_position_frac=1.0,
            max_total_exposure=1.0,
            max_drawdown_halt=0.20,
            stop_loss_frac=0.99,
        )
    )
    res = run_backtest(
        candles, _PhaseStrat(), symbol="X/USDT", starting_equity=10_000.0, risk=risk
    )

    buys = [f for f in res.fills if f.side is Side.BUY]
    reentry = [f for f in buys if f.ts >= 7 * HOUR]
    assert reentry, "breaker locked the strategy out of re-entry after a drawdown"
    assert len(buys) >= 2  # initial entry + at least one re-entry
