#!/usr/bin/env python
"""A/B tournament: the locked entry vs three creative challengers.

Same honest rig for everyone — daily bars 2021→2026, identical costs, the same
risk overlay (stop-loss + drawdown breaker) and rebalance band, no look-ahead, and
all parameters chosen by CONVENTION (never searched on this data). We measure each
on the FULL window and on the recent **holdout tail** (last 25% of the timeline,
read off the same continuously-warmed run — so slower signals aren't unfairly
cold-started).

Contestants:
  - ENTRY      : vol-targeted regime momentum (our champion)
  - donchian   : Turtle breakout 20/10 (stays long the whole trend)
  - tsmom      : 12-month time-series momentum (long while 365d return > 0)
  - rotation   : dual-momentum, hold top-2 by 90d return, cash if none positive
  - hold       : equal-weight buy & hold (benchmark)

    ./venv/bin/python scripts/run_ab_challengers.py   # -> reports/ab_challengers_summary.md
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.portfolio import (  # noqa: E402
    PortfolioResult,
    buy_and_hold_portfolio,
    run_portfolio_backtest,
    run_rotation_backtest,
)
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.rotation import dual_momentum_allocator  # noqa: E402
from bnb_bot.strategy import (  # noqa: E402
    DonchianBreakout,
    TimeSeriesMomentum,
)
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

FULL_START, WINDOW_END, TIMEFRAME, OUT_DIR = "2021-01-01", "2026-06-01", "1d", "reports"
HOLDOUT_FRAC = 0.25
RB = ENTRY.rebalance_band  # same execution friction for everyone


def _ms(s):
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x):
    return f"{x * 100:.1f}%"


def _ratio(x):
    if x in (float("inf"), float("-inf")):
        return "+inf" if x > 0 else "-inf"
    return f"{x:.2f}"


def _tail(curve):
    """Last HOLDOUT_FRAC of an equity curve (recent, unseen-ish performance)."""
    k = int(len(curve) * (1.0 - HOLDOUT_FRAC))
    return curve[k:]


def _metrics_of(curve, fills=()):
    res = PortfolioResult(
        symbols=[],
        window=(curve[0][0], curve[-1][0]),
        equity_curve=list(curve),
        fills=list(fills),
    )
    return compute_metrics(res)


# --- portfolio runs (one per contestant) -------------------------------


def _pf_entry(cbs):
    return run_portfolio_backtest(
        cbs,
        lambda s: ENTRY.build_strategy(),
        risk=ENTRY.build_risk(),
        max_total_exposure=1.0,
        rebalance_band=RB,
    )


def _pf_perasset(cbs, make):
    return run_portfolio_backtest(
        cbs,
        lambda s: make(),
        risk=ENTRY.build_risk(),
        max_total_exposure=1.0,
        rebalance_band=RB,
    )


def _pf_rotation(cbs):
    return run_rotation_backtest(
        cbs,
        dual_momentum_allocator(lookback=90, top_k=2),
        risk=ENTRY.build_risk(),
        max_total_exposure=1.0,
        rebalance_band=RB,
    )


def _row(label, m):
    return (
        f"| {label} | {_pct(m.total_return)} | {_pct(m.max_drawdown)} | "
        f"{_ratio(m.sharpe)} | {_ratio(m.calmar)} |"
    )


def main() -> int:
    lo, hi = _ms(FULL_START), _ms(WINDOW_END)
    cbs = {}
    for sym in config.TOKEN_SET:
        try:
            cbs[sym] = load_or_fetch(sym, TIMEFRAME, lo, hi)
        except DataGapError as e:
            print(f"SKIP {sym}: {e}")

    contestants = {
        "ENTRY (vol-tgt regime mom)": _pf_entry(cbs),
        "donchian 20/10 breakout": _pf_perasset(cbs, DonchianBreakout),
        "tsmom 365d": _pf_perasset(cbs, TimeSeriesMomentum),
        "rotation (dual-mom top2/90d)": _pf_rotation(cbs),
    }
    hold = buy_and_hold_portfolio(cbs)

    lines = [
        "# A/B tournament — entry vs creative challengers",
        "",
        "Daily 2021→2026, 4-token shared book. Identical costs, risk overlay, and "
        f"rebalance band ({RB}) for all; parameters by convention, not searched. "
        "Holdout = last 25% of the (continuously-warmed) run.",
        "",
        "## Portfolio — FULL window",
        "",
        "| Strategy | Return | MaxDD | Sharpe | Calmar |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    print("FULL window (portfolio):")
    for label, res in contestants.items():
        m = compute_metrics(res)
        lines.append(_row(label, m))
        print(
            f"  {label:30s} ret {_pct(m.total_return):>9s}  DD {_pct(m.max_drawdown):>6s}  "
            f"Sharpe {_ratio(m.sharpe)}  Calmar {_ratio(m.calmar)}"
        )
    mh = compute_metrics(hold)
    lines.append(_row("equal-weight hold", mh))
    print(
        f"  {'equal-weight hold':30s} ret {_pct(mh.total_return):>9s}  DD {_pct(mh.max_drawdown):>6s}  "
        f"Sharpe {_ratio(mh.sharpe)}  Calmar {_ratio(mh.calmar)}"
    )

    lines += [
        "",
        "## Portfolio — HOLDOUT tail (last 25%)",
        "",
        "| Strategy | Return | MaxDD | Sharpe | Calmar |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    print("\nHOLDOUT tail (portfolio):")
    for label, res in contestants.items():
        m = _metrics_of(_tail(res.equity_curve))
        lines.append(_row(label, m))
        print(
            f"  {label:30s} ret {_pct(m.total_return):>9s}  DD {_pct(m.max_drawdown):>6s}  "
            f"Sharpe {_ratio(m.sharpe)}  Calmar {_ratio(m.calmar)}"
        )
    mht = _metrics_of(_tail(hold.equity_curve))
    lines.append(_row("equal-weight hold", mht))
    print(
        f"  {'equal-weight hold':30s} ret {_pct(mht.total_return):>9s}  DD {_pct(mht.max_drawdown):>6s}  "
        f"Sharpe {_ratio(mht.sharpe)}  Calmar {_ratio(mht.calmar)}"
    )

    # --- Per-token, full window (rotation is portfolio-only -> N/A) ---
    lines += [
        "",
        "## Per token — FULL window return / maxDD (Calmar)",
        "",
        "| Token | ENTRY | donchian | tsmom | buy & hold |",
        "| --- | --- | --- | --- | --- |",
    ]
    print("\nPer token (ret / DD / Calmar):")

    def _single(candles, sym, make):
        res = run_backtest(
            candles,
            make(),
            symbol=sym,
            risk=ENTRY.build_risk(),
            rebalance_band=RB,
            strategy_name="ab",
        )
        return compute_metrics(res)

    for sym, candles in cbs.items():
        e = _single(candles, sym, ENTRY.build_strategy)
        d = _single(candles, sym, DonchianBreakout)
        t = _single(candles, sym, TimeSeriesMomentum)
        h = compute_metrics(buy_and_hold(candles, symbol=sym))

        def cell(m):
            return (
                f"{_pct(m.total_return)} / {_pct(m.max_drawdown)} ({_ratio(m.calmar)})"
            )

        lines.append(f"| {sym} | {cell(e)} | {cell(d)} | {cell(t)} | {cell(h)} |")
        print(
            f"  {sym:9s} ENTRY {cell(e)} | donch {cell(d)} | tsmom {cell(t)} | hold {cell(h)}"
        )
    lines.append("")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "ab_challengers_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
