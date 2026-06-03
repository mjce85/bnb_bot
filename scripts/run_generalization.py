#!/usr/bin/env python
"""Broad generalization test — frozen entry across many tokens & full history.

Answers "does it hold on more candidates over a bigger timeframe?" by running the
LOCKED entry (no re-fitting) on a wide set of liquid Binance tokens, each over its
*full* available daily history (from 2017 / listing — pulling in the 2018 bear
that our 2021-start tests never saw), versus buy-and-hold.

Writes reports/generalization_summary.md and docs/generalization.png. Tokens with
data gaps are skipped loud. Network: ccxt on a cache miss.
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

WINDOW_START = "2017-01-01"  # loader returns from each token's listing onward
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"

# The 4 the entry was designed on, plus a broad set it never saw.
DESIGN_SET = {"BNB/USDT", "CAKE/USDT", "ETH/USDT", "BTC/USDT"}
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


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    rows = []
    for symbol in TOKENS:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"  SKIP {symbol}: {e}")
            continue
        res = run_backtest(
            candles,
            ENTRY.build_strategy(),
            symbol=symbol,
            risk=ENTRY.build_risk(),
            rebalance_band=ENTRY.rebalance_band,
        )
        m = compute_metrics(res)
        bh = compute_metrics(buy_and_hold(candles, symbol=symbol))
        start = datetime.fromtimestamp(candles[0].ts / 1000, tz=timezone.utc)
        rows.append(
            {
                "symbol": symbol,
                "m": m,
                "bh": bh,
                "dd_better": m.max_drawdown < bh.max_drawdown,
                "start": start.strftime("%Y-%m"),
                "bars": len(candles),
                "design": symbol in DESIGN_SET,
            }
        )
        print(
            f"  {symbol:10s} [{start:%Y-%m}] ret {_pct(m.total_return):>8s} "
            f"(hold {_pct(bh.total_return):>8s})  maxDD {_pct(m.max_drawdown):>6s} "
            f"(hold {_pct(bh.max_drawdown):>6s})  DD-better {m.max_drawdown < bh.max_drawdown}"
        )

    dd_wins = sum(r["dd_better"] for r in rows)
    avg_red = statistics.mean(r["bh"].max_drawdown - r["m"].max_drawdown for r in rows)
    print(
        f"\nDrawdown beaten on {dd_wins}/{len(rows)} tokens; "
        f"average drawdown reduction {_pct(avg_red)}."
    )
    _figure(rows)
    _write_summary(rows, dd_wins, avg_red)
    return 0


def _figure(rows) -> None:
    rows = sorted(rows, key=lambda r: r["bh"].max_drawdown)
    labels = [r["symbol"].split("/")[0] for r in rows]
    y = range(len(rows))
    fig, ax = plt.subplots(figsize=(10, 0.45 * len(rows) + 1.5))
    ax.barh(
        [i + 0.2 for i in y],
        [r["bh"].max_drawdown * 100 for r in rows],
        height=0.4,
        color="#9ca3af",
        label="buy & hold",
    )
    ax.barh(
        [i - 0.2 for i in y],
        [r["m"].max_drawdown * 100 for r in rows],
        height=0.4,
        color="#16a34a",
        label="strategy",
    )
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("max drawdown (%) — shorter is better")
    ax.set_title(
        f"Drawdown: strategy vs buy & hold across {len(rows)} liquid tokens "
        f"(full history, frozen entry)",
        fontsize=11,
    )
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/generalization.png", dpi=120)
    plt.close(fig)
    print("Wrote docs/generalization.png")


def _write_summary(rows, dd_wins, avg_red) -> None:
    os.makedirs("reports", exist_ok=True)
    lines = [
        "# Generalization summary — frozen entry, many tokens, full history",
        "",
        f"The locked entry **{ENTRY.name}** (no re-fitting) on **{len(rows)}** "
        f"liquid tokens, each over its full Binance daily history from "
        f"{WINDOW_START} (or listing) to {WINDOW_END}. Tokens marked * are the four "
        "the entry was designed on; the rest it never saw.",
        "",
        f"**Drawdown beaten on {dd_wins}/{len(rows)} tokens. Average drawdown "
        f"reduction vs buy-and-hold: {_pct(avg_red)}.**",
        "",
        "![drawdown across tokens](../docs/generalization.png)",
        "",
        "| Token | History from | Return | B&H | MaxDD | B&H MaxDD | DD beaten |",
        "| --- | --- | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in sorted(rows, key=lambda r: r["m"].max_drawdown):
        m, bh = r["m"], r["bh"]
        star = "*" if r["design"] else ""
        lines.append(
            f"| {r['symbol']}{star} | {r['start']} | {_pct(m.total_return)} | "
            f"{_pct(bh.total_return)} | {_pct(m.max_drawdown)} | {_pct(bh.max_drawdown)} | "
            f"{'yes' if r['dd_better'] else 'NO'} |"
        )
    lines.append("")
    path = os.path.join("reports", "generalization_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Summary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
