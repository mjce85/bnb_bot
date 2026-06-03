#!/usr/bin/env python
"""Regime stress slices — how the entry behaves when trends aren't handed to it.

Trend strategies thrive in sustained moves and bleed in choppy, directionless
markets. This runs the FROZEN entry across distinct historical regimes — the 2018
crash, the 2019–20 chop (the real stress), the 2021 bull, the 2022 bear, the
2023–24 recovery — across the deep-history tokens, vs buy-and-hold. The honest
question: does it still control drawdown in the regimes it's *worst* suited to,
and where does it give up return?

Writes reports/regime_slices_summary.md and docs/regime_slices.png. Network: ccxt.
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

from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

TIMEFRAME = "1d"
MIN_BARS = 80  # need warmup (trend 50 + vol 15) + room

SLICES = [
    ("2018 crash", "2018-01-01", "2019-01-01"),
    ("2019-20 chop", "2019-01-01", "2020-10-01"),
    ("2021 bull", "2021-01-01", "2022-01-01"),
    ("2022 bear", "2022-01-01", "2023-01-01"),
    ("2023-24 recovery", "2023-01-01", "2025-01-01"),
]

TOKENS = (
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "LTC/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "TRX/USDT",
    "XLM/USDT",
    "ETC/USDT",
    "EOS/USDT",
    "LINK/USDT",
    "BCH/USDT",
    "ATOM/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "AVAX/USDT",
    "FIL/USDT",
    "CAKE/USDT",
)


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> int:
    full = {}
    for sym in TOKENS:
        try:
            full[sym] = load_or_fetch(
                sym, TIMEFRAME, _ms("2017-01-01"), _ms("2026-06-01")
            )
        except DataGapError as e:
            print(f"SKIP {sym}: {e}")

    results = []
    for name, start, end in SLICES:
        lo, hi = _ms(start), _ms(end)
        s_rets, h_rets, s_dds, h_dds, dd_wins = [], [], [], [], 0
        n = 0
        for sym, cands in full.items():
            seg = [c for c in cands if lo <= c.ts < hi]
            if len(seg) < MIN_BARS:
                continue
            m = compute_metrics(
                run_backtest(
                    seg,
                    ENTRY.build_strategy(),
                    symbol=sym,
                    risk=ENTRY.build_risk(),
                    rebalance_band=ENTRY.rebalance_band,
                )
            )
            bh = compute_metrics(buy_and_hold(seg, symbol=sym))
            s_rets.append(m.total_return)
            h_rets.append(bh.total_return)
            s_dds.append(m.max_drawdown)
            h_dds.append(bh.max_drawdown)
            dd_wins += m.max_drawdown < bh.max_drawdown
            n += 1
        row = {
            "name": name,
            "n": n,
            "s_ret": statistics.median(s_rets),
            "h_ret": statistics.median(h_rets),
            "s_dd": statistics.median(s_dds),
            "h_dd": statistics.median(h_dds),
            "dd_wins": dd_wins,
        }
        results.append(row)
        print(
            f"  {name:18s} (n={n})  strat ret {_pct(row['s_ret']):>7s} "
            f"(hold {_pct(row['h_ret']):>7s})  strat DD {_pct(row['s_dd']):>6s} "
            f"(hold {_pct(row['h_dd']):>6s})  DD-better {dd_wins}/{n}"
        )

    _figure(results)
    _write_summary(results)
    return 0


def _figure(results) -> None:
    names = [r["name"] for r in results]
    x = range(len(results))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.6))

    ax1.bar(
        [i - 0.2 for i in x],
        [r["h_ret"] * 100 for r in results],
        width=0.4,
        color="#9ca3af",
        label="buy & hold",
    )
    ax1.bar(
        [i + 0.2 for i in x],
        [r["s_ret"] * 100 for r in results],
        width=0.4,
        color="#16a34a",
        label="strategy",
    )
    ax1.axhline(0, color="#111827", lw=0.8)
    ax1.set_title("Median return by regime")
    ax1.set_ylabel("return (%)")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(names, rotation=20, fontsize=8, ha="right")
    ax1.legend(fontsize=8)

    ax2.bar(
        [i - 0.2 for i in x],
        [r["h_dd"] * 100 for r in results],
        width=0.4,
        color="#9ca3af",
        label="buy & hold",
    )
    ax2.bar(
        [i + 0.2 for i in x],
        [r["s_dd"] * 100 for r in results],
        width=0.4,
        color="#16a34a",
        label="strategy",
    )
    ax2.set_title("Median max drawdown by regime (lower is better)")
    ax2.set_ylabel("max drawdown (%)")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(names, rotation=20, fontsize=8, ha="right")
    ax2.legend(fontsize=8)

    fig.suptitle(
        "Frozen entry across market regimes (median across tokens)", fontsize=12
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/regime_slices.png", dpi=120)
    plt.close(fig)
    print("Wrote docs/regime_slices.png")


def _write_summary(results) -> None:
    os.makedirs("reports", exist_ok=True)
    lines = [
        "# Regime stress slices — the entry across different market types",
        "",
        "Frozen entry vs buy-and-hold across distinct regimes, median across the "
        "deep-history tokens available in each slice. The **2019–20 chop** is the "
        "hardest case for a trend strategy (no sustained direction to ride).",
        "",
        "![regime slices](../docs/regime_slices.png)",
        "",
        "| Regime | Tokens | Strat return | Hold return | Strat MaxDD | Hold MaxDD | DD beaten |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['n']} | {_pct(r['s_ret'])} | {_pct(r['h_ret'])} | "
            f"{_pct(r['s_dd'])} | {_pct(r['h_dd'])} | {r['dd_wins']}/{r['n']} |"
        )
    lines += [
        "",
        "Read it honestly: drawdown control should hold even in chop (it sits in "
        "cash), but *return* is where chop hurts — the strategy gives up the most, "
        "relative to its trending-market results, when there's no trend to capture.",
        "",
    ]
    with open("reports/regime_slices_summary.md", "w") as f:
        f.write("\n".join(lines))
    print("Summary: reports/regime_slices_summary.md")


if __name__ == "__main__":
    raise SystemExit(main())
