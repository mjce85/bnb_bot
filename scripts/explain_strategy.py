#!/usr/bin/env python
"""Visualize the locked entry's mechanics on one token (docs/strategy_mechanics.png).

Three stacked panels show the three layers acting on real BNB data:
  1. Price (log) + the 50-day trend line, shaded green where the strategy holds.
  2. The realized volatility vs the target — the input to position sizing.
  3. The resulting target weight (0 = cash, 1 = fully invested).

Network: ccxt on a cache miss (Binance spot, no key).
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

from bnb_bot.data import load_or_fetch  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402

SYMBOL = "BNB/USDT"
WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def main() -> int:
    candles = load_or_fetch(SYMBOL, "1d", _ms(WINDOW_START), _ms(WINDOW_END))
    closes = [c.close for c in candles]
    dts = [datetime.fromtimestamp(c.ts / 1000, tz=timezone.utc) for c in candles]

    strat = ENTRY.build_strategy()  # pure -> safe to call per prefix
    weights = [strat.signal(candles[: i + 1]) for i in range(len(candles))]

    tp = ENTRY.trend_period
    sma = [
        statistics.mean(closes[max(0, i - tp + 1) : i + 1]) if i >= tp - 1 else None
        for i in range(len(closes))
    ]

    vl = ENTRY.vol_lookback
    rvol = [None] * len(closes)
    for i in range(len(closes)):
        if i >= vl:
            rets = [closes[j] / closes[j - 1] - 1 for j in range(i - vl + 1, i + 1)]
            rvol[i] = statistics.pstdev(rets) * 100.0  # % per day

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(12, 9), sharex=True, height_ratios=[3, 1.3, 1.3]
    )

    # Panel 1: price + trend, shaded where invested.
    ax1.plot(dts, closes, color="#111827", lw=1.1, label=f"{SYMBOL} price")
    ax1.plot(dts, sma, color="#f59e0b", lw=1.4, label=f"{tp}-day trend (SMA)")
    ax1.fill_between(
        dts,
        min(closes),
        max(closes),
        where=[w > 0 for w in weights],
        color="#16a34a",
        alpha=0.12,
        label="strategy holding (else cash)",
    )
    ax1.set_yscale("log")
    ax1.set_ylabel("price (log)")
    ax1.set_title(
        "How the entry trades BNB — long only above the trend, sized by calm",
        fontsize=12,
    )
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Panel 2: realized vol vs target.
    ax2.plot(dts, rvol, color="#dc2626", lw=1.0, label="realized volatility (%/day)")
    ax2.axhline(
        ENTRY.target_vol * 100,
        color="#2563eb",
        ls="--",
        lw=1.2,
        label=f"target vol ({ENTRY.target_vol*100:.1f}%/day)",
    )
    ax2.set_ylabel("volatility")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Panel 3: resulting target weight.
    ax3.fill_between(dts, weights, 0, color="#16a34a", alpha=0.55)
    ax3.set_ylim(0, 1.05)
    ax3.set_ylabel("target weight\n(0 = cash, 1 = all in)")
    ax3.grid(True, alpha=0.3)

    fig.tight_layout()
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/strategy_mechanics.png", dpi=120)
    plt.close(fig)
    print("Wrote docs/strategy_mechanics.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
