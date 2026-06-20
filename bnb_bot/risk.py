"""Risk rules — the discipline that is our actual differentiator.

Rule adherence is a judged axis, so these caps are enforced inside the engine
loop, not bolted on after the fact. A :class:`RuleBasedRisk` is handed to
:func:`bnb_bot.backtest.run_backtest` as its ``risk=`` manager; the engine calls
:meth:`RuleBasedRisk.adjust` once per bar, *before* the fill, with the raw
strategy target weight and the current book state. It returns the weight the
engine is actually allowed to act on.

Four rules, applied in this precedence (each can only make the book *safer*):

1. **Stop-loss** — if an open position has fallen ``stop_loss_frac`` below its
   average entry, force the target to ``0.0`` (exit now). Overrides everything
   else; a stop is not negotiable.
2. **Position-size cap** — the target weight may never exceed
   ``max_position_frac`` of equity.
3. **Total-exposure cap** — nor exceed ``max_total_exposure`` deployed at once.
   (Single-symbol today, so this and the position cap both reduce to ``min``;
   the lower of the two binds. Kept distinct for when we go multi-symbol.)
4. **Drawdown breaker** — once equity is ``max_drawdown_halt`` below its
   *campaign* peak (the high since the book was last flat — see
   ``backtest.RiskManager``), halt *new* exposure: the target is capped at the
   weight already held, so the strategy can still trim or exit but cannot add.
   Because the peak resets when flat, a strategy that goes to cash is never
   locked out — it can re-enter once a fresh signal appears. Ported concept (not
   code) from a prior project's drawdown breaker.

Every rule only ever lowers risk, so order matters only for clarity: a stop
exits even mid-breaker, and the breaker never forces buying.
"""

from __future__ import annotations

from dataclasses import dataclass

from bnb_bot import config
from bnb_bot.types import Position


@dataclass(frozen=True)
class RuleBasedRisk:
    """Concrete risk manager satisfying ``backtest.RiskManager``.

    Holds a :class:`~bnb_bot.config.RiskLimits`; all four rules are active. The
    limits dataclass already range-validates its fields, so nothing here can be
    silently mis-configured.
    """

    limits: config.RiskLimits = config.DEFAULT_RISK

    def adjust(
        self,
        *,
        target_weight: float,
        equity: float,
        peak_equity: float,
        position: Position,
        price: float,
    ) -> float:
        lim = self.limits

        # 0. A non-positive book can't carry risk — force flat, loudly safe.
        if equity <= 0:
            return 0.0

        # 1. Stop-loss: an open position underwater past the threshold exits now.
        if position.is_open and position.avg_entry > 0:
            stop_price = position.avg_entry * (1.0 - lim.stop_loss_frac)
            if price <= stop_price:
                return 0.0

        # 2 + 3. Size and exposure caps — the lower binds.
        capped = min(target_weight, lim.max_position_frac, lim.max_total_exposure)

        # 4. Drawdown breaker: past the halt threshold, forbid *adding* exposure.
        drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
        if drawdown >= lim.max_drawdown_halt:
            current_weight = position.base_qty * price / equity
            capped = min(capped, current_weight)

        return capped
