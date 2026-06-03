#!/usr/bin/env python
"""Performance board — every token's equity curve, strategy vs buy & hold.

A grid of small-multiples (docs/performance_all.png): one panel per token, the
locked entry (green) vs buy-and-hold (grey) on a log scale, over the token's full
Binance daily history back to 2017. Each panel is annotated with both returns and
both max drawdowns. The companion table is reports/generalization_summary.md.

Network: ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

WINDOW_START = "2017-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
NCOLS = 3

TOKENS = (
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "CAKE/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "LTC/USDT",
    "TRX/USDT",
    "AVAX/USDT",
    "ATOM/USDT",
    "XLM/USDT",
    "ETC/USDT",
    "EOS/USDT",
    "BCH/USDT",
    "FIL/USDT",
)

STRAT_COLOR = "#16a34a"
BH_COLOR = "#9ca3af"


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _equity(result):
    ts = [
        datetime.fromtimestamp(t / 1000, tz=timezone.utc)
        for t, _ in result.equity_curve
    ]
    return ts, [e for _, e in result.equity_curve]


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    panels = []
    for symbol in TOKENS:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"  SKIP {symbol}: {e}")
            continue
        s_res = run_backtest(
            candles,
            ENTRY.build_strategy(),
            symbol=symbol,
            risk=ENTRY.build_risk(),
            rebalance_band=ENTRY.rebalance_band,
        )
        b_res = buy_and_hold(candles, symbol=symbol)
        panels.append(
            {
                "symbol": symbol,
                "s_ts": _equity(s_res)[0],
                "s_eq": _equity(s_res)[1],
                "b_eq": _equity(b_res)[1],
                "sm": compute_metrics(s_res),
                "bm": compute_metrics(b_res),
                "start": datetime.fromtimestamp(candles[0].ts / 1000, tz=timezone.utc),
            }
        )
        print(f"  {symbol}")

    n = len(panels)
    nrows = math.ceil(n / NCOLS)
    fig, axes = plt.subplots(nrows, NCOLS, figsize=(15, 3.1 * nrows))
    axes = axes.flatten()

    for i, p in enumerate(panels):
        ax = axes[i]
        ax.plot(p["s_ts"], p["b_eq"], color=BH_COLOR, lw=1.0, label="buy & hold")
        ax.plot(p["s_ts"], p["s_eq"], color=STRAT_COLOR, lw=1.3, label="strategy")
        ax.set_yscale("log")
        sym = p["symbol"].split("/")[0]
        ax.set_title(f"{sym}  (from {p['start']:%Y-%m})", fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
        sm, bm = p["sm"], p["bm"]
        ax.text(
            0.03,
            0.97,
            f"strat {sm.total_return*100:+.0f}% / DD {sm.max_drawdown*100:.0f}%\n"
            f"hold  {bm.total_return*100:+.0f}% / DD {bm.max_drawdown*100:.0f}%",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=7.5,
            bbox=dict(boxstyle="round", fc="white", ec="#d1d5db", alpha=0.85),
        )
        if i == 0:
            ax.legend(loc="lower right", fontsize=7.5)

    for j in range(n, len(axes)):
        axes[j].axis("off")

    fig.suptitle(
        f"Performance across {n} tokens — {ENTRY.name} (green) vs buy & hold "
        f"(grey), full history, equity log scale",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/performance_all.png", dpi=110)
    plt.close(fig)
    print(f"\nWrote docs/performance_all.png ({n} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
