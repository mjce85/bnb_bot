"""Locked, validated strategy presets — the shippable entry configurations.

A preset is a *frozen* bundle of every knob needed to reproduce a submission
result: the strategy parameters, the engine's rebalance band, and the risk
limits. The numbers in :data:`VOL_TARGETED_REGIME_MOMENTUM` are not hand-picked
— they were chosen by the bounded, train/holdout-validated search in
``scripts/search_params.py`` (see ``reports/search_summary.md``) and frozen here
so the headline result is reproducible with one call.

Do not edit these values casually: they are the validated entry. Re-running the
search and updating them is a deliberate act, recorded in FINDINGS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from bnb_bot import config
from bnb_bot.risk import RuleBasedRisk
from bnb_bot.strategy import (
    Momentum,
    RegimeGated,
    Strategy,
    VolatilityTargeted,
)


@dataclass(frozen=True)
class EntryPreset:
    """A reproducible strategy + execution + risk configuration."""

    name: str
    target_vol: float
    trend_period: int
    vol_lookback: int
    rebalance_band: float
    risk_limits: config.RiskLimits

    def build_strategy(self) -> Strategy:
        """Construct a fresh strategy instance for this preset."""
        return VolatilityTargeted(
            RegimeGated(Momentum(), trend_period=self.trend_period),
            target_vol=self.target_vol,
            lookback=self.vol_lookback,
        )

    def build_risk(self) -> RuleBasedRisk:
        """Construct the risk manager for this preset."""
        return RuleBasedRisk(self.risk_limits)


# The validated entry: volatility-targeted, regime-gated momentum, daily bars.
# Frozen from the P1 search holdout-validated winner.
VOL_TARGETED_REGIME_MOMENTUM = EntryPreset(
    name="vol_targeted_regime_momentum",
    target_vol=0.015,
    trend_period=50,
    vol_lookback=30,
    rebalance_band=0.03,
    risk_limits=config.RiskLimits(
        max_position_frac=1.0,
        max_total_exposure=1.0,
        max_drawdown_halt=0.20,
        stop_loss_frac=0.10,
    ),
)

PRESETS = {VOL_TARGETED_REGIME_MOMENTUM.name: VOL_TARGETED_REGIME_MOMENTUM}
