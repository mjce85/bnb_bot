"""Event-driven backtest engine — the credibility core of bnb_bot.

The whole product is *backtest honesty*. This engine is built so the three
classic backtest lies cannot creep in:

1. **No lookahead.** The decision at bar *t* is computed from a causal slice
   ``candles[: t + 1]`` — the strategy is physically handed only bars with
   timestamp ≤ *t*. That decision is executed at the *next* bar's open
   (``candles[t + 1].open``), never the same bar's close. A test pins this by
   feeding two series that differ only in the future and asserting identical
   fills up to the divergence point.

2. **Unmodeled costs.** Every fill pays swap fee + slippage + gas, taken from
   :class:`bnb_bot.config.CostModel`. There is no cost-free path through this
   code.

3. (Overfitting is guarded at the *experiment* level — walk-forward holdout in
   the baseline run — not here.)

Model: single-symbol, long-only **target-weight allocation**. At each bar the
strategy emits a target weight in ``[0, 1]`` (fraction of equity to hold). The
engine rebalances the position toward that weight at the next open, charging
costs on the traded notional.
"""

from __future__ import annotations

from typing import Callable, Optional, Protocol, Union, runtime_checkable

from bnb_bot import config
from bnb_bot.types import BacktestResult, Candle, Fill, Position, Side


@runtime_checkable
class SignalSource(Protocol):
    """Anything that turns a causal candle history into a target weight.

    ``history`` is ``candles[: t + 1]`` — every bar up to and including the
    decision bar, and *nothing after it*. Return a target weight in ``[0, 1]``;
    the engine clamps defensively but a strategy should stay in range.
    """

    def signal(self, history: list[Candle]) -> float: ...


# A strategy may be a SignalSource (object with ``.signal``) or a bare callable
# ``history -> float``. Both are accepted; both get the same causal slice.
StrategyLike = Union[SignalSource, Callable[[list[Candle]], float]]


@runtime_checkable
class RiskManager(Protocol):
    """Hook for T5 risk rules. Given the raw target weight and current state,
    return the risk-adjusted target weight (e.g. 0.0 to force flat on a stop,
    or a capped weight for position sizing). Default behaviour (no manager) is
    identity — the raw strategy weight is used as-is.
    """

    def adjust(
        self,
        *,
        target_weight: float,
        equity: float,
        peak_equity: float,
        position: Position,
        price: float,
    ) -> float: ...


def _as_signal_fn(strategy: StrategyLike) -> Callable[[list[Candle]], float]:
    if hasattr(strategy, "signal"):
        return strategy.signal  # type: ignore[return-value]
    if callable(strategy):
        return strategy
    raise TypeError(
        "strategy must be a SignalSource (have a .signal(history) method) or a "
        f"callable history->float; got {type(strategy).__name__}"
    )


def _clamp_weight(w: float) -> float:
    if w != w:  # NaN
        raise ValueError("strategy returned NaN target weight")
    return 0.0 if w < 0.0 else 1.0 if w > 1.0 else w


