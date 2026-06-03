#!/usr/bin/env python
"""Portfolio backtest — the locked entry traded across all tokens at once.

This is the "what you'd actually run" result: the locked preset applied to every
token on a single shared book, with the portfolio-level total-exposure cap doing
real work. Compared to an equal-weight buy-and-hold portfolio benchmark, and
contrasted with the average single-token drawdown to show the diversification
benefit. Full window + 5 independent folds. Writes reports/portfolio_summary.md
and the committed figure docs/portfolio.png.

Equity-curve metrics (return, drawdown, Sharpe, Sortino, Calmar) are reported;
fill-derived win-rate/exposure are omitted (they aren't meaningful across mixed
symbols). Network: ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bnb_bot import config  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.portfolio import (
    buy_and_hold_portfolio,
    run_portfolio_backtest,
)  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
N_FOLDS = 5
OUT_DIR = "reports"


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _ratio(x: float) -> str:
    if x in (float("inf"), float("-inf")):
        return "+inf" if x > 0 else "-inf"
    return f"{x:.2f}"


def _run_portfolio(cbs: dict):
    return run_portfolio_backtest(
        cbs,
        lambda sym: ENTRY.build_strategy(),
        risk=ENTRY.build_risk(),
        max_total_exposure=ENTRY.risk_limits.max_total_exposure,
        rebalance_band=ENTRY.rebalance_band,
    )


def _slice(cbs: dict, lo: int, hi: int) -> dict:
    return {s: [c for c in cands if lo <= c.ts < hi] for s, cands in cbs.items()}


def _drawdown_series(curve):
    ts = [datetime.fromtimestamp(t / 1000, tz=timezone.utc) for t, _ in curve]
    eq = [e for _, e in curve]
    peak, dd = eq[0], []
    for e in eq:
        peak = max(peak, e)
        dd.append((peak - e) / peak * 100.0 if peak > 0 else 0.0)
    return ts, eq, dd


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    cbs = {}
    single_dds = []
    for symbol in config.TOKEN_SET:
        try:
            cbs[symbol] = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"SKIP {symbol}: {e}")

    # Full-window portfolio vs equal-weight buy & hold.
    strat = _run_portfolio(cbs)
    bench = buy_and_hold_portfolio(cbs)
    m, bm = compute_metrics(strat), compute_metrics(bench)

    # Single-token strategy drawdowns (for the diversification contrast).
    for symbol, cands in cbs.items():
        sm = compute_metrics(_run_portfolio({symbol: cands}))
        single_dds.append(sm.max_drawdown)
    avg_single_dd = statistics.mean(single_dds)

    print("=== Full window ===")
    print(
        f"  portfolio       ret {_pct(m.total_return):>8s}  maxDD {_pct(m.max_drawdown):>6s}  "
        f"Sharpe {_ratio(m.sharpe)}  Calmar {_ratio(m.calmar)}"
    )
    print(
        f"  eq-weight hold  ret {_pct(bm.total_return):>8s}  maxDD {_pct(bm.max_drawdown):>6s}  "
        f"Sharpe {_ratio(bm.sharpe)}  Calmar {_ratio(bm.calmar)}"
    )
    print(
        f"  capital use: portfolio maxDD {_pct(m.max_drawdown)} vs "
        f"avg single-token {_pct(avg_single_dd)} "
        "(higher — correlated tokens + fuller deployment, not a free lunch)"
    )

    # Walk-forward folds on the shared timeline.
    common_ts = sorted(set.intersection(*[set(c.ts for c in v) for v in cbs.values()]))
    fold_rows = []
    fold = len(common_ts) // N_FOLDS
    for i in range(N_FOLDS):
        lo = common_ts[i * fold]
        hi = common_ts[(i + 1) * fold] if i < N_FOLDS - 1 else common_ts[-1] + 1
        sub = _slice(cbs, lo, hi)
        fm = compute_metrics(_run_portfolio(sub))
        fbm = compute_metrics(buy_and_hold_portfolio(sub))
        fold_rows.append(
            {
                "i": i,
                "ret": fm.total_return,
                "bh_ret": fbm.total_return,
                "dd": fm.max_drawdown,
                "bh_dd": fbm.max_drawdown,
                "dd_better": fm.max_drawdown < fbm.max_drawdown,
            }
        )
        print(
            f"  fold {i}: ret {_pct(fm.total_return):>8s} (hold {_pct(fbm.total_return):>8s})  "
            f"maxDD {_pct(fm.max_drawdown):>6s} (hold {_pct(fbm.max_drawdown)})  "
            f"DD-better {fm.max_drawdown < fbm.max_drawdown}"
        )

    _figure(strat, bench)
    _write_summary(m, bm, avg_single_dd, single_dds, fold_rows)
    return 0


def _figure(strat, bench) -> None:
    ts, s_eq, s_dd = _drawdown_series(strat.equity_curve)
    _, b_eq, b_dd = _drawdown_series(bench.equity_curve)
    fig, (ax_eq, ax_dd) = plt.subplots(1, 2, figsize=(13, 4.2))
    ax_eq.plot(ts, b_eq, color="#9ca3af", lw=1.2, label="equal-weight buy & hold")
    ax_eq.plot(ts, s_eq, color="#16a34a", lw=1.4, label="portfolio strategy")
    ax_eq.set_yscale("log")
    ax_eq.set_ylabel("equity (USD, log)")
    ax_eq.set_title("Portfolio equity (log)")
    ax_eq.legend(loc="upper left", fontsize=9)
    ax_eq.grid(True, alpha=0.3)
    ax_dd.fill_between(
        ts, b_dd, 0, color="#9ca3af", alpha=0.5, label="equal-weight hold"
    )
    ax_dd.fill_between(
        ts, s_dd, 0, color="#16a34a", alpha=0.5, label="portfolio strategy"
    )
    ax_dd.invert_yaxis()
    ax_dd.set_ylabel("drawdown (%)")
    ax_dd.set_title("Portfolio drawdown — shallower is better")
    ax_dd.legend(loc="lower left", fontsize=9)
    ax_dd.grid(True, alpha=0.3)
    fig.suptitle(
        f"4-token portfolio ({ENTRY.name}) vs equal-weight buy & hold", fontsize=12
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/portfolio.png", dpi=120)
    plt.close(fig)
    print("Wrote docs/portfolio.png")


def _write_summary(m, bm, avg_single_dd, single_dds, fold_rows) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    dd_wins = sum(r["dd_better"] for r in fold_rows)
    lines = [
        "# Portfolio summary",
        "",
        f"The locked entry **{ENTRY.name}** traded across {len(single_dds)} tokens on "
        f"one shared book ({WINDOW_START} → {WINDOW_END}, {TIMEFRAME}), vs an "
        "equal-weight buy-and-hold portfolio. Total-exposure cap "
        f"{_pct(ENTRY.risk_limits.max_total_exposure)}; risk-on. Metrics are "
        "equity-curve based (return, drawdown, Sharpe, Sortino, Calmar).",
        "",
        "## Full window",
        "",
        "| | Return | MaxDD | Sharpe | Sortino | Calmar |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| **Portfolio strategy** | {_pct(m.total_return)} | {_pct(m.max_drawdown)} | "
        f"{_ratio(m.sharpe)} | {_ratio(m.sortino)} | {_ratio(m.calmar)} |",
        f"| Equal-weight buy & hold | {_pct(bm.total_return)} | {_pct(bm.max_drawdown)} | "
        f"{_ratio(bm.sharpe)} | {_ratio(bm.sortino)} | {_ratio(bm.calmar)} |",
        "",
        "## Capital utilization & correlation (honest)",
        "",
        f"Portfolio max drawdown **{_pct(m.max_drawdown)}** is *higher* than the "
        f"average single-token strategy drawdown **{_pct(avg_single_dd)}** "
        f"(per-token: {', '.join(_pct(d) for d in single_dds)}) — not lower. "
        "Two honest reasons: these tokens are highly correlated (they fall "
        "together, so combining them diversifies little), and the portfolio "
        "deploys the cash that single-token runs leave idle. That fuller "
        "deployment is exactly why portfolio *return* is far higher than "
        "equal-weight holding. The benefit here is **capital efficiency vs "
        "holding**, not drawdown reduction vs a single token. Decorrelated "
        "assets would smooth the curve (see `test_diversification_reduces_"
        "drawdown`); this token set isn't decorrelated.",
        "",
        "## Walk-forward (5 independent folds) vs equal-weight hold",
        "",
        f"Drawdown beaten in **{dd_wins}/{len(fold_rows)}** folds.",
        "",
        "| Fold | Return | Hold | MaxDD | Hold MaxDD | DD beaten |",
        "| ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in fold_rows:
        lines.append(
            f"| {r['i']} | {_pct(r['ret'])} | {_pct(r['bh_ret'])} | {_pct(r['dd'])} | "
            f"{_pct(r['bh_dd'])} | {'yes' if r['dd_better'] else 'NO'} |"
        )
    lines.append("")
    path = os.path.join(OUT_DIR, "portfolio_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Summary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
