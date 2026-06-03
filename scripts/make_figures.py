#!/usr/bin/env python
"""Generate the committed headline figure for the submission.

Produces ``docs/headline.png``: one row per token, left = equity curve (log
scale, strategy vs buy-and-hold), right = underwater drawdown (strategy vs
buy-and-hold). The right column is the pitch — our drawdowns are visibly
shallower. Unlike ``reports/`` (gitignored run outputs), ``docs/`` is committed
so the figure shows up on GitHub for judges.

Network: fetches daily history via ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
OUT = "docs/headline.png"

STRAT_COLOR = "#2563eb"
BH_COLOR = "#9ca3af"


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _curve(result):
    ts = [
        datetime.fromtimestamp(t / 1000.0, tz=timezone.utc)
        for t, _ in result.equity_curve
    ]
    eq = [e for _, e in result.equity_curve]
    peak = eq[0]
    dd = []
    for e in eq:
        peak = max(peak, e)
        dd.append((peak - e) / peak * 100.0 if peak > 0 else 0.0)
    return ts, eq, dd


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    tokens = []
    for symbol in config.TOKEN_SET:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"SKIP {symbol}: {e}")
            continue
        s_res = run_backtest(
            candles,
            ENTRY.build_strategy(),
            symbol=symbol,
            risk=ENTRY.build_risk(),
            rebalance_band=ENTRY.rebalance_band,
        )
        b_res = buy_and_hold(candles, symbol=symbol)
        tokens.append(
            (symbol, s_res, compute_metrics(s_res), b_res, compute_metrics(b_res))
        )

    n = len(tokens)
    fig, axes = plt.subplots(n, 2, figsize=(12, 3.2 * n))
    if n == 1:
        axes = [axes]

    for row, (symbol, s_res, s_m, b_res, b_m) in enumerate(tokens):
        ts, s_eq, s_dd = _curve(s_res)
        _, b_eq, b_dd = _curve(b_res)

        ax_eq = axes[row][0]
        ax_eq.plot(ts, b_eq, color=BH_COLOR, lw=1.1, label="buy & hold")
        ax_eq.plot(ts, s_eq, color=STRAT_COLOR, lw=1.3, label="strategy")
        ax_eq.set_yscale("log")
        ax_eq.set_ylabel(f"{symbol}\nequity (USD, log)")
        ax_eq.grid(True, alpha=0.3)
        if row == 0:
            ax_eq.set_title("Equity (log scale)")
            ax_eq.legend(loc="upper left", fontsize=8)

        ax_dd = axes[row][1]
        ax_dd.fill_between(ts, b_dd, 0, color=BH_COLOR, alpha=0.5, label="buy & hold")
        ax_dd.fill_between(ts, s_dd, 0, color=STRAT_COLOR, alpha=0.5, label="strategy")
        ax_dd.invert_yaxis()
        ax_dd.set_ylabel("drawdown (%)")
        ax_dd.grid(True, alpha=0.3)
        if row == 0:
            ax_dd.set_title("Drawdown — shallower is better")
            ax_dd.legend(loc="lower left", fontsize=8)
        ax_dd.text(
            0.98,
            0.06,
            f"maxDD {s_m.max_drawdown*100:.0f}% vs {b_m.max_drawdown*100:.0f}%",
            transform=ax_dd.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            bbox=dict(boxstyle="round", fc="white", ec="#d1d5db", alpha=0.8),
        )

    fig.suptitle(
        f"{ENTRY.name} vs buy & hold — daily, {WINDOW_START}…{WINDOW_END}",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    os.makedirs("docs", exist_ok=True)
    fig.savefig(OUT, dpi=120)
    plt.close(fig)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
