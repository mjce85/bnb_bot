"""T1 — config + types foundation."""

import pytest

from bnb_bot import config
from bnb_bot.types import BacktestResult, Candle, Position, Side, Signal


def test_default_costs_sane():
    assert config.DEFAULT_COSTS.swap_fee > 0
    assert config.DEFAULT_COSTS.gas_usd >= 0


def test_default_risk_in_range():
    r = config.DEFAULT_RISK
    for v in (
        r.max_position_frac,
        r.max_total_exposure,
        r.max_drawdown_halt,
        r.stop_loss_frac,
    ):
        assert 0 < v <= 1


def test_cost_model_rejects_negative():
    with pytest.raises(ValueError):
        config.CostModel(swap_fee=-0.1)


def test_risk_rejects_out_of_range():
    with pytest.raises(ValueError):
        config.RiskLimits(max_position_frac=1.5)


def test_candle_rejects_high_below_low():
    with pytest.raises(ValueError):
        Candle(ts=1, open=1, high=0.5, low=1.0, close=0.8, volume=10)


def test_signal_weight_bounds():
    Signal(ts=1, symbol="BNB/USDT", target_weight=0.5)  # ok
    with pytest.raises(ValueError):
        Signal(ts=1, symbol="BNB/USDT", target_weight=1.5)


def test_position_is_open():
    p = Position(symbol="BNB/USDT")
    assert not p.is_open
    p.base_qty = 2.0
    assert p.is_open


def test_backtest_result_defaults_empty_metrics():
    r = BacktestResult(
        strategy="x",
        symbol="BNB/USDT",
        window=("a", "b"),
        params={},
        equity_curve=[],
        fills=[],
    )
    assert r.metrics == {}
    assert Side.BUY.value == "buy"
