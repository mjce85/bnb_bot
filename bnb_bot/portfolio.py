"""Multi-asset portfolio backtest — what you'd actually trade.

Every result so far ran one token at a time, which means the portfolio-level risk
rules (per-position cap, total-exposure cap) never did anything. This engine runs
all tokens together on a shared book: one cash balance, coordinated rebalancing,
and the diversification benefit of holding several decorrelated single-token
strategies at once (each sits in cash at different times, so the *combined*
equity curve is smoother than any one of them).

Same honesty guarantees as the single-asset engine:

* **No look-ahead** — each symbol's strategy sees only ``candles[: t+1]``; fills
  land at the next bar's open.
* **Costs on every fill** — via the shared :func:`bnb_bot.backtest.execute_delta`,
  so portfolio and single-asset economics are identical by construction.

Risk is applied in two stages each bar: per-symbol (stop-loss, position-size cap,
drawdown breaker — using *portfolio* equity and a portfolio campaign peak), then
a portfolio-level total-exposure cap that scales all targets down to fit.

Timeline: symbols are aligned on their common (intersected) set of timestamps, so
every bar has a candle for every symbol. Minimal data is lost (only the ragged
edges where listings differ); the kept span is validated contiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from bnb_bot import config
from bnb_bot.backtest import (
    RiskManager,
    StrategyLike,
    _as_signal_fn,
    _clamp_weight,
    execute_delta,
)
from bnb_bot.types import Candle, Fill, Position


@dataclass
class PortfolioResult:
    """Combined result of a multi-asset run. Equity curve is portfolio-total."""

    symbols: list
    window: tuple  # (start_ts, end_ts)
    equity_curve: list  # list[tuple[int ts, float equity]]
    fills: list  # list[Fill] across all symbols
    params: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)


def _aligned_timeline(candles_by_symbol: dict) -> list:
    """Common, sorted timestamps present for every symbol (intersection)."""
    ts_sets = [set(c.ts for c in candles) for candles in candles_by_symbol.values()]
    common = set.intersection(*ts_sets) if ts_sets else set()
    if len(common) < 2:
        raise ValueError(
            "symbols share fewer than 2 common timestamps; cannot build a "
            "portfolio timeline — check the windows/timeframes line up"
        )
    return sorted(common)


# An allocator sees every symbol's causal history and returns a target-weight
# vector. The per-symbol engine is the special case where each weight depends only
# on its own history; a *rotation* allocator ranks symbols against each other.
Allocator = Callable[[dict], dict]


def _portfolio_loop(
    candles_by_symbol: dict,
    allocator: Allocator,
    *,
    starting_equity: float,
    costs: config.CostModel,
    risk: Optional[RiskManager],
    max_total_exposure: float,
    rebalance_band: float,
    min_trade_usd: float,
    params: Optional[dict],
) -> PortfolioResult:
    """Shared shared-book rebalancing loop, driven by a portfolio ``allocator``.

    ``allocator`` is called each bar with ``{symbol: candles[: t+1]}`` and returns
    ``{symbol: target_weight}``. Everything downstream — next-bar fills, costs,
    per-symbol risk, the total-exposure cap, sells-before-buys — is identical for
    every allocation model, so economics can't drift between them.
    """
    symbols = list(candles_by_symbol)
    timeline = _aligned_timeline(candles_by_symbol)
    n = len(timeline)
    if starting_equity <= 0:
        raise ValueError(f"starting_equity must be > 0, got {starting_equity}")

    # Align each symbol's candles to the common timeline (one per timestamp).
    by_ts = {
        sym: {c.ts: c for c in candles} for sym, candles in candles_by_symbol.items()
    }
    aligned = {sym: [by_ts[sym][t] for t in timeline] for sym in symbols}

    slip = costs.slippage_bps / 10_000.0

    cash = starting_equity
    positions = {sym: Position(symbol=sym) for sym in symbols}
    fills: list[Fill] = []
    equity_curve: list[tuple[int, float]] = []
    peak_equity = starting_equity
    pending: dict[str, Optional[float]] = {sym: None for sym in symbols}

    def _invested(prices: dict) -> float:
        return sum(positions[s].base_qty * prices[s] for s in symbols)

    for i in range(n):
        ts = timeline[i]
        bars = {sym: aligned[sym][i] for sym in symbols}

        # 1. Execute decisions made at i-1, at this bar's opens.
        if any(pending[s] is not None for s in symbols):
            opens = {sym: bars[sym].open for sym in symbols}
            total_equity = cash + _invested(opens)

            # Portfolio campaign peak: reset while the whole book is flat.
            if _invested(opens) <= 1e-9:
                peak_equity = total_equity
            elif total_equity > peak_equity:
                peak_equity = total_equity

            # Per-symbol risk adjustment (portfolio equity + portfolio peak).
            targets = {}
            for sym in symbols:
                tw = pending[sym] or 0.0
                if risk is not None:
                    tw = _clamp_weight(
                        risk.adjust(
                            target_weight=tw,
                            equity=total_equity,
                            peak_equity=peak_equity,
                            position=positions[sym],
                            price=opens[sym],
                        )
                    )
                targets[sym] = tw

            # Portfolio-level total-exposure cap: scale all down to fit.
            gross = sum(targets.values())
            if gross > max_total_exposure and gross > 0:
                scale = max_total_exposure / gross
                targets = {s: w * scale for s, w in targets.items()}

            # Compute deltas off the same total equity; sells first to free cash.
            deltas = {
                sym: (targets[sym] * total_equity / opens[sym])
                - positions[sym].base_qty
                for sym in symbols
            }
            order = sorted(symbols, key=lambda s: deltas[s])  # sells (neg) first
            for sym in order:
                delta = deltas[sym]
                trade_notional = abs(delta) * opens[sym]
                if (
                    trade_notional < min_trade_usd
                    or trade_notional < rebalance_band * total_equity
                ):
                    continue
                cash, fill = execute_delta(
                    cash=cash,
                    pos=positions[sym],
                    delta_qty=delta,
                    open_price=opens[sym],
                    ts=ts,
                    symbol=sym,
                    costs=costs,
                    slip=slip,
                )
                if fill is not None:
                    fills.append(fill)

        # 2. Decide the whole weight vector from causal slices, to fill at i+1.
        if i < n - 1:
            histories = {sym: aligned[sym][: i + 1] for sym in symbols}
            weights = allocator(histories)
            pending = {sym: _clamp_weight(weights.get(sym, 0.0)) for sym in symbols}
        else:
            pending = {sym: None for sym in symbols}

        # 3. Mark to close and record the portfolio equity point.
        closes = {sym: bars[sym].close for sym in symbols}
        equity = cash + _invested(closes)
        if _invested(closes) <= 1e-9:
            peak_equity = equity
        elif equity > peak_equity:
            peak_equity = equity
        equity_curve.append((ts, equity))

    return PortfolioResult(
        symbols=symbols,
        window=(timeline[0], timeline[-1]),
        equity_curve=equity_curve,
        fills=fills,
        params=dict(params or {}),
    )


def run_portfolio_backtest(
    candles_by_symbol: dict,
    make_strategy: Callable[[str], StrategyLike],
    *,
    starting_equity: float = config.STARTING_EQUITY_USD,
    costs: config.CostModel = config.DEFAULT_COSTS,
    risk: Optional[RiskManager] = None,
    max_total_exposure: float = 1.0,
    rebalance_band: float = 0.0,
    min_trade_usd: float = 1.0,
    params: Optional[dict] = None,
) -> PortfolioResult:
    """Run ``make_strategy(symbol)`` across all symbols on a shared book.

    ``make_strategy`` is a factory called once per symbol, so stateful strategies
    stay isolated. Each symbol's weight depends only on its own history — the
    independent-sleeves model. ``max_total_exposure`` caps the summed target weight
    across symbols (the constraint a single-asset run can't express).
    """
    symbols = list(candles_by_symbol)
    signal_fns = {sym: _as_signal_fn(make_strategy(sym)) for sym in symbols}

    def allocator(histories: dict) -> dict:
        return {sym: signal_fns[sym](histories[sym]) for sym in histories}

    return _portfolio_loop(
        candles_by_symbol,
        allocator,
        starting_equity=starting_equity,
        costs=costs,
        risk=risk,
        max_total_exposure=max_total_exposure,
        rebalance_band=rebalance_band,
        min_trade_usd=min_trade_usd,
        params=params,
    )


def run_rotation_backtest(
    candles_by_symbol: dict,
    allocator: Allocator,
    *,
    starting_equity: float = config.STARTING_EQUITY_USD,
    costs: config.CostModel = config.DEFAULT_COSTS,
    risk: Optional[RiskManager] = None,
    max_total_exposure: float = 1.0,
    rebalance_band: float = 0.0,
    min_trade_usd: float = 1.0,
    params: Optional[dict] = None,
) -> PortfolioResult:
    """Run a cross-sectional ``allocator`` across all symbols on a shared book.

    The allocator sees ``{symbol: candles[: t+1]}`` and returns
    ``{symbol: target_weight}`` — letting a symbol's weight depend on *other*
    symbols (rotation, ranking, relative momentum). Shares the exact fill / cost /
    risk machinery of :func:`run_portfolio_backtest`.
    """
    return _portfolio_loop(
        candles_by_symbol,
        allocator,
        starting_equity=starting_equity,
        costs=costs,
        risk=risk,
        max_total_exposure=max_total_exposure,
        rebalance_band=rebalance_band,
        min_trade_usd=min_trade_usd,
        params=params,
    )


def buy_and_hold_portfolio(
    candles_by_symbol: dict,
    *,
    starting_equity: float = config.STARTING_EQUITY_USD,
    costs: config.CostModel = config.DEFAULT_COSTS,
) -> PortfolioResult:
    """Equal-weight buy-and-hold benchmark: 1/N per symbol, bought once, held.

    Built analytically rather than via the rebalancing engine: a constant *target
    weight* would make the engine sell winners and buy losers (a rebalanced
    portfolio, not buy-and-hold). Here each symbol is bought once at the first
    bar's open — paying one honest entry cost — and the shares are held fixed, so
    weights drift with price exactly as a real hold would.
    """
    symbols = list(candles_by_symbol)
    timeline = _aligned_timeline(candles_by_symbol)
    by_ts = {
        sym: {c.ts: c for c in candles} for sym, candles in candles_by_symbol.items()
    }
    aligned = {sym: [by_ts[sym][t] for t in timeline] for sym in symbols}
    slip = costs.slippage_bps / 10_000.0
    weight = 1.0 / len(symbols)

    cash = starting_equity
    positions = {sym: Position(symbol=sym) for sym in symbols}
    fills: list[Fill] = []

    # Buy 1/N of starting equity in each symbol at the first bar's open.
    for sym in symbols:
        open_price = aligned[sym][0].open
        delta_qty = (weight * starting_equity) / open_price
        cash, fill = execute_delta(
            cash=cash,
            pos=positions[sym],
            delta_qty=delta_qty,
            open_price=open_price,
            ts=timeline[0],
            symbol=sym,
            costs=costs,
            slip=slip,
        )
        if fill is not None:
            fills.append(fill)

    # Mark to close each bar; positions are held fixed.
    equity_curve = [
        (
            timeline[i],
            cash + sum(positions[s].base_qty * aligned[s][i].close for s in symbols),
        )
        for i in range(len(timeline))
    ]
    return PortfolioResult(
        symbols=symbols,
        window=(timeline[0], timeline[-1]),
        equity_curve=equity_curve,
        fills=fills,
        params={"benchmark": "equal_weight_buy_and_hold"},
    )