def run_backtest(
    candles: list[Candle],
    strategy: StrategyLike,
    *,
    symbol: str,
    starting_equity: float = config.STARTING_EQUITY_USD,
    costs: config.CostModel = config.DEFAULT_COSTS,
    risk: Optional[RiskManager] = None,
    min_trade_usd: float = 1.0,
    rebalance_band: float = 0.0,
    strategy_name: str = "strategy",
    params: Optional[dict] = None,
) -> BacktestResult:
    """Simulate ``strategy`` on ``candles`` and return a :class:`BacktestResult`.

    Parameters
    ----------
    candles:
        Contiguous OHLCV series (validate with :func:`bnb_bot.data.assert_contiguous`
        upstream). Must hold at least two bars — one to decide on, one to fill at.
    strategy:
        A :class:`SignalSource` or ``history -> float`` callable. Called once per
        bar with the causal slice ``candles[: t + 1]``.
    symbol:
        Traded symbol, recorded on fills and the result.
    starting_equity:
        Opening cash (USD). The book starts 100% cash.
    costs:
        Swap fee / slippage / gas charged on every fill.
    risk:
        Optional risk manager that may rewrite the target weight per bar (T5).
    min_trade_usd:
        Absolute floor: rebalances whose traded notional is below this are
        skipped, so micro-drift doesn't bleed equity through gas. Not a strategy
        parameter — purely an engine hygiene knob.
    rebalance_band:
        Relative tolerance, as a fraction of equity. A rebalance is skipped
        unless the position is off-target by more than ``rebalance_band *
        equity``. ``0.0`` (default) means follow the target weight exactly every
        bar; a small band (e.g. ``0.02``) stops a held position from churning
        fees on tiny drift. The two floors compose — a trade must clear *both*.
    """
    n = len(candles)
    if n < 2:
        raise ValueError(
            f"need at least 2 candles to backtest (one to decide, one to fill); "
            f"got {n}"
        )
    if starting_equity <= 0:
        raise ValueError(f"starting_equity must be > 0, got {starting_equity}")

    signal_fn = _as_signal_fn(strategy)
    slip = costs.slippage_bps / 10_000.0

    cash = starting_equity
    pos = Position(symbol=symbol)
    fills: list[Fill] = []
    equity_curve: list[tuple[int, float]] = []
    peak_equity = starting_equity

    # `pending_target` is the weight decided at the PREVIOUS bar, awaiting
    # execution at THIS bar's open. None means "no decision to execute yet".
    pending_target: Optional[float] = None

    for i in range(n):
        bar = candles[i]

        # 1. Execute the decision made at bar i-1, at THIS bar's open.
        if pending_target is not None:
            open_price = bar.open
            equity_at_exec = cash + pos.base_qty * open_price
            if equity_at_exec > peak_equity:
                peak_equity = equity_at_exec

            target_w = pending_target
            if risk is not None:
                target_w = _clamp_weight(
                    risk.adjust(
                        target_weight=target_w,
                        equity=equity_at_exec,
                        peak_equity=peak_equity,
                        position=pos,
                        price=open_price,
                    )
                )

            cash, fill = _rebalance(
                cash=cash,
                pos=pos,
                target_weight=target_w,
                open_price=open_price,
                ts=bar.ts,
                symbol=symbol,
                costs=costs,
                slip=slip,
                min_trade_usd=min_trade_usd,
                rebalance_band=rebalance_band,
            )
            if fill is not None:
                fills.append(fill)

        # 2. Decide for bar i from a strictly causal slice, to fill at i+1 open.
        #    The last bar has no next open, so no decision is taken there.
        if i < n - 1:
            raw = signal_fn(candles[: i + 1])
            pending_target = _clamp_weight(raw)
        else:
            pending_target = None

        # 3. Mark equity to this bar's close and record the curve point.
        equity = cash + pos.base_qty * bar.close
        if equity > peak_equity:
            peak_equity = equity
        equity_curve.append((bar.ts, equity))

    return BacktestResult(
        strategy=strategy_name,
        symbol=symbol,
        window=(candles[0].ts, candles[-1].ts),
        params=dict(params or {}),
        equity_curve=equity_curve,
        fills=fills,
    )


def _rebalance(
    *,
    cash: float,
    pos: Position,
    target_weight: float,
    open_price: float,
    ts: int,
    symbol: str,
    costs: config.CostModel,
    slip: float,
    min_trade_usd: float,
    rebalance_band: float,
) -> tuple[float, Optional[Fill]]:
    """Move ``pos`` toward ``target_weight`` of equity at ``open_price``.

    Sizing reference is the *pre-slippage* open: ``target_qty`` is chosen so the
    position would be exactly ``target_weight`` of equity if filled at the open.
    Slippage and fees are then charged on the realized fill, so the book ends up
    slightly under target — that shortfall is the honest cost of trading.

    Mutates ``pos`` in place; returns the new cash balance and the resulting
    :class:`Fill` (or ``None`` if the trade was too small to bother with).
    """
    equity = cash + pos.base_qty * open_price
    target_notional = target_weight * equity
    target_qty = target_notional / open_price
    delta_qty = target_qty - pos.base_qty
    trade_notional = abs(delta_qty) * open_price

    if trade_notional < min_trade_usd or trade_notional < rebalance_band * equity:
        return cash, None

    if delta_qty > 0:  # BUY — slippage pushes the fill price up
        eff_price = open_price * (1.0 + slip)
        notional = delta_qty * eff_price
        fee = costs.swap_fee * notional + costs.gas_usd
        cash -= notional + fee
        new_qty = pos.base_qty + delta_qty
        pos.avg_entry = (pos.avg_entry * pos.base_qty + eff_price * delta_qty) / new_qty
        pos.base_qty = new_qty
        side = Side.BUY
        filled_qty = delta_qty
    else:  # SELL — slippage pushes the fill price down
        sell_qty = -delta_qty
        eff_price = open_price * (1.0 - slip)
        notional = sell_qty * eff_price
        fee = costs.swap_fee * notional + costs.gas_usd
        cash += notional - fee
        pos.base_qty -= sell_qty
        if pos.base_qty <= 1e-12:  # fully closed — clear residual dust
            pos.base_qty = 0.0
            pos.avg_entry = 0.0
        side = Side.SELL
        filled_qty = sell_qty

    fill = Fill(
        ts=ts,
        symbol=symbol,
        side=side,
        base_qty=filled_qty,
        price=eff_price,
        fee_usd=fee,
    )
    return cash, fill
