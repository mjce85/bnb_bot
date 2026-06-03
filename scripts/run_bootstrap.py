#!/usr/bin/env python
"""Bootstrap confidence bands — is the result one lucky path, or robust?

Paired stationary block bootstrap of the 4-token portfolio's daily returns vs the
equal-weight buy-and-hold portfolio. We resample ~1-month blocks (preserving
short-term autocorrelation) to build thousands of alternate histories, applying
the SAME resampled calendar to strategy and hold so the comparison stays fair.
Reports confidence intervals on the strategy's return, drawdown, and Sharpe, and
— the headline question — the fraction of alternate histories in which the
strategy's drawdown still beats holding's.

Writes reports/bootstrap_summary.md and docs/bootstrap.png. Network: ccxt on miss.
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bnb_bot import config  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.portfolio import (
    buy_and_hold_portfolio,
    run_portfolio_backtest,
)  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
BLOCK = 21  # ~1 month of daily bars
N_RESAMPLES = 3000
SEED = 20260603
PPY = 365.25


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _returns(curve) -> np.ndarray:
    eq = np.array([e for _, e in curve], dtype=float)
    return eq[1:] / eq[:-1] - 1.0


def _max_dd(rets: np.ndarray) -> float:
    eq = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(eq)
    return float(np.max((peak - eq) / peak))


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    cbs = {}
    for sym in config.TOKEN_SET:
        try:
            cbs[sym] = load_or_fetch(sym, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"SKIP {sym}: {e}")

    strat = run_portfolio_backtest(
        cbs,
        lambda s: ENTRY.build_strategy(),
        risk=ENTRY.build_risk(),
        max_total_exposure=ENTRY.risk_limits.max_total_exposure,
        rebalance_band=ENTRY.rebalance_band,
    )
    hold = buy_and_hold_portfolio(cbs)
    rs, rh = _returns(strat.equity_curve), _returns(hold.equity_curve)
    T = len(rs)
    print(f"{T} daily returns; {N_RESAMPLES} resamples, block {BLOCK}.")

    rng = np.random.default_rng(SEED)
    n_blocks = math.ceil(T / BLOCK)
    tot_s, dd_s, dd_h, shp_s = [], [], [], []
    for _ in range(N_RESAMPLES):
        starts = rng.integers(0, T, size=n_blocks)
        idx = np.concatenate([(np.arange(s, s + BLOCK) % T) for s in starts])[:T]
        b_s, b_h = rs[idx], rh[idx]
        tot_s.append(float(np.prod(1.0 + b_s) - 1.0))
        dd_s.append(_max_dd(b_s))
        dd_h.append(_max_dd(b_h))
        sd = b_s.std(ddof=1)
        shp_s.append(float(b_s.mean() / sd * math.sqrt(PPY)) if sd > 0 else 0.0)

    tot_s = np.array(tot_s)
    dd_s = np.array(dd_s)
    dd_h = np.array(dd_h)
    shp_s = np.array(shp_s)
    dd_reduction = dd_h - dd_s  # positive = strategy drew down less
    p_dd_better = float(np.mean(dd_s < dd_h))

    def ci(a):
        return np.percentile(a, 5), np.percentile(a, 50), np.percentile(a, 95)

    rows = [
        ("Total return", ci(tot_s), _pct),
        ("Max drawdown", ci(dd_s), _pct),
        ("Sharpe (ann.)", ci(shp_s), lambda x: f"{x:.2f}"),
        ("Drawdown reduction vs hold", ci(dd_reduction), _pct),
    ]
    print(f"\nP(strategy drawdown < hold drawdown) = {p_dd_better*100:.1f}%")
    for name, (lo, mid, hi), fmt in rows:
        print(f"  {name:30s} median {fmt(mid):>8s}  [5–95%: {fmt(lo)} … {fmt(hi)}]")

    _figure(tot_s, dd_s, dd_h, dd_reduction)
    _write_summary(rows, p_dd_better, T)
    return 0


def _figure(tot_s, dd_s, dd_h, dd_reduction) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.2))
    ax1.hist(tot_s * 100, bins=50, color="#16a34a", alpha=0.8)
    ax1.axvline(np.median(tot_s) * 100, color="#111827", ls="--", lw=1)
    ax1.set_title("Bootstrapped total return")
    ax1.set_xlabel("total return (%)")
    ax1.set_ylabel("resamples")

    ax2.hist(dd_reduction * 100, bins=50, color="#2563eb", alpha=0.8)
    ax2.axvline(0, color="#dc2626", ls="--", lw=1.2, label="0 = no improvement")
    ax2.set_title("Drawdown reduction vs buy & hold (positive = better)")
    ax2.set_xlabel("hold drawdown − strategy drawdown (pp)")
    ax2.legend(fontsize=8)
    fig.suptitle(
        "Bootstrap (paired block resample of portfolio daily returns)", fontsize=12
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/bootstrap.png", dpi=120)
    plt.close(fig)
    print("Wrote docs/bootstrap.png")


def _write_summary(rows, p_dd_better, T) -> None:
    os.makedirs("reports", exist_ok=True)
    lines = [
        "# Bootstrap summary — confidence bands on the portfolio result",
        "",
        f"Paired stationary block bootstrap (block {BLOCK} days, {N_RESAMPLES} "
        f"resamples, seed {SEED}) of the 4-token portfolio's {T} daily returns vs "
        f"equal-weight buy-and-hold, {WINDOW_START}→{WINDOW_END}. The same resampled "
        "calendar is applied to both, so each alternate history is a fair fight.",
        "",
        f"**In {p_dd_better*100:.1f}% of {N_RESAMPLES} alternate histories the "
        "strategy's max drawdown was smaller than buy-and-hold's.**",
        "",
        "![bootstrap distributions](../docs/bootstrap.png)",
        "",
        "| Metric | Median | 5th pct | 95th pct |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, (lo, mid, hi), fmt in rows:
        lines.append(f"| {name} | {fmt(mid)} | {fmt(lo)} | {fmt(hi)} |")
    lines += [
        "",
        "Caveat: a return bootstrap measures *path/sampling* variability of the "
        "realized return stream; it cannot capture regime risk the strategy never "
        "encountered. See the regime-slice stress test for that.",
        "",
    ]
    with open("reports/bootstrap_summary.md", "w") as f:
        f.write("\n".join(lines))
    print("Summary: reports/bootstrap_summary.md")


if __name__ == "__main__":
    raise SystemExit(main())
