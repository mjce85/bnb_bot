#!/usr/bin/env python
"""T8 baseline run — both strategies, all tokens, in-/out-of-sample split.

For each token we load one contiguous window, split it ~70/30 into an
*in-sample* head and an *out-of-sample* tail, and run both baseline strategies
on each segment independently. Each run gets its own markdown+plot report; a
consolidated ``reports/baseline_summary.md`` table is the input to FINDINGS.md.

Honesty choices, stated loud:

* **Risk-off.** Strategies are run at their raw target weight (up to fully
  invested). The gate question is whether the *signal* beats fees; the default
  ``max_position_frac=0.25`` would only ever deploy a quarter and blur that.
  The risk layer (T5) is built and tested separately.
* **Independent OOS.** The out-of-sample segment starts flat and re-warms its
  own indicators — it does not peek at in-sample state. The first ``lookback``
  bars of each segment are therefore flat warmup, slightly shortening the
  active period. That is the honest cost of a clean split.

Network: fetches history via ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.report import render_report  # noqa: E402
from bnb_bot.strategy import MeanReversion, Momentum  # noqa: E402

WINDOW_START = "2024-06-01"
WINDOW_END = "2026-06-01"  # exclusive
TIMEFRAME = "1h"
SPLIT = 0.70  # fraction of bars used as in-sample
OUT_DIR = "reports"

# Fresh instance per run — MeanReversion carries causal stance state.
STRATEGIES = {
    "momentum": Momentum,
    "mean_reversion": MeanReversion,
}


def _ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _fmt_ratio(x: float) -> str:
    if x == float("inf"):
        return "+inf"
    if x == float("-inf"):
        return "-inf"
    return f"{x:.2f}"


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    rows = []

    for symbol in config.TOKEN_SET:
        print(f"\n=== {symbol} ===")
        print(f"Loading {TIMEFRAME} {WINDOW_START}..{WINDOW_END} ...")
        candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        n = len(candles)
        k = int(n * SPLIT)
        segments = {
            "in_sample": candles[:k],
            "out_of_sample": candles[k:],
        }
        print(f"  {n} bars -> in_sample {k}, out_of_sample {n - k}")

        for sname, factory in STRATEGIES.items():
            for label, seg in segments.items():
                strat = factory()
                res = run_backtest(
                    seg,
                    strat,
                    symbol=symbol,
                    strategy_name=strat.name,
                    params=strat.params,
                )
                m = compute_metrics(res)
                render_report(
                    res,
                    m,
                    out_dir=OUT_DIR,
                    label=label,
                    caveats=[
                        f"Segment: {label} ({len(seg)} bars).",
                        "Risk-off baseline: raw strategy weight, no position cap.",
                    ],
                )
                rows.append(
                    {
                        "symbol": symbol,
                        "strategy": sname,
                        "window": label,
                        "ret": m.total_return,
                        "dd": m.max_drawdown,
                        "sharpe": m.sharpe,
                        "sortino": m.sortino,
                        "calmar": m.calmar,
                        "win": m.win_rate,
                        "trades": m.n_trades,
                        "bars": m.n_bars,
                    }
                )
                print(
                    f"  {sname:14s} {label:14s} "
                    f"ret {_fmt_pct(m.total_return):>8s}  "
                    f"DD {_fmt_pct(m.max_drawdown):>7s}  "
                    f"Sharpe {_fmt_ratio(m.sharpe):>6s}  "
                    f"trades {m.n_trades}"
                )

    _write_summary(rows)
    return 0


def _write_summary(rows: list[dict]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    header = (
        "| Symbol | Strategy | Window | Return | MaxDD | Sharpe | Sortino | "
        "Calmar | WinRate | Trades | Bars |"
    )
    sep = "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    lines = [
        "# Baseline summary (T8)",
        "",
        f"Window **{WINDOW_START} → {WINDOW_END}**, timeframe **{TIMEFRAME}**, "
        f"split **{int(SPLIT * 100)}/{int((1 - SPLIT) * 100)}** "
        "(in-sample head / out-of-sample tail).",
        "",
        "Risk-off baseline (raw strategy weight). Every fill pays swap fee + "
        "slippage + gas. Signals causal; fills at next open.",
        "",
        header,
        sep,
    ]
    for r in rows:
        lines.append(
            f"| {r['symbol']} | {r['strategy']} | {r['window']} | "
            f"{_fmt_pct(r['ret'])} | {_fmt_pct(r['dd'])} | "
            f"{_fmt_ratio(r['sharpe'])} | {_fmt_ratio(r['sortino'])} | "
            f"{_fmt_ratio(r['calmar'])} | {_fmt_pct(r['win'])} | "
            f"{r['trades']} | {r['bars']} |"
        )
    lines.append("")
    path = os.path.join(OUT_DIR, "baseline_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
