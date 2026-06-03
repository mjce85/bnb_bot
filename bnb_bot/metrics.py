"""Performance metrics computed from a :class:`BacktestResult`.

These are the numbers the hackathon is judged on — returns, max drawdown,
risk-adjusted performance — so they are computed only from the engine's two
honest outputs: the mark-to-market **equity curve** and the realized **fills**.
Nothing here re-simulates or peeks at data the engine didn't already pay costs
on.

Conventions (stated loud, because a hidden convention is a quiet lie):

* **Periods** are the bars of the equity curve. Annualization factor is derived
  from the *median* spacing of the curve's timestamps (e.g. 1h bars ->
  ~8766 periods/year), not assumed — so a daily and an hourly run annualize
  correctly without being told the timeframe.
* **Sharpe / Sortino** use per-bar simple returns and the *sample* standard
  deviation (ddof=1). Risk-free defaults to 0 (crypto, no honest cash rate).
  A flat equity curve has zero volatility and therefore an undefined ratio;
  we report ``0.0`` there (no risk signal) rather than crash or emit NaN.
* **Max drawdown** is the largest peak-to-trough fall of the equity curve,
  as a positive fraction (0.20 == a 20% drop).
* **Calmar** is CAGR / max drawdown. With no drawdown it is ``+inf`` for a
  winning run, ``0.0`` for a flat one.
* **Win rate** replays the fills with average-cost accounting in which *every*
  cost (swap fee, slippage, gas) is folded into the basis, so the sum of
  realized PnL over a fully-closed book equals the equity-curve P&L exactly.
  It is the fraction of position-reducing fills (sells) that realized a profit.
* **Exposure** is time-in-market: the fraction of bars on which a position was
  held, reconstructed by replaying fills against the curve's timestamps.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass

from bnb_bot.types import BacktestResult, Side

_MS_PER_YEAR = 365.25 * 24 * 60 * 60 * 1000.0


@dataclass(frozen=True)
class Metrics:
    """Scored performance summary of one backtest run."""

    total_return: float  # (final / initial) - 1
    cagr: float  # compound annual growth rate
    max_drawdown: float  # positive fraction, e.g. 0.20 == -20%
    sharpe: float  # annualized, rf=0, sample std
    sortino: float  # annualized, downside deviation only
    calmar: float  # cagr / max_drawdown (+inf if no drawdown)
    win_rate: float  # fraction of profitable closing fills
    exposure: float  # fraction of bars holding a position
    n_trades: int  # total fills
    n_bars: int  # equity-curve points
    periods_per_year: float  # annualization factor used

    def as_dict(self) -> dict:
        return asdict(self)


def _periods_per_year(timestamps: list[int]) -> float:
    """Annualization factor from the median bar spacing (epoch ms)."""
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:]) if b > a]
    if not deltas:
        raise ValueError(
            "cannot infer bar spacing: equity-curve timestamps are not strictly "
            "increasing — the engine should emit one rising point per bar"
        )
    bar_ms = statistics.median(deltas)
    return _MS_PER_YEAR / bar_ms


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for e in equity:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (peak - e) / peak
            if dd > worst:
                worst = dd
    return worst


def _win_rate(result: BacktestResult) -> float:
    """Average-cost replay; fraction of sells that realized positive PnL.

    Cost basis folds in slippage *and* fees on the buy side; sell proceeds are
    net of the sell fee. So realized PnL ties out to the equity curve.
    """
    qty = 0.0
    basis = 0.0  # all-in cost of the currently held qty (USD)
    closes = 0
    wins = 0
    for f in result.fills:
        if f.side is Side.BUY:
            qty += f.base_qty
            basis += f.base_qty * f.price + f.fee_usd
        else:  # SELL — realize against average cost
            if qty <= 0:
                continue  # nothing open to close; skip defensively
            avg_cost = basis / qty
            sell_qty = min(f.base_qty, qty)
            proceeds = sell_qty * f.price - f.fee_usd
            realized = proceeds - sell_qty * avg_cost
            basis -= sell_qty * avg_cost
            qty -= sell_qty
            if qty <= 1e-12:
                qty = 0.0
                basis = 0.0
            closes += 1
            if realized > 0:
                wins += 1
    return wins / closes if closes else 0.0


def _exposure(result: BacktestResult) -> float:
    """Fraction of bars on which a position was held (time in market).

    A fill at a bar's open changes the qty held through that bar's close, so a
    bar at timestamp ``ts`` reflects all fills with ``f.ts <= ts``.
    """
    n_bars = len(result.equity_curve)
    if n_bars == 0:
        return 0.0
    fills = sorted(result.fills, key=lambda f: f.ts)
    qty = 0.0
    fi = 0
    held = 0
    for ts, _ in result.equity_curve:
        while fi < len(fills) and fills[fi].ts <= ts:
            f = fills[fi]
            qty += f.base_qty if f.side is Side.BUY else -f.base_qty
            fi += 1
        if qty > 1e-12:
            held += 1
    return held / n_bars


def compute_metrics(
    result: BacktestResult,
    *,
    periods_per_year: float | None = None,
    risk_free_rate: float = 0.0,
) -> Metrics:
    """Compute scored metrics from a finished :class:`BacktestResult`.

    Parameters
    ----------
    result:
        A completed run. Its ``equity_curve`` must have at least two points
        (one return interval) or there is nothing to measure.
    periods_per_year:
        Override the annualization factor. Default: inferred from bar spacing.
    risk_free_rate:
        Annual risk-free rate for Sharpe/Sortino. Default 0.0 (crypto).
    """
    curve = result.equity_curve
    if len(curve) < 2:
        raise ValueError(
            f"need at least 2 equity points to compute metrics; got {len(curve)} "
            "— run the backtest over more bars"
        )

    timestamps = [ts for ts, _ in curve]
    equity = [e for _, e in curve]
    if equity[0] <= 0:
        raise ValueError(
            f"starting equity must be > 0 to compute returns; got {equity[0]}"
        )

    ppy = (
        periods_per_year
        if periods_per_year is not None
        else _periods_per_year(timestamps)
    )

    total_return = equity[-1] / equity[0] - 1.0

    # CAGR over the elapsed span (number of return intervals / periods per year).
    n_intervals = len(equity) - 1
    years = n_intervals / ppy
    growth = equity[-1] / equity[0]
    if years > 0 and growth > 0:
        try:
            cagr = growth ** (1.0 / years) - 1.0
        except OverflowError:
            # Annualizing a large move over a tiny window (e.g. doubling in two
            # hours) explodes past float range. The honest reading is "absurdly
            # large" — surface that as +/-inf rather than a fake finite number.
            cagr = float("inf") if growth > 1.0 else -1.0
    else:
        cagr = total_return

    max_dd = _max_drawdown(equity)

    # Per-bar simple returns.
    rets = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    rf_per_period = risk_free_rate / ppy
    excess = [r - rf_per_period for r in rets]
    mean_excess = statistics.mean(excess)

    if len(excess) >= 2:
        sd = statistics.stdev(excess)  # sample std, ddof=1
    else:
        sd = 0.0
    sharpe = (mean_excess / sd) * math.sqrt(ppy) if sd > 0 else 0.0

    downside = [min(0.0, x) for x in excess]
    dd_var = sum(x * x for x in downside) / len(downside)
    downside_dev = math.sqrt(dd_var)
    sortino = (mean_excess / downside_dev) * math.sqrt(ppy) if downside_dev > 0 else 0.0

    if max_dd > 0:
        calmar = cagr / max_dd
    else:
        calmar = float("inf") if cagr > 0 else 0.0

    return Metrics(
        total_return=total_return,
        cagr=cagr,
        max_drawdown=max_dd,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        win_rate=_win_rate(result),
        exposure=_exposure(result),
        n_trades=len(result.fills),
        n_bars=len(curve),
        periods_per_year=ppy,
    )
