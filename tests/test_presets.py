"""Tests pinning the locked submission preset.

These assert the validated numbers don't drift silently. If the search is re-run
and the entry changes, these values change deliberately (and FINDINGS records it).
"""

from __future__ import annotations

from bnb_bot.backtest import SignalSource, run_backtest
from bnb_bot.presets import PRESETS, VOL_TARGETED_REGIME_MOMENTUM as ENTRY
from bnb_bot.risk import RuleBasedRisk
from bnb_bot.types import Candle

HOUR = 60 * 60 * 1000


def test_entry_preset_values_are_locked():
    assert ENTRY.name == "vol_targeted_regime_momentum"
    assert ENTRY.target_vol == 0.015
    assert ENTRY.trend_period == 50
    assert ENTRY.vol_lookback == 15
    assert ENTRY.rebalance_band == 0.15
    assert ENTRY.risk_limits.max_position_frac == 1.0
    assert ENTRY.risk_limits.max_drawdown_halt == 0.20
    assert ENTRY.risk_limits.stop_loss_frac == 0.10


def test_entry_registered_in_presets():
    assert PRESETS[ENTRY.name] is ENTRY


def test_build_strategy_is_a_signal_source_with_expected_composition():
    strat = ENTRY.build_strategy()
    assert isinstance(strat, SignalSource)
    # Composed name reflects vol-targeting over regime-gated momentum.
    assert strat.name == "momentum_ema_cross_regime50_voltgt"
    assert strat.params["target_vol"] == 0.015
    assert strat.params["regime_trend_period"] == 50
    assert strat.params["vol_lookback"] == 15


def test_build_risk_carries_the_locked_limits():
    risk = ENTRY.build_risk()
    assert isinstance(risk, RuleBasedRisk)
    assert risk.limits is ENTRY.risk_limits


def test_preset_runs_end_to_end_through_engine():
    closes = [100.0 + (i % 11) - 5 for i in range(120)]  # noisy series past warmup
    candles = [
        Candle(ts=i * HOUR, open=c, high=c + 1, low=c - 1, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]
    res = run_backtest(
        candles,
        ENTRY.build_strategy(),
        symbol="X/USDT",
        risk=ENTRY.build_risk(),
        rebalance_band=ENTRY.rebalance_band,
        strategy_name=ENTRY.name,
    )
    assert res.strategy == ENTRY.name
    assert len(res.equity_curve) == len(candles)
